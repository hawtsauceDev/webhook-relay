from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictBool

from webhook_relay.schemas.types import EventType


class SubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_url: HttpUrl = Field(
        description="HTTP or HTTPS URL that receives webhook deliveries.",
        examples=["https://example.com/webhook"],
    )
    event_type: EventType = Field(
        description="Event type this subscription receives.",
        examples=["order.created"],
    )


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: StrictBool = Field(
        description="Whether the subscription should receive new deliveries.",
    )


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_url: str
    event_type: str
    active: bool
    created_at: datetime
