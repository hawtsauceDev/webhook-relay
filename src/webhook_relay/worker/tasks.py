import logging

import httpx
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from webhook_relay.database import SessionLocal
from webhook_relay.enums import DeliveryStatus
from webhook_relay.exceptions import DeliveryAttemptRecordingError
from webhook_relay.models import Delivery, Event, Subscription
from webhook_relay.services.deliveries import record_delivery_attempt
from webhook_relay.worker.celery_app import app

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10

DELIVERY_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@app.task(bind=True, max_retries=MAX_RETRIES)
def process_delivery(self: Task, delivery_id: int) -> None:
    with SessionLocal() as db:
        delivery = db.get(Delivery, delivery_id)
        if delivery is None:
            logger.warning("Delivery %s not found; skipping", delivery_id)
            return
        if delivery.status == DeliveryStatus.SUCCESS:
            logger.info("Delivery %s already succeeded; skipping", delivery_id)
            return
        if delivery.status == DeliveryStatus.SKIPPED:
            logger.info(
                "Delivery %s already skipped; not reprocessing",
                delivery_id,
            )
            return

        subscription = db.get(Subscription, delivery.subscription_id)
        event = db.get(Event, delivery.event_id)
        if subscription is None or event is None:
            # FKs make this almost impossible; if it happens, fail loudly.
            logger.error("Delivery %s has missing parent rows", delivery_id)
            return
        # Use plain values, so the HTTP section does not depend on ORM objects or session state.
        target_url = subscription.target_url
        body = {
            "event_id": event.id,
            "event_type": event.event_type,
            "payload": event.payload,
        }
        host = httpx.URL(target_url).host

        if not subscription.active:
            logger.info(
                "Delivery %s skipped: subscription %s is inactive",
                delivery_id,
                subscription.id,
            )
            delivery.status = DeliveryStatus.SKIPPED
            db.commit()
            return

        delivery.status = DeliveryStatus.PROCESSING
        db.commit()

        response_status: int | None = None
        error_label: str | None = None
        delivered = False

        try:
            response = httpx.post(target_url, json=body, timeout=DELIVERY_TIMEOUT)
        except httpx.RequestError as exc:
            # Transport failure: timeout, DNS, conncetion refused.
            # Log the class name only: the message could inlude the url (not safe).
            error_label = type(exc).__name__
            logger.warning(
                "Delivery %s to %s failed: %s", delivery_id, host, error_label
            )
        except SoftTimeLimitExceeded:
            error_label = "SoftTimeLimitExceeded"
            logger.warning(
                "Delivery %s to %s hit the soft time limit", delivery_id, host
            )

        else:
            response_status = response.status_code
            delivered = response.is_success
            if delivered:
                logger.info(
                    "Delivery %s to %s succeeded (%s)",
                    delivery_id,
                    host,
                    response_status,
                )
            else:
                logger.warning(
                    "Delivery %s to %s got HTTP %s", delivery_id, host, response_status
                )
        if delivered:
            new_status = DeliveryStatus.SUCCESS
        elif self.request.retries < MAX_RETRIES:
            new_status = DeliveryStatus.PENDING
        else:
            new_status = DeliveryStatus.FAILED

        try:
            record_delivery_attempt(
                db, delivery, new_status, response_status, error_label
            )
        except DeliveryAttemptRecordingError as exc:
            # The POST may already have happened: re-running the task can duplicate it.
            # Accepted under at-leat-once
            raise self.retry(exc=exc, countdown=RETRY_DELAY_SECONDS)

        if new_status == DeliveryStatus.PENDING:
            raise self.retry(countdown=RETRY_DELAY_SECONDS)
