import logging
from collections.abc import Sequence

import psycopg
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from webhook_relay.dependencies import DbSession, SubscriptionDep
from webhook_relay.models.subscription import (
    SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT,
    Subscription,
)
from webhook_relay.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionUpdate,
)
from webhook_relay.schemas.types import EventType

# Test imports
from webhook_relay.services.subscriptions import get_active_subscriptions

PG_UNIQUE_VIOLATION = "23505"

SUBSCRIPTION_CONFLICT_MESSAGE = (
    "A subscription for this target url and event type already exists. "
    "Reactivate the existing subscription using PATCH instead."
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def get_db_error_details(error: BaseException | None) -> tuple[str | None, str | None]:
    """Return (sqlstate, constraint_name) for a psycopg error, else (None, None)."""
    if isinstance(error, psycopg.Error):
        constraint_name = error.diag.constraint_name if error.diag else None
        return error.sqlstate, constraint_name
    return None, None


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SubscriptionRead,
    responses={
        409: {
            "description": (
                "A subscription already exists for this target URL and event type."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "message": (SUBSCRIPTION_CONFLICT_MESSAGE),
                            "subscription_id": 42,
                        }
                    }
                }
            },
        }
    },
)
def create_subscription(
    subscription_data: SubscriptionCreate, db: DbSession
) -> Subscription:
    subscription = Subscription(
        target_url=str(subscription_data.target_url),
        event_type=subscription_data.event_type,
    )
    db.add(subscription)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        sqlstate, constraint_name = get_db_error_details(exc.orig)

        if (
            sqlstate == PG_UNIQUE_VIOLATION
            and constraint_name == SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT
        ):
            logger.warning(
                "Failed to create subscription: subscription already exists for hostname=%s and event_type=%s",
                subscription_data.target_url.host,
                subscription_data.event_type,
            )

            existing_subscription = db.scalar(
                select(Subscription).where(
                    Subscription.target_url == str(subscription_data.target_url),
                    Subscription.event_type == subscription_data.event_type,
                )
            )

            if existing_subscription is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": (
                            "A conflicting subscription was detected, "
                            "but it could not be retrieved. Please retry."
                        ),
                        "subscription_id": None,
                    },
                ) from None

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (SUBSCRIPTION_CONFLICT_MESSAGE),
                    "subscription_id": existing_subscription.id,
                },
            ) from None

        logger.error(
            "Unexpected database error while creating subscription "
            "(sqlstate=%s, constraint=%s)",
            sqlstate,
            constraint_name,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None

    db.refresh(subscription)
    return subscription


@router.get("", status_code=status.HTTP_200_OK, response_model=list[SubscriptionRead])
def list_subscriptions(
    db: DbSession,
    target_url: HttpUrl | None = None,
    event_type: EventType | None = None,
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Subscription]:
    query = select(Subscription)
    if target_url is not None:
        query = query.where(Subscription.target_url == str(target_url))

    if event_type is not None:
        query = query.where(Subscription.event_type == event_type)

    if active is not None:
        query = query.where(Subscription.active == active)

    query = (
        query.order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .limit(limit)
        .offset(offset)
    )

    subscriptions = db.scalars(query).all()

    return subscriptions


# --- Test Endpoint ---


@router.get(
    "/active_subs",
    response_model=list[SubscriptionRead],
)
def debug_active_subscriptions(
    db: DbSession, event_type: EventType
) -> Sequence[Subscription]:
    return get_active_subscriptions(db, event_type)


# --- END ---


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionRead,
)
def get_subscription(
    subscription: SubscriptionDep,
) -> Subscription:
    return subscription


@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionRead,
)
def update_subscription(
    subscription_update: SubscriptionUpdate,
    subscription: SubscriptionDep,
    db: DbSession,
) -> Subscription:
    subscription.active = subscription_update.active

    db.commit()

    return subscription
