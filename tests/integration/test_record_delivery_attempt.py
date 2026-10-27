import logging

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.integration.helpers import SECRET_URL, make_delivery, reload
from webhook_relay.database import engine
from webhook_relay.enums import DeliveryStatus
from webhook_relay.exceptions import DeliveryAttemptRecordingError
from webhook_relay.services.deliveries import record_delivery_attempt


def committed_state(delivery_id: int) -> tuple[str, int, int]:
    """Read status, attempt_count and attempt rows through a fresh connection."""
    with engine.connect() as conn:
        status, count = conn.execute(
            text("SELECT status, attempt_count FROM deliveries WHERE id = :id"),
            {"id": delivery_id},
        ).one()
        attempts = conn.execute(
            text("SELECT count(*) FROM delivery_attempts WHERE delivery_id = :id"),
            {"id": delivery_id},
        ).scalar_one()
    return status, count, attempts


def test_one_call_commits_status_count_and_attempt_together(db_session: Session) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id

    record_delivery_attempt(
        db_session, delivery, DeliveryStatus.FAILED, response_status=503
    )

    assert committed_state(delivery_id) == (DeliveryStatus.FAILED, 1, 1)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT response_status, error FROM delivery_attempts WHERE delivery_id = :id"),
            {"id": delivery_id},
        ).one()
    assert row.response_status == 503
    assert row.error is None


def test_attempt_count_increases_by_exactly_one_per_call(db_session: Session) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id

    for _ in range(3):
        record_delivery_attempt(
            db_session, delivery, DeliveryStatus.PENDING, error_label="ReadTimeout"
        )

    assert committed_state(delivery_id) == (DeliveryStatus.PENDING, 3, 3)
    assert reload(db_session, delivery).attempt_count == 3


def test_failed_write_rolls_back_everything_and_leaks_nothing(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    too_big = 2**40  # does not fit an INTEGER column, so Postgres rejects the insert

    with caplog.at_level(logging.INFO), pytest.raises(DeliveryAttemptRecordingError):
        record_delivery_attempt(
            db_session, delivery, DeliveryStatus.SUCCESS, response_status=too_big
        )

    # Nothing was half-written: status and count are untouched, no attempt row.
    assert committed_state(delivery_id) == (DeliveryStatus.PENDING, 0, 0)
    # Only metadata was logged: not the parameter value, not the secret.
    assert "error_type=DataError" in caplog.text
    assert str(too_big) not in caplog.text
    assert "token-abc123" not in caplog.text