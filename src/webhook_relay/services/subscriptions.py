from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from webhook_relay.models.subscription import Subscription


def get_active_subscriptions(db: Session, event_type: str) -> Sequence[Subscription]:
    query = (
        select(Subscription)
        .where(Subscription.event_type == event_type, Subscription.active.is_(True))
        .order_by(Subscription.id)
    )

    subscriptions = db.scalars(query).all()
    return subscriptions
