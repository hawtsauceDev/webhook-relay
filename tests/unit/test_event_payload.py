import pytest
from typing import Any
from pydantic import TypeAdapter, ValidationError

from webhook_relay.schemas.types import EventPayload

payload_adapter = TypeAdapter(EventPayload)

@pytest.mark.parametrize(
    "payload", 
    [
        pytest.param({}, id="empty-object"),
        pytest.param({"order_id": 1, "tags": ["a", "b"]}, id="simple"),
        pytest.param({"a": {"b": {"c": [1, 2.5, None, True]}}}, id="deeply-nested"),
        pytest.param({"nombre": "ñandú"}, id="unicode"),
    ],
)
def test_payload_accepts_valid_objects(payload: dict[str, Any]) -> None:
    assert payload_adapter.validate_python(payload) == payload


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(["a", "b"], id="list"),
        pytest.param("text", id="string"),
        pytest.param(1, id="number"),
        pytest.param(None, id="none"),
        pytest.param({"x": float("nan")}, id="nan-value"),
        pytest.param({"x": float("inf")}, id="infinity-value"),
        pytest.param({"x": float("-inf")}, id="negative-infinity"),
        pytest.param({"x": [1, float("nan")]}, id="nan-inside-list"),
        pytest.param({"x": {"y": float("inf")}}, id="infinity-nested"),
        pytest.param({"x": "a\x00b"}, id="nul-in-value"),
        pytest.param({"a\x00b": 1}, id="nul-in-key"),
        pytest.param({"x": ["ok", {"y": "a\x00b"}]}, id="nul-nested"),
    ]
)
def test_payload_rejects(payload: object) -> None:
    with pytest.raises(ValidationError) as exc_info:
        payload_adapter.validate_python(payload)
    # First run: print the real error types, then replace this with an
    # assertion on them, like event_type.
    print([e["type"] for e in exc_info.value.errors()])
    assert exc_info.value.errors()