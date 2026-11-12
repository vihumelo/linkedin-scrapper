"""Tests for validation of decoded JSON values."""

import pytest

from app.core.json_types import normalize_json_value


def test_normalizes_nested_json_containers() -> None:
    """Preserves supported JSON scalars inside nested objects and arrays."""

    payload = {"items": [1, True, None, {"name": "Vaga"}]}

    assert normalize_json_value(payload) == payload


def test_rejects_non_string_object_keys() -> None:
    """Rejects mappings that cannot be represented as JSON objects."""

    with pytest.raises(ValueError, match="keys must be strings"):
        normalize_json_value({1: "invalid"})


def test_rejects_values_outside_the_json_data_model() -> None:
    """Rejects Python values that cannot be serialized as JSON."""

    with pytest.raises(ValueError, match="not a valid JSON value"):
        normalize_json_value({"items": {"not", "json"}})
