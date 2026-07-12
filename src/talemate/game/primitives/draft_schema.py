"""Canonical draft lifecycle and intentional change-target models."""

from __future__ import annotations

from typing import Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.containers import (
    AnchorPayload,
    PrimitiveDefinitions,
    normalize_anchor_payloads,
)


class DraftValidation(pydantic.BaseModel):
    """Record the persisted validation outcome for one primitive draft.

    Attributes:
        ok: Whether validation found no blocking errors.
        errors: Blocking diagnostics that prevent commit.
        warnings: Non-blocking diagnostics retained for author review.

    Invariants:
        Values are strictly typed, unknown fields are rejected, and existing
        model instances are revalidated when nested.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )
    ok: bool = False
    errors: list[str] = pydantic.Field(default_factory=list)
    warnings: list[str] = pydantic.Field(default_factory=list)


class DraftDefinitionTarget(pydantic.BaseModel):
    """Identify one reusable definition intentionally replaced or deleted.

    Attributes:
        kind: Non-empty canonical definition collection segment.
        id: Non-empty canonical definition identifier segment.

    Invariants:
        Both segments satisfy primitive path-segment rules. Instances are frozen,
        strictly typed, whitespace-normalized, and reject unknown fields.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
        revalidate_instances="always",
    )
    kind: str = pydantic.Field(min_length=1)
    id: str = pydantic.Field(min_length=1)

    @pydantic.model_validator(mode="after")
    def validate_segments(self) -> "DraftDefinitionTarget":
        """Normalize and validate both definition path segments.

        Returns:
            The frozen target with canonical ``kind`` and ``id`` segments.

        Raises:
            ValueError: If either value is not a valid path segment.

        """
        object.__setattr__(self, "kind", PrimitiveRef.validate_path_segment(self.kind))
        object.__setattr__(self, "id", PrimitiveRef.validate_path_segment(self.id))
        return self


class DraftChangeTargets(pydantic.BaseModel):
    """Record committed resources intentionally replaced or deleted by a draft.

    Attributes:
        definitions: Unique reusable-definition targets.
        anchors: Unique canonical anchor references.
        primitives: Unique canonical primitive references.

    Invariants:
        Each collection contains no duplicate canonical target. Values are
        strictly typed, and unknown fields are rejected.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )
    definitions: list[DraftDefinitionTarget] = pydantic.Field(default_factory=list)
    anchors: list[str] = pydantic.Field(default_factory=list)
    primitives: list[str] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("anchors")
    @classmethod
    def validate_anchors(cls, values: list[str]) -> list[str]:
        """Canonicalize unique anchor references.

        Args:
            values: Strict string references supplied for validation.

        Returns:
            Canonical references in input order.

        Raises:
            ValueError: If a reference is invalid or canonical values duplicate.

        """
        return _canonical_unique(values, lambda value: AnchorRef.parse(value).key())

    @pydantic.field_validator("primitives")
    @classmethod
    def validate_primitives(cls, values: list[str]) -> list[str]:
        """Canonicalize unique primitive references.

        Args:
            values: Strict string references supplied for validation.

        Returns:
            Canonical references in input order.

        Raises:
            ValueError: If a reference is invalid or canonical values duplicate.

        """
        return _canonical_unique(values, lambda value: PrimitiveRef.parse(value).key())

    @pydantic.field_validator("definitions")
    @classmethod
    def validate_definitions(
        cls, values: list[DraftDefinitionTarget]
    ) -> list[DraftDefinitionTarget]:
        """Reject duplicate definition change targets.

        Args:
            values: Validated definition targets supplied for the change set.

        Returns:
            The original ordered target list.

        Raises:
            ValueError: If two targets have the same kind and identifier.

        """
        if len({(value.kind, value.id) for value in values}) != len(values):
            raise ValueError("Duplicate definition change target")
        return values


def _canonical_unique(values: list[str], canonicalize) -> list[str]:
    canonical = [canonicalize(value) for value in values]
    if len(set(canonical)) != len(canonical):
        raise ValueError("Duplicate draft change target")
    return canonical


class PrimitiveDraft(pydantic.BaseModel):
    """Stage isolated primitive definitions and anchors for validated commit.

    Attributes:
        id: Non-empty canonical draft identifier.
        status: Draft lifecycle state.
        created_by: Non-empty identifier of the authoring source.
        definitions: Reusable definitions staged by kind and identifier.
        anchors: Canonical anchor payloads staged by reference.
        replacements: Existing resources intentionally replaced on commit.
        deletions: Existing resources intentionally removed on commit.
        validation: Latest persisted validation result.

    Invariants:
        Replacement targets have corresponding staged values. A resource cannot
        be both staged and deleted. All identifiers are canonical, nested models
        are revalidated, and unknown fields are rejected.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        strict=True,
        str_strip_whitespace=True,
        revalidate_instances="always",
    )
    id: str = pydantic.Field(min_length=1)
    status: Literal["draft", "validated", "committed"] = "draft"
    created_by: str = pydantic.Field(default="llm", min_length=1)
    definitions: PrimitiveDefinitions = pydantic.Field(
        default_factory=PrimitiveDefinitions
    )
    anchors: dict[str, AnchorPayload] = pydantic.Field(default_factory=dict)
    replacements: DraftChangeTargets = pydantic.Field(
        default_factory=DraftChangeTargets
    )
    deletions: DraftChangeTargets = pydantic.Field(default_factory=DraftChangeTargets)
    validation: DraftValidation = pydantic.Field(default_factory=DraftValidation)

    @pydantic.field_validator("anchors")
    @classmethod
    def validate_anchor_keys(
        cls, value: dict[str, AnchorPayload]
    ) -> dict[str, AnchorPayload]:
        """Canonicalize draft anchor keys while retaining typed payloads."""
        return normalize_anchor_payloads(value)

    @pydantic.model_validator(mode="after")
    def validate_identity(self) -> "PrimitiveDraft":
        """Normalize identity and require coherent staged change targets.

        Returns:
            The validated draft with a canonical identifier.

        Raises:
            ValueError: If the identifier is invalid or replacement, deletion,
                and staged-value sets are inconsistent.

        """
        self.id = PrimitiveRef.validate_path_segment(self.id)
        definition_values = {
            (kind, definition_id)
            for kind, definitions in self.definitions.items()
            for definition_id in definitions
        }
        replacement_definitions = {
            (target.kind, target.id) for target in self.replacements.definitions
        }
        deleted_definitions = {
            (target.kind, target.id) for target in self.deletions.definitions
        }
        if not replacement_definitions <= definition_values:
            raise ValueError("Definition replacement target has no staged value")
        if definition_values & deleted_definitions:
            raise ValueError("Definition cannot be staged and deleted in one draft")
        if not set(self.replacements.anchors) <= set(self.anchors):
            raise ValueError("Anchor replacement target has no staged value")
        if set(self.anchors) & set(self.deletions.anchors):
            raise ValueError("Anchor cannot be staged and deleted in one draft")
        primitive_values = {
            PrimitiveRef(
                anchor=AnchorRef.parse(anchor), kind=kind, id=primitive_id
            ).key()
            for anchor, payload in self.anchors.items()
            for kind, primitives in payload.primitives.items()
            for primitive_id in primitives
        }
        if not set(self.replacements.primitives) <= primitive_values:
            raise ValueError("Primitive replacement target has no staged value")
        if primitive_values & set(self.deletions.primitives):
            raise ValueError("Primitive cannot be staged and deleted in one draft")
        return self
