import logging

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from webhook_relay.dependencies import DbSession
from webhook_relay.models.subscription import Subscription
from webhook_relay.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionUpdate,
)
from webhook_relay.schemas.types import EventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=SubscriptionRead)
def create_subscription(
    subscription_data: SubscriptionCreate, db: DbSession
) -> SubscriptionRead:
    subscription = Subscription(**subscription_data.model_dump(mode="json"))
    db.add(subscription)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        constraint_name = getattr(
            getattr(exc.orig, "diag", None), "constraint_name", None
        )

        if constraint_name == "uq_subscriptions_target_url":
            logger.warning(
                "Failed to create subscription: subscription already exists for target_url=%s and event_type=%s",
                str(subscription.target_url),
                str(subscription.event_type),
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A subscription for this target url and event type already exists. Reactivate the existing subscription using PATCH instead.",
            )
        logger.exception("Unexpected database error while creating subscription")
        raise
    db.refresh(subscription)

    return subscription


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[SubscriptionRead])
def list_subscriptions(
    db: DbSession,
    event_type: EventType | None = None,
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SubscriptionRead]:
    query = select(Subscription)

    if event_type is not None:
        query = query.where(Subscription.event_type == event_type)

    if active is not None:
        query = query.where(Subscription.active == active)

    query = query.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)

    subscriptions = db.scalars(query).all()

    return subscriptions


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionRead,
)
def get_subscription(
    db: DbSession,
    subscription_id: int = Path(ge=1),
) -> SubscriptionRead:
    query = select(Subscription).where(Subscription.id == subscription_id)
    subscription = db.scalar(query)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    return subscription


@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionRead,
)
def update_subscription(
    subscription_id: int,
    subscription_update: SubscriptionUpdate,
    db: DbSession,
) -> SubscriptionRead:
    query = select(Subscription).where(Subscription.id == subscription_id)
    subscription = db.scalar(query)

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    subscription.active = subscription_update.active

    db.commit()
    db.refresh(subscription)

    return subscription
