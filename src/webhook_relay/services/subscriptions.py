import logging
from collections.abc import Sequence
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from webhook_relay.db_errors import PG_UNIQUE_VIOLATION, get_db_error_details
from webhook_relay.models.subscription import (
    SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT,
    Subscription,
)

logger = logging.getLogger(__name__)


class SubscriptionAlreadyExists(Exception):
    def __init__(self, existing_id: int | None) -> None:
        super().__init__("Subscription already exists")
        self.existing_id = existing_id


def create_subscription(db: Session, target_url: str, event_type: str) -> Subscription:
    subscription = Subscription(target_url=target_url, event_type=event_type)
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
                "Failed to create subscription: already exists for hostname=%s and event_type=%s",
                urlsplit(target_url).hostname,
                event_type,
            )
            existing_id = db.scalar(
                select(Subscription.id).where(
                    Subscription.target_url == target_url,
                    Subscription.event_type == event_type,
                )
            )
            raise SubscriptionAlreadyExists(existing_id) from exc
        logger.error(
            "Unexpected database error while creating subscription "
            "(sqlstate=%s, constraint=%s)",
            sqlstate,
            constraint_name,
        )
        raise
    db.refresh(subscription)
    return subscription


def get_active_subscriptions(db: Session, event_type: str) -> Sequence[Subscription]:
    query = (
        select(Subscription)
        .where(Subscription.event_type == event_type, Subscription.active.is_(True))
        .order_by(Subscription.id)
    )

    subscriptions = db.scalars(query).all()
    return subscriptions
