"""Ledger entries for deterministic Game Primitives operations."""

from __future__ import annotations

import uuid

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef


class LedgerEntry(pydantic.BaseModel):
    """JSON-serializable audit record for one primitive runtime operation.

    Ledger entries record deterministic runtime operations in a form that can be
    stored in scene JSON without custom encoders.

    Attributes:
        id: Unique ledger entry identifier generated as a UUID string by
            default.
        op: Non-empty operation name, such as ``primitive.set``.
        ref: Optional primitive reference string affected by the operation.
        anchor: Optional anchor reference string affected by the operation.
        input: JSON-compatible operation input payload.
        output: JSON-compatible operation result payload.
        message: Optional human-readable operation note.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )

    id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
    op: str = pydantic.Field(min_length=1)
    ref: str | None = None
    anchor: str | None = None
    input: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    output: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    message: str | None = None

    @pydantic.field_validator("ref")
    @classmethod
    def validate_ref(cls, value: str | None) -> str | None:
        """Validate and normalize an optional primitive reference string.

        Args:
            value: Primitive reference string or ``None``.

        Returns:
            Canonical primitive reference string, or ``None``.

        Raises:
            ValueError: If ``value`` is not a valid primitive reference.
        """
        if value is None:
            return None
        return PrimitiveRef.model_validate(value).key()

    @pydantic.field_validator("anchor")
    @classmethod
    def validate_anchor(cls, value: str | None) -> str | None:
        """Validate and normalize an optional anchor reference string.

        Args:
            value: Anchor reference string or ``None``.

        Returns:
            Canonical anchor reference string, or ``None``.

        Raises:
            ValueError: If ``value`` is not a valid anchor reference.
        """
        if value is None:
            return None
        return AnchorRef.model_validate(value).key()

    @pydantic.field_validator("op")
    @classmethod
    def validate_op(cls, value: str) -> str:
        """Validate and normalize the operation name.

        Args:
            value: Operation name such as ``primitive.set``.

        Returns:
            The stripped operation name.

        Raises:
            ValueError: If the operation name is empty after trimming.
        """
        value = value.strip()
        if not value:
            raise ValueError("Ledger operation cannot be empty")
        return value
