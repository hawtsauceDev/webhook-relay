import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from webhook_relay.db_errors import get_db_error_details
from webhook_relay.enums import DeliveryStatus
from webhook_relay.exceptions import EventIngestionError
from webhook_relay.models.delivery import Delivery
from webhook_relay.models.event import Event
from webhook_relay.services.subscriptions import get_active_subscriptions

logger = logging.getLogger(__name__)


def ingest_event(
    db: Session, event_type: str, payload: dict[str, Any]
) -> tuple[Event, list[Delivery]]:
    try:
        matching_subs = get_active_subscriptions(db, event_type)

        event = Event(event_type=event_type, payload=payload)
        db.add(event)
        delivery_list: list[Delivery] = []

        for sub in matching_subs:
            delivery = Delivery(
                event=event, subscription_id=sub.id, status=DeliveryStatus.PENDING
            )
            delivery_list.append(delivery)

        db.add_all(delivery_list)
        db.commit()

    except SQLAlchemyError as exc:
        db.rollback()
        sqlstate, constraint_name = get_db_error_details(getattr(exc, "orig", None))
        logger.error(
            "Unexpected database error while ingesting event "
            "(event_type=%s, error_type=%s, sqlstate=%s, constraint=%s)",
            event_type,
            type(exc).__name__,
            sqlstate,
            constraint_name,
        )
        raise EventIngestionError from None

    logger.info(
        "Event created. event_id=%s, event_type=%s, deliveries=%s",
        event.id,
        event.event_type,
        len(delivery_list),
    )
    return event, delivery_list
