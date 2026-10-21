from celery import Celery

from webhook_relay.config import get_settings

settings = get_settings()

app = Celery(
    "webhook_relay",
    broker=settings.celery_broker_url.get_secret_value(),
    include=["webhook_relay.worker.tasks"],
)

app.conf.update(task_acks_late=True, task_soft_time_limit=30, task_time_limit=40)
