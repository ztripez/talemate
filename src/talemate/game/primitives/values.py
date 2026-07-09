"""Shared primitive payload value helpers."""

from __future__ import annotations

import copy
from typing import Any


def primitive_payload_value(payload: Any) -> Any:
    """Return the conventional scalar value from a primitive payload."""
    if isinstance(payload, dict) and "value" in payload:
        return copy.deepcopy(payload["value"])
    return copy.deepcopy(payload)


def primitive_value_payload(value: Any) -> dict[str, Any]:
    """Wrap a scalar value as a primitive JSON object payload."""
    if isinstance(value, dict):
        return copy.deepcopy(value)
    return {"value": copy.deepcopy(value)}
