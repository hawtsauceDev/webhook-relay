import logging

from webhook_relay.database import SessionLocal
from webhook_relay.enums import DeliveryStatus
from webhook_relay.models import Delivery
from webhook_relay.worker.celery_app import app

logger = logging.getLogger(__name__)


@app.task
def process_delivery(delivery_id: int) -> None:
    with SessionLocal() as db:  
        delivery = db.get(Delivery, delivery_id)
        if delivery is None:
            logger.warning(
                "Delivery destination does not exist. delivery_id=%s", delivery_id
            )
            return
        if delivery.status == DeliveryStatus.SUCCESS:
            logger.info("Delivery SUCCESS. delivery_id=%s", delivery_id)
            return
        delivery.status = DeliveryStatus.PROCESSING
        db.commit()
        logger.info("Delivery PROCESSING. delivery_id =%s", delivery_id)
        delivery.status = DeliveryStatus.SUCCESS
        db.commit()
        logger.info("Delivery SUCCESS. delivery_id =%s", delivery_id)
