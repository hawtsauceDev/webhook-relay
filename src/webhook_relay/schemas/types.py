from typing import Annotated

from pydantic import BeforeValidator, StringConstraints


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
