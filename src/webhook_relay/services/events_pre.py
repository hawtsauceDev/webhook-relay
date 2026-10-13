import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from webhook_relay.enums import DeliveryStatus
from webhook_relay.models.delivery import Delivery
from webhook_relay.models.event import Event
from webhook_relay.services.subscriptions import get_active_subscriptions

logger = logging.getLogger(__name__)


def ingest_event(
    db: Session, event_type: str, payload: dict[str, Any]
) -> tuple[Event, list[Delivery]]:
    event = Event(event_type=event_type, payload=payload)
    db.add(event)
    try:
        db.flush()

        matching_subs = get_active_subscriptions(db, event_type)

        delivery_list: list[Delivery] = []
        for sub in matching_subs:
            delivery = Delivery(
                event_id=event.id, subscription_id=sub.id, status=DeliveryStatus.PENDING
            )
            delivery_list.append(delivery)
            db.add(delivery)

        db.commit()
        logger.info(
            "Event created. event_id=%s, event_type=%s, deliveries=%s",
            event.id,
            event.event_type,
            len(delivery_list),
        )
    except SQLAlchemyError:
        db.rollback()

        logger.exception("Error while creating Event with event_type=%s", event_type)
        raise

    return event, delivery_list
