import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from webhook_relay.db_errors import get_db_error_details
from webhook_relay.enums import DeliveryStatus
from webhook_relay.exceptions import DeliveryAttemptRecordingError
from webhook_relay.models.delivery import Delivery
from webhook_relay.models.delivery_attempt import DeliveryAttempt

logger = logging.getLogger(__name__)


def record_delivery_attempt(
    db: Session,
    delivery: Delivery,
    new_status: DeliveryStatus,
    response_status: int | None = None,
    error_label: str | None = None,
) -> None:
    delivery_id = delivery.id
    try:
        delivery.status = new_status
        delivery.attempt_count = Delivery.attempt_count + 1
        delivery_attempt = DeliveryAttempt(
            delivery=delivery, response_status=response_status, error=error_label
        )
        db.add(delivery_attempt)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        sqlstate, constraint_name = get_db_error_details(getattr(exc, "orig", None))
        logger.error(
            "Unexpected database error while recording delivery attempt"
            "(delivery_id=%s, error_type=%s, sqlstate=%s, constraint_name=%s)",
            delivery_id,
            type(exc).__name__,
            sqlstate,
            constraint_name,
        )
        raise DeliveryAttemptRecordingError from None

    logger.info(
        "Delivery attempt recorded. delivery_id=%s, attempt_id=%s, status=%s",
        delivery_id,
        delivery_attempt.id,
        new_status,
    )
