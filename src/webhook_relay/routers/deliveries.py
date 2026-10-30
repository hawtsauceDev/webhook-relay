from collections.abc import Sequence

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from webhook_relay.dependencies import DbSession
from webhook_relay.enums import DeliveryStatus
from webhook_relay.models.delivery import Delivery
from webhook_relay.schemas.delivery import DeliveryRead

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=list[DeliveryRead],
    summary="List deliveries",
)
def list_deliveries(
    db: DbSession,
    subscription_id: int | None = None,
    status_filter: DeliveryStatus | None = Query(default=None, alias="status"),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Sequence[Delivery]:
    """List deliveries, optionally filtered by subscription or status.

    Results are ordered by most recently created first.
    """

    query = select(Delivery)
    if subscription_id is not None:
        query = query.where(Delivery.subscription_id == subscription_id)

    if status_filter is not None:
        query = query.where(Delivery.status == status_filter)

    query = (
        query.order_by(Delivery.created_at.desc(), Delivery.id.desc())
        .limit(limit)
        .offset(offset)
    )

    deliveries = db.scalars(query).all()

    return deliveries
