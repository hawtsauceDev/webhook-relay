import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from webhook_relay.models.subscription import Subscription
from webhook_relay.routers.subscriptions import (
    SUBSCRIPTION_CONFLICT_MESSAGE_NONE,
    SUBSCRIPTION_CREATE_FAILED_MESSAGE,
)


def count_rows(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_non_duplicate_unique_violation_returns_500_without_leaking(
    client: TestClient, db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # Seed a row with an explicit id. The cleanup fixture reset the id
    # sequence, so the next generated id will also be 1: a primary key
    # collision, which is a unique violation on a DIFFERENT constraint.
    db_session.add(
        Subscription(
            id=1,
            target_url="https://example.com/seeded",
            event_type="order.created",
            active=True,
        )
    )
    db_session.commit()

    secret_url = "https://hooks.example.com/token-abc123"
    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/subscriptions",
            json={"target_url": secret_url, "event_type": "order.created"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": SUBSCRIPTION_CREATE_FAILED_MESSAGE}
    assert "token-abc123" not in response.text
    assert count_rows(db_session, Subscription) == 1  # only the seeded row

    # The service took the generic error branch, not the duplicate branch.
    assert "Unexpected database error while creating subscription" in caplog.text
    assert "sqlstate=23505" in caplog.text
    assert "already exists" not in caplog.text
    assert "token-abc123" not in caplog.text


def test_duplicate_with_unretrievable_existing_id_returns_409_with_null_id(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {"target_url": "https://example.com/hook", "event_type": "order.created"}
    assert client.post("/subscriptions", json=body).status_code == 201

    # Simulate the re-read of the existing id failing. Patched in the
    # service module, because create_subscription looks the name up there.
    def no_id(db: Session, target_url: str, event_type: str) -> None:
        return None

    monkeypatch.setattr(
        "webhook_relay.services.subscriptions._find_existing_subscription_id", no_id
    )

    response = client.post("/subscriptions", json=body)

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": SUBSCRIPTION_CONFLICT_MESSAGE_NONE,
        "subscription_id": None,
    }
    assert count_rows(db_session, Subscription) == 1