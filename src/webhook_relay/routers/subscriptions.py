from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import HttpUrl
from sqlalchemy import select

from webhook_relay.dependencies import DbSession, SubscriptionDep
from webhook_relay.models.subscription import (
    Subscription,
)
from webhook_relay.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionUpdate,
)
from webhook_relay.schemas.types import EventType
from webhook_relay.services import subscriptions as subscriptions_service
from webhook_relay.services.subscriptions import (
    SubscriptionAlreadyExists,
)

SUBSCRIPTION_CONFLICT_MESSAGE = (
    "A subscription for this target url and event type already exists. "
    "Reactivate the existing subscription using PATCH instead."
)
SUBSCRIPTION_CONFLICT_MESSAGE_NONE = "A conflicting subscription was detected, but it could not be retrieved. Please retry."


router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SubscriptionRead,
    summary="Create a new subscription",
    responses={
        status.HTTP_409_CONFLICT: {
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
    try:
        return subscriptions_service.create_subscription(
            db, str(subscription_data.target_url), subscription_data.event_type
        )
    except SubscriptionAlreadyExists as exc:
        if exc.existing_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": SUBSCRIPTION_CONFLICT_MESSAGE_NONE,
                    "subscription_id": None,
                },
            ) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": SUBSCRIPTION_CONFLICT_MESSAGE,
                "subscription_id": exc.existing_id,
            },
        ) from None


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
