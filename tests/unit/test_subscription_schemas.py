import pytest
from pydantic import ValidationError

from webhook_relay.schemas.subscription import SubscriptionCreate, SubscriptionUpdate

VALID = {"target_url": "https://exmaple.com/hook", "event_type": "order.created"}


def test_create_accepts_valid_input() -> None:
    sub = SubscriptionCreate.model_validate(VALID)
    # HttpUrl is a URL object, not a str, so compare its string form
    assert str(sub.target_url) == "https://exmaple.com/hook"
    assert sub.event_type == "order.created"


def test_create_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SubscriptionCreate.model_validate({**VALID, "is_admin": True})
    errors = exc_info.value.errors()
    assert len(errors)
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("is_admin",)


def test_create_typo_is_reported_as_missing_and_extra() -> None:
    # The real-world reason for extra="forbid": a misspelled field name.
    bad = {"targt_url": "https://exmaple.com/hook", "event_type": "order.created"}
    with pytest.raises(ValidationError) as exc_info:
        SubscriptionCreate.model_validate(bad)
    assert {e["type"] for e in exc_info.value.errors()} == {
        "missing",
        "extra_forbidden",
    }


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("https://example.com/hook", id="https"),
        pytest.param("http://example.com/hook", id="http"),
        pytest.param("https://example.com:8443/hook", id="custom-port"),
        pytest.param("https://example.com/hook?token=abc", id="query-string"),
    ],
)
def test_target_url_accepts(url: str) -> None:
    SubscriptionCreate.model_validate({**VALID, "target_url": url})


@pytest.mark.parametrize(
    ("url", "error_type"),
    [
        pytest.param("example.com/hook", "url_parsing", id="no-scheme"),
        pytest.param("ftp://example.com/file", "url_scheme", id="wrong-scheme"),
        pytest.param("javascript:alert(1)", "url_scheme", id="javascript-scheme"),
        pytest.param("https://", "url_parsing", id="no-host"),
        pytest.param("", "url_parsing", id="empty"),
        pytest.param(
            "https://example.com/" + "a" * 2100, "url_too_long", id="too-long"
        ),
        pytest.param(123, "url_type", id="not-a-string"),
    ],
)
def test_target_url_rejects(url: object, error_type: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        SubscriptionCreate.model_validate({**VALID, "target_url": url})
    assert exc_info.value.errors()[0]["type"] == error_type


@pytest.mark.parametrize("value", [True, False])
def test_update_accepts_real_booleans(value: bool) -> None:
    assert SubscriptionUpdate.model_validate({"active": value}).active is value


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("true", id="string-true"),
        pytest.param("false", id="string-false"),
        pytest.param(1, id="int-one"),
        pytest.param(0, id="int-zero"),
        pytest.param(None, id="none"),
    ],
)
def test_update_rejects_non_booleans(value: object) -> None:
    with pytest.raises(ValidationError) as exc_info:
        SubscriptionUpdate.model_validate({"active": value})
    assert exc_info.value.errors()[0]["type"] == "bool_type"


def test_update_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SubscriptionUpdate.model_validate({"active": True, "is_admin": True})
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"
