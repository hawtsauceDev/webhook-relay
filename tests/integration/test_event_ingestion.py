import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.integration.conftest import BrokerDownTask, FakeTask
from webhook_relay.enums import DeliveryStatus
from webhook_relay.models.delivery import Delivery
from webhook_relay.models.event import Event
from webhook_relay.models.subscription import Subscription

EVENT = {"event_type": "order.created", "payload": {"order_id": 1}}


def make_subscription(
    db: Session,
    url_suffix: str,
    event_type: str = "order.created",
    active: bool = True,
) -> Subscription:
    # Each (target_url, event_type) pair must be unique, so the suffix
    # keeps several subscriptions for one event_type from colliding.
    sub = Subscription(
        target_url=f"https://example.com/hook/{url_suffix}",
        event_type=event_type,
        active=active,
    )
    db.add(sub)
    db.commit()
    return sub


def count_rows(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_event_fans_out_to_every_active_matching_subscription(
    client: TestClient, db_session: Session, fake_process_delivery: FakeTask
) -> None:
    subs = [make_subscription(db_session, str(n)) for n in range(3)]

    response = client.post("/events", json=EVENT)

    assert response.status_code == 201
    delivery_ids = response.json()["delivery_ids"]
    assert len(delivery_ids) == 3

    deliveries = db_session.scalars(select(Delivery)).all()
    assert len(deliveries) == 3
    assert {d.status for d in deliveries} == {DeliveryStatus.PENDING}
    assert {d.subscription_id for d in deliveries} == {s.id for s in subs}
    # One enqueue per delivery, with the right ids.
    assert sorted(args[0] for args in fake_process_delivery.calls) == sorted(
        delivery_ids
    )


def test_inactive_and_non_matching_subscriptions_get_no_delivery(
    client: TestClient, db_session: Session, fake_process_delivery: FakeTask
) -> None:
    matching = make_subscription(db_session, "active")
    make_subscription(db_session, "inactive", active=False)
    make_subscription(db_session, "other", event_type="user.deleted")

    response = client.post("/events", json=EVENT)

    assert response.status_code == 201
    deliveries = db_session.scalars(select(Delivery)).all()
    assert [d.subscription_id for d in deliveries] == [matching.id]
    assert len(fake_process_delivery.calls) == 1


def test_event_with_no_matching_subscriptions_is_still_stored(
    client: TestClient, db_session: Session, fake_process_delivery: FakeTask
) -> None:
    response = client.post("/events", json=EVENT)

    assert response.status_code == 201
    assert response.json()["delivery_ids"] == []
    assert count_rows(db_session, Event) == 1
    assert count_rows(db_session, Delivery) == 0
    assert fake_process_delivery.calls == []


def test_enqueue_failure_still_returns_201_and_keeps_rows(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_subscription(db_session, "a")
    # Overrides the autouse fake: a later setattr wins.
    monkeypatch.setattr(
        "webhook_relay.services.events.process_delivery", BrokerDownTask()
    )

    response = client.post("/events", json=EVENT)

    assert response.status_code == 201
    assert count_rows(db_session, Event) == 1
    deliveries = db_session.scalars(select(Delivery)).all()
    assert [d.status for d in deliveries] == [DeliveryStatus.PENDING]


def test_duplicate_subscription_returns_409_with_existing_id(
    client: TestClient, db_session: Session
) -> None:
    body = {"target_url": "https://example.com/hook", "event_type": "order.created"}

    first = client.post("/subscriptions", json=body)
    second = client.post("/subscriptions", json=body)

    assert first.status_code == 201
    assert second.status_code == 409
    # ASSUMPTION: the 409 body names the existing id under "subscription_id".
    assert second.json()["detail"]["subscription_id"] == first.json()["id"]
    assert count_rows(db_session, Subscription) == 1
