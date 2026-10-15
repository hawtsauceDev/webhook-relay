import math
from typing import Annotated, Any

from pydantic import BeforeValidator, StringConstraints, AfterValidator


def normalize_event_type(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


EventType = Annotated[
    str,
    BeforeValidator(normalize_event_type),
    StringConstraints(
        min_length=1,
        max_length=100,
        pattern="^[a-z0-9]+(?:[._-][a-z0-9]+)*$",
    ),
]


def _check_json_safe(node: Any) -> None:
    if isinstance(node, float):
        if not math.isfinite(node):
            raise ValueError("payload contains a non-finite number (NaN or Infinity)")
    elif isinstance(node, str):
        if "\x00" in node:
            raise ValueError("payload contains a NUL character (\\u0000)")
    elif isinstance(node, dict):
        for key, value in node.items():
            _check_json_safe(key)
            _check_json_safe(value)
    elif isinstance(node, list):
        for item in node:
            _check_json_safe(item)


def validate_payload(value: dict[str, Any]) -> dict[str, Any]:
    _check_json_safe(value)
    return value


EventPayload = Annotated[dict[str, Any], AfterValidator(validate_payload)]
