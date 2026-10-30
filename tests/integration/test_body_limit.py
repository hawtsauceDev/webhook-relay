from fastapi.testclient import TestClient

from webhook_relay.config import get_settings


def test_oversized_request_body_is_rejected_with_413(client: TestClient) -> None:
    max_body_size = get_settings().payload_max_body_size
    assert max_body_size is not None, "payload_max_body_size must be set for this test"

    oversized_payload = {"event_type": "order.created", "payload": {"data": "a" * max_body_size}}

    response = client.post("/events", json=oversized_payload)

    assert response.status_code == 413
