import pytest
from pydantic import TypeAdapter, ValidationError

from webhook_relay.schemas.types import EventType

# EventType is an Annotated type not a model, so it needs TypeAdapter
# to be validadted on its own. Built once and reused by every test below.
event_type_adapter = TypeAdapter(EventType)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("order.created", "order.created", id="already valid"),
        pytest.param("   Order.Created   ", "order.created", id="strip-and-lowercase"),
        pytest.param("a", "a", id="shortest-allowed"),
        pytest.param("a" * 100, "a" * 100, id="longest-allowed"),
        pytest.param(" " + "a" * 100 + " ", "a" * 100, id="longest-after-strip"),
        pytest.param("user-signed_up.v2", "user-signed_up.v2", id="mixed-separators"),
    ],
)
def test_event_type_accepts_and_normalizes(raw: str, expected: str) -> None:
    assert event_type_adapter.validate_python(raw) == expected


@pytest.mark.parametrize(
    ("raw", "error_type"),
    [
        pytest.param("", "too_short", id="empty"),
        pytest.param("   ", "too_short", id="only-whitespace"),
        pytest.param("a" * 101, "too_long", id="one-over-limit"),
        pytest.param(
            "order..created", "string_pattern_mismatch", id="double-separator"
        ),
        pytest.param(".order", "string_pattern_mismatch", id="leading-separator"),
        pytest.param("order.", "string_pattern_mismatch", id="trailing-separator"),
        pytest.param("order created", "string_pattern_mismatch", id="inner-space"),
        pytest.param("órden", "string_pattern_mismatch", id="non-ascii"),
        pytest.param(123, "string_type", id="not-a-string"),
    ],
)
def test_event_type_rejects(raw: object, error_type: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        event_type_adapter.validate_python(raw)
    # Check WHY it failed, not only that it failed.
    assert exc_info.value.errors()[0]["type"] == error_type
