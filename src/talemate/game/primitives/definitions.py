"""Reusable meter and clock definitions for Game Primitives."""

from __future__ import annotations

import math

import pydantic

from talemate.game.primitives.anchors import PrimitiveRef
from talemate.game.primitives.constants import (
    DEFINITION_KINDS,
    EDITABLE_DEFINITION_KINDS,
    TYPED_DEFINITION_KINDS,
    DefinitionKind,
    EditableDefinitionKind,
)
from talemate.game.primitives.render import RenderPolicy


class MeterPayload(pydantic.BaseModel):
    """Represent a canonical bounded numeric meter definition or instance."""

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )
    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    min: pydantic.StrictInt | pydantic.StrictFloat
    max: pydantic.StrictInt | pydantic.StrictFloat
    value: pydantic.StrictInt | pydantic.StrictFloat
    render_policy: RenderPolicy = "hidden"

    @pydantic.model_validator(mode="after")
    def validate_bounds(self) -> "MeterPayload":
        """Validate the identifier and finite inclusive numeric bounds."""
        for value in (self.min, self.max, self.value):
            if not math.isfinite(float(value)):
                raise ValueError("Meter values must be finite")
        if self.min > self.max:
            raise ValueError("Meter min cannot exceed max")
        if not self.min <= self.value <= self.max:
            raise ValueError("Meter value must be within min and max")
        self.id = PrimitiveRef.validate_path_segment(self.id)
        return self


class ClockPayload(pydantic.BaseModel):
    """Represent a canonical bounded integer progress clock."""

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    max: pydantic.StrictInt = pydantic.Field(gt=0)
    value: pydantic.StrictInt = pydantic.Field(default=0, ge=0)
    render_policy: RenderPolicy = "summary"

    @pydantic.model_validator(mode="after")
    def validate_bounds(self) -> "ClockPayload":
        """Validate the identifier and bounded clock progress."""
        self.id = PrimitiveRef.validate_path_segment(self.id)
        if self.value > self.max:
            raise ValueError("Clock value cannot exceed max")
        return self


__all__ = [
    "ClockPayload",
    "DEFINITION_KINDS",
    "EDITABLE_DEFINITION_KINDS",
    "DefinitionKind",
    "EditableDefinitionKind",
    "MeterPayload",
    "TYPED_DEFINITION_KINDS",
]
