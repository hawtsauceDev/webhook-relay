from collections.abc import Iterator
from typing import Any

import pytest
from alembic.config import Config
from kombu.exceptions import OperationalError
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from alembic import command
from webhook_relay.database import SessionLocal, engine
from webhook_relay.main import app
from webhook_relay.models.base import Base


def _assert_test_database() -> None:
    # Read name from the live engine, not from a typed string
    host = engine.url.host or ""
    name = engine.url.database or ""
    if not name.endswith("_test") and host != "localhost":
        pytest.exit(
            f"Refusing to run: {name!r} is not a test database or {host!r} is not localhost",
            returncode=2,
        )


@pytest.fixture(scope="session", autouse=True)
def migrated_schema() -> None:
    _assert_test_database()
    # Alembic's env.py reads the URL via get_settings(), which sees the
    # test URL because we set the env var before importing anything.
    command.upgrade(Config("alembic.ini"), "head")  # no-op if already at head.


@pytest.fixture(autouse=True)
def clean_tables(migrated_schema: None) -> None:
    # Depending on migrated_schema guarantees the tables exist first.
    _assert_test_database()  # Truncating is destructive a guard is needed.
    # Table names come from our own metadata, never from user input.
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:  # begin() commits when the block exits
        conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()  # releases connection and any open transaction


@pytest.fixture
def client() -> Iterator[TestClient]:
    # 'with' runs the app's startup/shutdown events.
    with TestClient(app) as test_client:
        yield test_client


class FakeTask:
    """Stands in for a Celery task: records calls instead of using a broker."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def delay(self, *args: Any) -> None:
        self.calls.append(args)


class BrokerDownTask:
    """Stands in for a task whose broker is unreachable."""

    def delay(self, *args: Any) -> None:
        raise OperationalError("broker is down")


@pytest.fixture(autouse=True)
def fake_process_delivery(monkeypatch: pytest.MonkeyPatch) -> FakeTask:
    fake = FakeTask()
    monkeypatch.setattr("webhook_relay.services.events.process_delivery", fake)
    return fake
