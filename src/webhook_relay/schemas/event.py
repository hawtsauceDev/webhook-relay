from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from webhook_relay.enums import DeliveryStatus
from webhook_relay.schemas.types import EventType


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: EventType = Field(
        description="Event type of the incoming event", examples=["order.created"]
    )
    payload: dict[str, Any] = Field(
        description="Payload of the incoming event", examples=[{"order_id": 1}]
    )


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subscription_id: int
    status: DeliveryStatus
    created_at: datetime


class EventCreateResponse(BaseModel):
    id: int
    event_type: str
    delivery_ids: list[int]
    created_at: datetime
