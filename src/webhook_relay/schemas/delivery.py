from pydantic import BaseModel, ConfigDict

from webhook_relay.enums import DeliveryStatus


class DeliveryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    subscription_id: int
    status: DeliveryStatus
    attempt_count: int
