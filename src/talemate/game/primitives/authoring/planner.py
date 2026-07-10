"""Strict schemas for scenario primitive planning and generation results."""

from __future__ import annotations

from typing import Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef
from talemate.game.primitives.schema import PrimitiveDraft


class PrimitivePlanSystem(pydantic.BaseModel):
    """A primitive system proposed by the advisory planning pass."""

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, str_strip_whitespace=True
    )

    kind: Literal[
        "meter",
        "clock",
        "deck",
        "roll_table",
        "relationship",
        "modifier",
        "attribute_source",
    ] = pydantic.Field(description="Primitive category to author")
    id: str = pydantic.Field(min_length=1, description="Unique planned system ID")
    anchor: AnchorRef | None = pydantic.Field(description="Owning canonical anchor")
    purpose: str = pydantic.Field(min_length=1, description="Purpose of the system")
    visibility: Literal["prompt_visible", "hidden"] = pydantic.Field(
        description="Prompt visibility of the system"
    )
    depends_on: list[str] = pydantic.Field(description="Required system IDs")

    @pydantic.field_validator("depends_on", mode="after")
    @classmethod
    def validate_dependencies(cls, value: list[str]) -> list[str]:
        """Reject dependencies that are blank or duplicated.

        Args:
            value: Planned system identifiers required by this system.

        Returns:
            The unchanged validated dependency list.

        Raises:
            ValueError: If a dependency is blank or duplicated.
        """
        if any(not dependency.strip() for dependency in value):
            raise ValueError("System dependencies cannot be blank")
        if len(value) != len(set(value)):
            raise ValueError("System dependencies must be unique")
        return value


class PrimitiveScenarioPlan(pydantic.BaseModel):
    """Advisory plan used to guide, but never directly persist, primitives."""

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, str_strip_whitespace=True
    )

    needed: bool = pydantic.Field(description="Whether primitives are needed")
    rationale: str = pydantic.Field(min_length=1, description="Planning rationale")
    anchors: list[AnchorRef] = pydantic.Field(description="Required anchors")
    systems: list[PrimitivePlanSystem] = pydantic.Field(description="Planned systems")
    prompt_visible: list[str] = pydantic.Field(description="Prompt-visible details")
    hidden: list[str] = pydantic.Field(description="Prompt-hidden details")
    warnings: list[str] = pydantic.Field(description="Non-fatal planning concerns")

    @pydantic.field_validator("anchors", mode="after")
    @classmethod
    def validate_unique_anchors(cls, value: list[AnchorRef]) -> list[AnchorRef]:
        """Reject repeated canonical anchor references.

        Args:
            value: Canonical anchors declared by the plan.

        Returns:
            The unchanged validated anchor list.

        Raises:
            ValueError: If an anchor is repeated.
        """
        references = [anchor.key() for anchor in value]
        if len(references) != len(set(references)):
            raise ValueError("Plan anchor references must be unique")
        return value

    @pydantic.field_validator("systems", mode="after")
    @classmethod
    def validate_unique_systems(
        cls, value: list[PrimitivePlanSystem]
    ) -> list[PrimitivePlanSystem]:
        """Reject repeated system identifiers.

        Args:
            value: Primitive systems declared by the plan.

        Returns:
            The unchanged validated system list.

        Raises:
            ValueError: If a system ID is repeated.
        """
        identifiers = [system.id for system in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Plan system IDs must be unique")
        return value

    @pydantic.field_validator("prompt_visible", "hidden", "warnings", mode="after")
    @classmethod
    def validate_labels(cls, value: list[str]) -> list[str]:
        """Reject blank or duplicate planning labels.

        Args:
            value: Prompt-visible, hidden, or warning labels from the plan.

        Returns:
            The unchanged validated label list.

        Raises:
            ValueError: If a label is blank or duplicated.
        """
        if any(not label.strip() for label in value):
            raise ValueError("Plan labels cannot be blank")
        if len(value) != len(set(value)):
            raise ValueError("Plan labels must be unique")
        return value

    @pydantic.model_validator(mode="after")
    def validate_needed_content(self) -> "PrimitiveScenarioPlan":
        """Require planned content when primitive authoring is needed.

        Returns:
            The validated plan.

        Raises:
            ValueError: If a needed plan has no anchors or systems.
        """
        if self.needed and not self.anchors and not self.systems:
            raise ValueError("needed=True requires at least one anchor or system")
        return self

    @property
    def is_empty(self) -> bool:
        """Whether the plan explicitly requests no primitive authoring."""
        return not self.needed


class PrimitivePlanExtraction(pydantic.BaseModel):
    """Extracted response envelope returned by the planning prompt."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    response: PrimitiveScenarioPlan = pydantic.Field(description="Validated plan")


class PrimitiveCreationCounts(pydantic.BaseModel):
    """Counts of each primitive category staged by an authoring pass."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    anchors: int = pydantic.Field(default=0, ge=0, description="Anchors staged")
    meters: int = pydantic.Field(default=0, ge=0, description="Meters staged")
    clocks: int = pydantic.Field(default=0, ge=0, description="Clocks staged")
    decks: int = pydantic.Field(default=0, ge=0, description="Decks staged")
    roll_tables: int = pydantic.Field(default=0, ge=0, description="Roll tables staged")
    relationships: int = pydantic.Field(
        default=0, ge=0, description="Relationships staged"
    )
    modifiers: int = pydantic.Field(default=0, ge=0, description="Modifiers staged")
    attribute_sources: int = pydantic.Field(
        default=0, ge=0, description="Attribute sources staged"
    )


class PrimitiveDraftReport(pydantic.BaseModel):
    """Count taxonomy and human-readable summary for a primitive draft."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    created: PrimitiveCreationCounts = pydantic.Field(
        description="Derived creation counts"
    )
    summary: str = pydantic.Field(description="Human-readable draft outcome")

    @classmethod
    def from_draft(
        cls, draft: PrimitiveDraft, *, committed: bool
    ) -> "PrimitiveDraftReport":
        """Build a report from validated draft contents.

        Args:
            draft: Validated draft to count.
            committed: Whether the draft was committed.

        Returns:
            Counts and a summary of the draft outcome.

        Raises:
            KeyError: If a required definition category is absent.
            pydantic.ValidationError: If derived report data is invalid.
        """
        counts = PrimitiveCreationCounts(
            anchors=len(draft.anchors),
            relationships=sum(
                anchor.startswith("relationship:") for anchor in draft.anchors
            ),
            meters=sum(
                len(anchor.primitives.get("meters", {}))
                for anchor in draft.anchors.values()
            ),
            clocks=sum(
                len(anchor.primitives.get("clocks", {}))
                for anchor in draft.anchors.values()
            ),
            attribute_sources=sum(
                len(anchor.primitives.get("attributes", {}))
                for anchor in draft.anchors.values()
            ),
            decks=len(draft.definitions.root["decks"]),
            roll_tables=len(draft.definitions.root["roll_tables"]),
            modifiers=len(draft.definitions.root["modifiers"]),
        )
        created = ", ".join(
            f"{count} {kind.replace('_', ' ')}"
            for kind, count in counts.model_dump().items()
            if count
        )
        state = "Committed" if committed else "Drafted"
        return cls(created=counts, summary=f"{state} {created or 'no primitives'}.")


class PrimitiveScenarioBundleResult(pydantic.BaseModel):
    """Outcome of an isolated scenario primitive authoring pass."""

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    ok: bool = pydantic.Field(description="Whether generation succeeded")
    draft_id: str | None = pydantic.Field(default=None, description="Created draft ID")
    committed: bool = pydantic.Field(
        default=False, description="Whether the draft was committed"
    )
    summary: str = pydantic.Field(default="", description="Generation outcome")
    created: PrimitiveCreationCounts = pydantic.Field(
        default_factory=PrimitiveCreationCounts, description="Staged primitive counts"
    )
    warnings: list[str] = pydantic.Field(
        default_factory=list, description="Non-fatal concerns"
    )
    errors: list[str] = pydantic.Field(
        default_factory=list, description="Generation failures"
    )


__all__ = [
    "PrimitiveCreationCounts",
    "PrimitiveDraftReport",
    "PrimitivePlanExtraction",
    "PrimitivePlanSystem",
    "PrimitiveScenarioBundleResult",
    "PrimitiveScenarioPlan",
]
