from datetime import datetime

from sqlalchemy import TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from webhook_relay.models.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_url: Mapped[str]
    event_type: Mapped[str] = mapped_column(index=True)
    active: Mapped[bool] = mapped_column(
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    deliveries: Mapped[list["Delivery"]] = relationship(
        back_populates="subscription",
    )

    __table_args__ = (UniqueConstraint("target_url", "event_type"),)
