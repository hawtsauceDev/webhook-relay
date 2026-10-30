from datetime import datetime

from pydantic import BaseModel, ConfigDict

from webhook_relay.enums import DeliveryStatus


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subscription_id: int
    status: DeliveryStatus
    attempt_count: int
    created_at: datetime
