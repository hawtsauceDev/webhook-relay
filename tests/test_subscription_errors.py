import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from webhook_relay.database import get_db
from webhook_relay.main import app
from webhook_relay.models.subscription import (
    SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT,
)
from webhook_relay.routers import subscriptions as subscriptions_router

SECRET_URL = "https://hooks.example.com/services/SECRET123?token=abc"
BODY = {"target_url": SECRET_URL, "event_type": "order.created"}


@pytest.fixture
def fake_db():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    # Not used as a context manager, so the lifespan does not run.
    # raise_server_exceptions defaults to True: an unhandled error such as
    # UnboundLocalError fails the test instead of becoming a quiet 500.
    return TestClient(app)


def make_integrity_error(orig):
    return IntegrityError("INSERT ...", {}, orig)


def test_unexpected_error_returns_generic_500(client, fake_db, caplog):
    orig = psycopg.errors.NotNullViolation(f"DETAIL: Key=({SECRET_URL})")
    fake_db.commit.side_effect = make_integrity_error(orig)

    with caplog.at_level(logging.INFO):
        response = client.post("/subscriptions", json=BODY)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "sqlstate=23502" in caplog.text
    assert "SECRET123" not in caplog.text
    assert "SECRET123" not in response.text
    fake_db.rollback.assert_called_once()


def test_unique_violation_on_other_constraint_is_500(client, fake_db, monkeypatch):
    fake_db.commit.side_effect = make_integrity_error(
        psycopg.errors.UniqueViolation("duplicate")
    )
    monkeypatch.setattr(
        subscriptions_router,
        "get_db_error_details",
        lambda error: ("23505", "some_other_constraint"),
    )

    response = client.post("/subscriptions", json=BODY)

    assert response.status_code == 500


def test_duplicate_returns_409_with_existing_id(client, fake_db, monkeypatch):
    fake_db.commit.side_effect = make_integrity_error(
        psycopg.errors.UniqueViolation("duplicate")
    )
    monkeypatch.setattr(
        subscriptions_router,
        "get_db_error_details",
        lambda error: ("23505", SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT),
    )
    fake_db.scalar.return_value = SimpleNamespace(id=42)

    response = client.post("/subscriptions", json=BODY)

    assert response.status_code == 409
    assert response.json()["detail"]["subscription_id"] == 42


def test_duplicate_but_row_missing_returns_409_without_id(client, fake_db, monkeypatch):
    fake_db.commit.side_effect = make_integrity_error(
        psycopg.errors.UniqueViolation("duplicate")
    )
    monkeypatch.setattr(
        subscriptions_router,
        "get_db_error_details",
        lambda error: ("23505", SUBSCRIPTION_TARGET_EVENT_UNIQUE_CONSTRAINT),
    )
    fake_db.scalar.return_value = None

    response = client.post("/subscriptions", json=BODY)

    assert response.status_code == 409
    assert response.json()["detail"]["subscription_id"] is None


def test_get_db_error_details_for_non_psycopg_errors():
    assert subscriptions_router.get_db_error_details(ValueError("x")) == (None, None)
    assert subscriptions_router.get_db_error_details(None) == (None, None)


def test_get_db_error_details_for_psycopg_error():
    sqlstate, constraint = subscriptions_router.get_db_error_details(
        psycopg.errors.NotNullViolation("x")
    )
    assert sqlstate == "23502"
    assert constraint is None
