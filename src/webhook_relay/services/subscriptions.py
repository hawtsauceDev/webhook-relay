import logging
from collections.abc import Sequence
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from webhook_relay.db_errors import PG_UNIQUE_VIOLATION, get_db_error_details
from webhook_relay.exceptions import (
    SubscriptionAlreadyExists,
    SubscriptionCreationError,
    SubscriptionUpdateError,
)
from webhook_relay.models.subscription import (
    SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT,
    Subscription,
)

logger = logging.getLogger(__name__)





def create_subscription(db: Session, target_url: str, event_type: str) -> Subscription:
    subscription = Subscription(target_url=target_url, event_type=event_type)
    db.add(subscription)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        sqlstate, constraint_name = get_db_error_details(getattr(exc, "orig", None))
        if (
            sqlstate == PG_UNIQUE_VIOLATION
            and constraint_name == SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT
        ):
            logger.warning(
                "Failed to create subscription: already exists for hostname=%s and event_type=%s",
                urlsplit(target_url).hostname,
                event_type,
            )
            existing_id = _find_existing_subscription_id(db, target_url, event_type)
            raise SubscriptionAlreadyExists(existing_id) from None
        logger.error(
            "Unexpected database error while creating subscription "
            "(error_type=%s, sqlstate=%s, constraint=%s)",
            type(exc).__name__,
            sqlstate,
            constraint_name,
        )
        raise SubscriptionCreationError from None
    return subscription


def _find_existing_subscription_id(
    db: Session, target_url: str, event_type: str
) -> int | None:
    try:
        return db.scalar(
            select(Subscription.id).where(
                Subscription.target_url == target_url,
                Subscription.event_type == event_type,
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning(
            "Could not re-read existing subscription id (error_type=%s)",
            type(exc).__name__,
        )
        return None


def get_active_subscriptions(db: Session, event_type: str) -> Sequence[Subscription]:
    query = (
        select(Subscription)
        .where(Subscription.event_type == event_type, Subscription.active.is_(True))
        .order_by(Subscription.id)
    )

    subscriptions = db.scalars(query).all()
    return subscriptions


def update_subscription(
    db: Session, subscription: Subscription, active: bool
) -> Subscription:
    subscription_id = subscription.id
    subscription.active = active
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        sqlstate, constraint_name = get_db_error_details(getattr(exc, "orig", None))
        logger.error(
            "Unexpected database error while updating subscription "
            "(subscription_id=%s, error_type=%s, sqlstate=%s, constraint=%s)",
            subscription_id,
            type(exc).__name__,
            sqlstate,
            constraint_name,
        )
        raise SubscriptionUpdateError from None
    return subscription
