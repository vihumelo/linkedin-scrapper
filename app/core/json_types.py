"""Types and validation helpers for values decoded from JSON."""

from typing import cast

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


def normalize_json_value(value: object) -> JSONValue:
    """Validates and converts a decoded JSON value into a recursively typed value."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        items = cast(list[object], value)
        return [normalize_json_value(item) for item in items]
    if isinstance(value, dict):
        normalized: dict[str, JSONValue] = {}
        entries = cast(dict[object, object], value)
        for key, item in entries.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings.")
            normalized[key] = normalize_json_value(item)
        return normalized
    raise ValueError("Value is not a valid JSON value.")
