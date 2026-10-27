import logging
from collections.abc import Callable
from typing import Any, NoReturn

import httpx
import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.integration.helpers import (
    SECRET_URL,
    attempts_for,
    make_delivery,
    reload,
)
from webhook_relay.database import engine
from webhook_relay.enums import DeliveryStatus
from webhook_relay.exceptions import DeliveryAttemptRecordingError
from webhook_relay.worker.tasks import (
    DELIVERY_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    process_delivery,
)

POST_PATH = "webhook_relay.worker.tasks.httpx.post"


class FakeResponse:
    """Same shape the task reads from a real httpx.Response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


class FakePost:
    """Stands in for httpx.post: records calls, then returns or raises."""

    def __init__(self, outcome: int | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeResponse(self.outcome)


class RetrySpy:
    """Stands in for task.retry: records its arguments, then raises Retry."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> NoReturn:
        self.calls.append(kwargs)
        raise Retry("retry requested")


@pytest.fixture
def install_post(monkeypatch: pytest.MonkeyPatch) -> Callable[[int | Exception], FakePost]:
    def _install(outcome: int | Exception) -> FakePost:
        fake = FakePost(outcome)
        monkeypatch.setattr(POST_PATH, fake)
        return fake

    return _install


def run_task(delivery_id: int, retries: int = 0) -> None:
    # Fake the request context a worker would provide, so that
    # self.request.retries has the value this test needs.
    process_delivery.push_request(retries=retries)
    try:
        process_delivery.run(delivery_id)
    finally:
        process_delivery.pop_request()


def test_success_posts_the_envelope_and_records_one_attempt(
    db_session: Session, install_post: Callable[[int | Exception], FakePost]
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    fake = install_post(200)

    run_task(delivery_id)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == SECRET_URL
    assert call["json"] == {
        "event_id": delivery.event_id,
        "event_type": "order.created",
        "payload": {"order_id": 1},
    }
    assert call["timeout"] == DELIVERY_TIMEOUT  # a missing timeout would hang forever

    reload(db_session, delivery)
    assert delivery.status == DeliveryStatus.SUCCESS
    assert delivery.attempt_count == 1
    attempts = attempts_for(db_session, delivery_id)
    assert len(attempts) == 1
    assert attempts[0].response_status == 200
    assert attempts[0].error is None


@pytest.mark.parametrize("status_code", [301, 400, 404, 500, 503])
def test_non_2xx_response_is_a_failed_attempt_and_retries(
    db_session: Session,
    install_post: Callable[[int | Exception], FakePost],
    status_code: int,
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    install_post(status_code)

    with pytest.raises(Retry):
        run_task(delivery_id)

    reload(db_session, delivery)
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempt_count == 1
    attempts = attempts_for(db_session, delivery_id)
    assert len(attempts) == 1
    assert attempts[0].response_status == status_code
    assert attempts[0].error is None


@pytest.mark.parametrize(
    ("error", "label"),
    [
        pytest.param(httpx.ConnectTimeout(SECRET_URL), "ConnectTimeout", id="connect-timeout"),
        pytest.param(httpx.ReadTimeout(SECRET_URL), "ReadTimeout", id="read-timeout"),
        pytest.param(httpx.ConnectError(SECRET_URL), "ConnectError", id="connect-error"),
        pytest.param(SoftTimeLimitExceeded(), "SoftTimeLimitExceeded", id="soft-limit"),
    ],
)
def test_transport_failure_records_only_the_class_name(
    db_session: Session,
    install_post: Callable[[int | Exception], FakePost],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
    label: str,
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    install_post(error)

    with caplog.at_level(logging.INFO), pytest.raises(Retry):
        run_task(delivery_id)

    attempts = attempts_for(db_session, delivery_id)
    assert len(attempts) == 1
    assert attempts[0].response_status is None
    assert attempts[0].error == label
    # The exception MESSAGE contained the secret URL; it must not leak.
    assert "token-abc123" not in caplog.text
    assert reload(db_session, delivery).status == DeliveryStatus.PENDING


@pytest.mark.parametrize(
    ("retries", "expected_status", "retry_expected"),
    [
        pytest.param(0, DeliveryStatus.PENDING, True, id="first-attempt"),
        pytest.param(MAX_RETRIES - 1, DeliveryStatus.PENDING, True, id="last-retry-scheduled"),
        pytest.param(MAX_RETRIES, DeliveryStatus.FAILED, False, id="final-attempt"),
    ],
)
def test_status_after_a_failed_attempt_depends_on_retries_used(
    db_session: Session,
    install_post: Callable[[int | Exception], FakePost],
    retries: int,
    expected_status: DeliveryStatus,
    retry_expected: bool,
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    install_post(500)

    if retry_expected:
        with pytest.raises(Retry):
            run_task(delivery_id, retries=retries)
    else:
        run_task(delivery_id, retries=retries)

    assert reload(db_session, delivery).status == expected_status
    assert len(attempts_for(db_session, delivery_id)) == 1


def test_permanently_failing_target_gets_four_attempts_then_failed(
    db_session: Session, install_post: Callable[[int | Exception], FakePost]
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    fake = install_post(500)

    for retries in range(MAX_RETRIES + 1):
        if retries < MAX_RETRIES:
            with pytest.raises(Retry):
                run_task(delivery_id, retries=retries)
        else:
            run_task(delivery_id, retries=retries)

    assert len(fake.calls) == MAX_RETRIES + 1
    reload(db_session, delivery)
    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.attempt_count == MAX_RETRIES + 1
    attempts = attempts_for(db_session, delivery_id)
    assert len(attempts) == MAX_RETRIES + 1
    assert all(a.response_status == 500 for a in attempts)


def test_retry_uses_the_fixed_delay(
    db_session: Session,
    install_post: Callable[[int | Exception], FakePost],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivery = make_delivery(db_session)
    install_post(500)
    spy = RetrySpy()
    monkeypatch.setattr(process_delivery, "retry", spy)

    with pytest.raises(Retry):
        run_task(delivery.id)

    assert spy.calls == [{"countdown": RETRY_DELAY_SECONDS}]


@pytest.mark.parametrize("status", [DeliveryStatus.SUCCESS, DeliveryStatus.SKIPPED])
def test_terminal_deliveries_are_not_reprocessed(
    db_session: Session,
    install_post: Callable[[int | Exception], FakePost],
    status: DeliveryStatus,
) -> None:
    delivery = make_delivery(db_session, status=status)
    delivery_id = delivery.id
    fake = install_post(200)

    run_task(delivery_id)

    assert fake.calls == []
    reload(db_session, delivery)
    assert delivery.status == status
    assert delivery.attempt_count == 0
    assert attempts_for(db_session, delivery_id) == []


def test_missing_delivery_is_logged_and_ignored(
    install_post: Callable[[int | Exception], FakePost],
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = install_post(200)

    with caplog.at_level(logging.WARNING):
        run_task(999_999)

    assert fake.calls == []
    assert "not found" in caplog.text


def test_inactive_subscription_is_skipped_without_posting(
    db_session: Session, install_post: Callable[[int | Exception], FakePost]
) -> None:
    delivery = make_delivery(db_session, active=False)
    delivery_id = delivery.id
    fake = install_post(200)

    run_task(delivery_id)

    assert fake.calls == []
    reload(db_session, delivery)
    assert delivery.status == DeliveryStatus.SKIPPED
    assert delivery.attempt_count == 0
    assert attempts_for(db_session, delivery_id) == []


def test_processing_is_committed_before_the_post(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    seen: list[str] = []

    def spy_post(url: str, **kwargs: Any) -> FakeResponse:
        # A brand-new connection can only see COMMITTED data.
        with engine.connect() as conn:
            seen.append(
                conn.execute(
                    text("SELECT status FROM deliveries WHERE id = :id"),
                    {"id": delivery_id},
                ).scalar_one()
            )
        return FakeResponse(200)

    monkeypatch.setattr(POST_PATH, spy_post)

    run_task(delivery_id)

    assert seen == [DeliveryStatus.PROCESSING]


def test_recording_failure_asks_celery_to_retry_the_whole_task(
    db_session: Session,
    install_post: Callable[[int | Exception], FakePost],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivery = make_delivery(db_session)
    delivery_id = delivery.id
    fake = install_post(200)

    def failing_record(*args: Any, **kwargs: Any) -> None:
        raise DeliveryAttemptRecordingError

    monkeypatch.setattr("webhook_relay.worker.tasks.record_delivery_attempt", failing_record)
    spy = RetrySpy()
    monkeypatch.setattr(process_delivery, "retry", spy)

    with pytest.raises(Retry):
        run_task(delivery_id)

    assert len(fake.calls) == 1  # the POST already happened: duplicates accepted (PIPE-3)
    assert len(spy.calls) == 1
    assert spy.calls[0]["countdown"] == RETRY_DELAY_SECONDS
    assert isinstance(spy.calls[0]["exc"], DeliveryAttemptRecordingError)
    # The row stays "processing": the stuck-delivery limitation (PIPE-2).
    assert reload(db_session, delivery).status == DeliveryStatus.PROCESSING