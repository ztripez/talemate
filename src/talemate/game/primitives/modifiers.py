"""Roll modifier models for Game Primitives selection sources."""

from __future__ import annotations

import pydantic

from talemate.game.primitives.conditions import PrimitiveConditionGroup


class RollModifier(pydantic.BaseModel):
    """Conditional numeric modifier applied to roll table totals.

    Attributes:
        id: Stable modifier identifier.
        label: Optional display label for debug traces.
        applies_to: Roll table definition id or primitive reference this modifier
            targets.
        when: Primitive-aware condition groups that must match for activation.
        add: Numeric value added to the raw roll total when active.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    applies_to: str = pydantic.Field(min_length=1)
    when: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)
    add: pydantic.StrictInt | pydantic.StrictFloat = 0
