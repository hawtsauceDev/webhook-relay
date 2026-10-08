from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from webhook_relay.enums import DeliveryStatus
from webhook_relay.models.base import Base


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"),
        index=True,
    )

    status: Mapped[DeliveryStatus] = mapped_column(String(25), server_default="pending")

    attempt_count: Mapped[int] = mapped_column(server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )

    event: Mapped["Event"] = relationship(
        back_populates="deliveries",
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="deliveries")

    attempts: Mapped[list["DeliveryAttempt"]] = relationship(back_populates="delivery")
