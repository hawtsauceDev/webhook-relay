from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from webhook_relay.database import get_db
from webhook_relay.models.subscription import Subscription

DbSession = Annotated[Session, Depends(get_db)]


def get_subscription_or_404(
    subscription_id: Annotated[int, Path(ge=1)],
    db: DbSession,
) -> Subscription:
    subscription = db.scalar(
        select(Subscription).where(Subscription.id == subscription_id)
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    return subscription


SubscriptionDep = Annotated[Subscription, Depends(get_subscription_or_404)]
