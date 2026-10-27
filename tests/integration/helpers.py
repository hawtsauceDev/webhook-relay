from sqlalchemy import select
from sqlalchemy.orm import Session

from webhook_relay.enums import DeliveryStatus
from webhook_relay.models import Delivery, Event, Subscription
from webhook_relay.models.delivery_attempt import DeliveryAttempt

SECRET_URL = "https://hooks.example.com/token-abc123"


def make_delivery(
    db: Session,
    *,
    active: bool = True,
    status: DeliveryStatus = DeliveryStatus.PENDING,
) -> Delivery:
    subscription = Subscription(
        target_url=SECRET_URL, event_type="order.created", active=active
    )
    event = Event(event_type="order.created", payload={"order_id": 1})
    db.add_all([subscription, event])
    db.flush()  # assigns ids without committing
    delivery = Delivery(event=event, subscription_id=subscription.id, status=status)
    db.add(delivery)
    db.commit()
    return delivery


def reload(db: Session, delivery: Delivery) -> Delivery:
    # The task commits from ANOTHER session, and our session does not expire
    # objects on commit, so without a refresh we would read stale values.
    db.refresh(delivery)
    return delivery


def attempts_for(db: Session, delivery_id: int) -> list[DeliveryAttempt]:
    query = (
        select(DeliveryAttempt)
        .where(DeliveryAttempt.delivery_id == delivery_id)
        .order_by(DeliveryAttempt.id)
    )
    return list(db.scalars(query).all())