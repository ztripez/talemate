"""Shared selection result models for Game Primitives."""

from __future__ import annotations

import pydantic

from talemate.game.primitives.effects import Effect


class SelectionResult(pydantic.BaseModel):
    """Common result emitted by primitive selection sources.

    Attributes:
        source_type: Selection source category, such as ``"roll_table"``.
        source_id: Definition id or primitive reference resolved for the source.
        anchor: Optional anchor reference associated with the selection.
        result_id: Optional selected row or item id.
        label: Optional display label for the selected result.
        text: Optional narrative text for the selected result.
        effects: Effects attached to the selected result.
        variables: JSON-compatible variables attached to the selected result.
        debug: JSON-compatible trace data explaining selection resolution.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    source_type: str
    source_id: str
    anchor: str | None = None
    result_id: str | None = None
    label: str | None = None
    text: str | None = None
    effects: list[Effect] = pydantic.Field(default_factory=list)
    variables: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    debug: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
