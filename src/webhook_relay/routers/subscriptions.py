from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from webhook_relay.dependencies import DbSession
from webhook_relay.models.subscription import Subscription
from webhook_relay.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionRead,
    SubscriptionUpdate,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=SubscriptionRead)
def create_subscription(
    db: DbSession, subscription_data: SubscriptionCreate
) -> SubscriptionRead:
    subscription = Subscription(**subscription_data.model_dump())

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return subscription


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[SubscriptionRead])
def list_subscriptions(
    db: DbSession,
    event_type: str | None = None,
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
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionRead,
)
def get_subscription(db: DbSession, subscription_id: int) -> SubscriptionRead:
    query = select(Subscription).where(Subscription.id == subscription_id)
    subscription = db.scalars(query).first()
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    return subscription


@router.patch(
    "/{subscription_id}",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionRead,
)
def update_subscription(
    db: DbSession, subscription_id: int, subscription_update: SubscriptionUpdate
) -> SubscriptionRead:
    query = select(Subscription).where(Subscription.id == subscription_id)
    subscription = db.scalars(query).first()

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )

    subscription.active = subscription_update.active

    db.commit()
    db.refresh(subscription)

    return subscription
