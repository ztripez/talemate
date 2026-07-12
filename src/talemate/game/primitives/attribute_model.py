"""Persisted primitive attribute payload contract."""

from typing import Literal

import pydantic

from talemate.game.primitives.attribute_sources import validated_options
from talemate.game.primitives.conditions import PrimitiveConditionGroup
from talemate.game.primitives.render import RenderPolicy

AttributeSourceKind = Literal[
    "literal",
    "deck",
    "roll_table",
    "meter",
    "clock",
    "relationship",
    "modifier",
    "state_ref",
]


class AttributeSource(pydantic.BaseModel):
    """Persist one deterministic source for an anchored attribute."""

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    source: AttributeSourceKind
    render_policy: RenderPolicy = "hidden"
    value: pydantic.JsonValue | None = None
    ref: str | None = None
    options: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    conditions: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def validate_source_contract(self) -> "AttributeSource":
        """Enforce source-specific value, reference, and option constraints."""
        if self.source == "literal":
            if self.ref is not None:
                raise ValueError("Literal attribute sources cannot define ref")
            if "value" not in self.model_fields_set:
                raise ValueError("Literal attribute sources require explicit value")
            self.options = validated_options(self)
            return self
        if "value" in self.model_fields_set and self.value is not None:
            raise ValueError("Non-literal attribute sources cannot define value")
        if not self.ref or not self.ref.strip():
            raise ValueError(f"Attribute source '{self.source}' requires ref")
        self.options = validated_options(self)
        return self
