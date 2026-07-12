"""Canonical primitive instance payload models."""

from __future__ import annotations

import pydantic

from talemate.game.primitives.anchors import PrimitiveRef
from talemate.game.primitives.constants import (
    EDITABLE_PRIMITIVE_KINDS,
    PRIMITIVE_KINDS,
    TYPED_PRIMITIVE_KINDS,
    EditablePrimitiveKind,
    PrimitiveKind,
)


class PrimitivePayload(pydantic.RootModel[dict[str, pydantic.JsonValue]]):
    """Validate a generic JSON object stored for one primitive instance.

    Attributes:
        root: String-keyed object containing only JSON-compatible values.

    Invariants:
        Non-finite numbers are rejected and nested model instances are always
        revalidated.

    """

    model_config = pydantic.ConfigDict(
        allow_inf_nan=False, revalidate_instances="always"
    )


class RollTableInstancePayload(pydantic.BaseModel):
    """Persist the reusable definition selected by a roll-table instance.

    Attributes:
        definition: Non-empty canonical roll-table definition identifier.

    Invariants:
        The identifier satisfies primitive path-segment rules. Unknown fields and
        non-finite numbers are rejected, and whitespace is stripped.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
        revalidate_instances="always",
    )

    definition: str = pydantic.Field(min_length=1)

    @pydantic.field_validator("definition")
    @classmethod
    def validate_definition_id(cls, value: str) -> str:
        """Normalize and validate the referenced definition identifier.

        Args:
            value: Strict string identifier supplied for validation.

        Returns:
            Canonical path-segment identifier.

        Raises:
            ValueError: If ``value`` is not a valid path segment.

        """
        return PrimitiveRef.validate_path_segment(value)


__all__ = [
    "EDITABLE_PRIMITIVE_KINDS",
    "PRIMITIVE_KINDS",
    "TYPED_PRIMITIVE_KINDS",
    "EditablePrimitiveKind",
    "PrimitiveKind",
    "PrimitivePayload",
    "RollTableInstancePayload",
]
