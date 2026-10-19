from celery import Celery

from webhook_relay.config import get_settings

settings = get_settings()

app = Celery(
    "webhook_relay",
    broker = settings.celery_broker_url.get_secret_value(),
    include=["webhook_relay.worker.tasks"]
)