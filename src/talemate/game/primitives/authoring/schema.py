"""Authoring request and result schemas for primitive drafts."""

import pydantic

from talemate.game.primitives.attributes import AttributeSource
from talemate.game.primitives.conditions import PrimitiveConditionGroup
from talemate.game.primitives.deck_schema import DeckDefinition
from talemate.game.primitives.definitions import ClockPayload, MeterPayload
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.roll_tables import RollTableDefinition


class DraftRequest(pydantic.BaseModel):
    """Target one existing primitive authoring draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to read or mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.

    Invariants:
        Unknown fields are rejected and surrounding string whitespace is stripped.
        ``draft_id`` and ``expected_revision`` are non-empty.

    """

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    draft_id: str = pydantic.Field(min_length=1)
    expected_revision: str = pydantic.Field(min_length=1)

    @property
    def canonical_payload(self) -> dict[str, pydantic.JsonValue]:
        """Serialize request fields that belong in a primitive payload.

        Returns:
            A JSON-compatible dictionary excluding the authoring-only draft
            identifier.

        """
        return self.model_dump(mode="json", exclude={"draft_id", "expected_revision"})


class AnchoredDraftRequest(DraftRequest):
    """Target a primitive attached to an anchor within an authoring draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        anchor: Anchor reference under which to stage the primitive.

    """

    anchor: str

    @property
    def canonical_payload(self) -> dict[str, pydantic.JsonValue]:
        """Serialize fields stored in an anchored primitive payload.

        Returns:
            A JSON-compatible dictionary excluding the draft identifier, anchor
            reference, and fields whose values are ``None``.

        """
        return self.model_dump(
            mode="json",
            exclude={"draft_id", "expected_revision", "anchor"},
            exclude_none=True,
        )


class DefinitionDraftRequest(DraftRequest):
    """Target a reusable definition within an authoring draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.

    """

    @property
    def canonical_payload(self) -> dict[str, pydantic.JsonValue]:
        """Serialize fields stored in a reusable primitive definition.

        Returns:
            A JSON-compatible dictionary excluding the authoring-only draft
            identifier.

        """
        return self.model_dump(mode="json", exclude={"draft_id", "expected_revision"})


class OptionalAnchoredDefinitionRequest(DefinitionDraftRequest):
    """Optionally stage an anchored instance with a reusable definition.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        anchor: Optional anchor reference under which to stage an instance.
        instance_id: Optional instance identifier requiring ``anchor``; the
            definition identifier is used when this value is omitted.

    """

    anchor: str | None = None
    instance_id: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_instance_anchor(self) -> "OptionalAnchoredDefinitionRequest":
        """Require an anchor whenever a custom instance identifier is supplied.

        Returns:
            The validated request instance without mutation.

        Raises:
            ValueError: If ``instance_id`` is set without ``anchor``. Pydantic
                reports this failure as a validation error during model validation.

        """
        if self.instance_id is not None and self.anchor is None:
            raise ValueError("instance_id requires anchor")
        return self

    @property
    def canonical_payload(self) -> dict[str, pydantic.JsonValue]:
        """Serialize only fields belonging to the reusable definition.

        Returns:
            A JSON-compatible dictionary excluding the authoring-only ``draft_id``,
            ``anchor``, and ``instance_id`` fields.

        """
        return self.model_dump(
            mode="json",
            exclude={"draft_id", "expected_revision", "anchor", "instance_id"},
        )


class CreateAnchorRequest(DraftRequest):
    """Describe an anchor to stage in a primitive authoring draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        kind: Anchor kind used in the canonical anchor reference.
        id: Anchor identifier used in the canonical anchor reference.
        tags: Tag strings assigned to the staged anchor.
        meta: JSON-compatible metadata assigned to the staged anchor.

    """

    kind: str
    id: str
    tags: list[str] = pydantic.Field(default_factory=list)
    meta: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class CreateMeterRequest(AnchoredDraftRequest, MeterPayload):
    """Describe a bounded numeric meter to stage under an anchor.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        anchor: Anchor reference under which to stage the meter.
        id: Canonical path-segment identifier for the meter.
        label: Optional human-readable meter label.
        min: Finite inclusive lower bound for the meter value.
        max: Finite inclusive upper bound for the meter value.
        value: Finite current value constrained between ``min`` and ``max``.
        render_policy: Visibility policy used when rendering the meter.

    """


class CreateClockRequest(AnchoredDraftRequest, ClockPayload):
    """Describe an integer progress clock to stage under an anchor.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        anchor: Anchor reference under which to stage the clock.
        id: Canonical path-segment identifier for the clock.
        label: Optional human-readable clock label.
        max: Positive inclusive upper bound for clock progress.
        value: Non-negative current progress not exceeding ``max``.
        render_policy: Visibility policy used when rendering the clock.

    """


class CreateDeckRequest(OptionalAnchoredDefinitionRequest, DeckDefinition):
    """Describe a reusable deck definition to stage in a draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        id: Stable non-empty deck identifier.
        name: Human-readable non-empty deck name.
        mode: Card selection mode controlling replacement and runtime state.
        shuffle: Shuffle strategy used for draw piles.
        reshuffle: Exhaustion policy used by draw-pile modes.
        cards: Non-empty list of uniquely identified deck cards.
        tags: Metadata tags associated with the deck.
        variables: JSON-compatible metadata associated with the deck.
        anchor: Optional anchor under which to stage a canonical deck instance.
        instance_id: Optional anchored primitive id; defaults to the definition id.

    """


class CreateRollTableRequest(OptionalAnchoredDefinitionRequest, RollTableDefinition):
    """Describe a reusable roll-table definition to stage in a draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        id: Stable non-empty roll-table identifier.
        name: Human-readable non-empty roll-table name.
        mode: Selection mode, either dice-total or weighted selection.
        dice: Dice expression required by dice-total tables.
        rows: Non-empty list of uniquely identified roll-table rows.
        modifiers: Modifier references applied by the roll table.
        anchor: Optional anchor under which to stage a canonical table instance.
        instance_id: Optional anchored primitive id; defaults to the definition id.

    """


class CreateRelationshipRequest(DraftRequest):
    """Describe a directional relationship anchor to stage in a draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        source: Anchor reference for the relationship source.
        target: Anchor reference for the relationship target.
        dimensions: Uniquely identified bounded meters representing relationship
            dimensions.
        tags: Tag strings assigned to the relationship anchor.

    """

    source: str
    target: str
    dimensions: list[MeterPayload]
    tags: list[str] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("dimensions", mode="before")
    @classmethod
    def apply_relationship_dimension_defaults(cls, value: object) -> object:
        """Apply relationship-specific defaults before canonical meter validation."""
        if not isinstance(value, list):
            return value
        defaults = {"min": -5, "max": 5, "value": 0, "render_policy": "summary"}
        return [
            {**defaults, **dimension} if isinstance(dimension, dict) else dimension
            for dimension in value
        ]

    @pydantic.field_validator("dimensions")
    @classmethod
    def validate_unique_dimensions(
        cls, value: list[MeterPayload]
    ) -> list[MeterPayload]:
        """Require unique identifiers across relationship dimensions.

        Args:
            value: Validated relationship dimension meters.

        Returns:
            The unchanged list of relationship dimension meters.

        Raises:
            ValueError: If multiple dimensions have the same canonical meter
                identifier.

        """
        dimension_ids = [dimension.id for dimension in value]
        if len(dimension_ids) != len(set(dimension_ids)):
            raise ValueError("Relationship dimension IDs must be unique")
        return value


class AddModifierOperation(pydantic.BaseModel):
    """Represent the external additive operation for a roll modifier request.

    Attributes:
        add: Finite numeric amount added to a matching roll-table result.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)
    add: pydantic.StrictInt | pydantic.StrictFloat


class CreateModifierRequest(DraftRequest):
    """Describe a conditional roll modifier to stage in a draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        id: Stable modifier identifier.
        label: Optional display label for debug traces.
        applies_to: Roll-table definition identifier or primitive reference
            targeted by the modifier.
        when: Primitive-aware condition groups required for activation.
        operation: External additive operation converted to canonical ``add``.
        explanation: Optional human-readable reason for the modifier.

    """

    id: str
    label: str | None = None
    applies_to: str
    when: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)
    operation: AddModifierOperation
    explanation: str | None = None

    def canonical_model(self) -> RollModifier:
        """Convert the external additive operation to a canonical roll modifier.

        Returns:
            A validated roll modifier whose ``add`` field contains the request's
            operation value and which excludes the draft identifier.

        Raises:
            pydantic.ValidationError: If the converted payload violates the roll
                modifier schema.

        """
        return RollModifier.model_validate(
            {
                **self.model_dump(
                    mode="python",
                    exclude={"draft_id", "expected_revision", "operation"},
                ),
                "add": self.operation.add,
            }
        )

    @property
    def canonical_payload(self) -> dict[str, pydantic.JsonValue]:
        """Serialize the request as a canonical roll modifier payload.

        Returns:
            A JSON-compatible roll modifier dictionary excluding authoring-only
            request fields.

        Raises:
            pydantic.ValidationError: If conversion to the canonical roll
                modifier schema fails.

        """
        return self.canonical_model().model_dump(mode="json")


class CreateAttributeSourceRequest(AnchoredDraftRequest, AttributeSource):
    """Describe an attribute source to stage under an anchor in a draft.

    Attributes:
        draft_id: Non-empty identifier of the draft to mutate.
        expected_revision: Non-empty primitive-root revision required by mutations.
        anchor: Anchor reference under which to stage the attribute source.
        id: Stable non-empty attribute identifier under the anchor.
        label: Optional human-readable label used during rendering.
        source: Deterministic source kind used to resolve the attribute value.
        render_policy: Visibility policy controlling attribute rendering.
        value: Explicit JSON-compatible value used by literal sources.
        ref: Optional primitive, modifier, anchor, or state reference.
        options: JSON-compatible source-specific options.
        conditions: Condition groups that gate attribute resolution.

    """

    @property
    def canonical_payload(self) -> dict[str, pydantic.JsonValue]:
        """Serialize fields stored in an anchored attribute source payload.

        Returns:
            A JSON-compatible attribute source dictionary excluding the draft and
            anchor boundary fields. An explicitly supplied literal ``None`` value
            remains present in the dictionary.

        """
        payload = super().canonical_payload
        if self.source == "literal" and "value" in self.model_fields_set:
            payload["value"] = self.value
        return payload


__all__ = [
    "AddModifierOperation",
    "AnchoredDraftRequest",
    "CreateAnchorRequest",
    "CreateAttributeSourceRequest",
    "CreateClockRequest",
    "CreateDeckRequest",
    "CreateMeterRequest",
    "CreateModifierRequest",
    "CreateRelationshipRequest",
    "CreateRollTableRequest",
    "DefinitionDraftRequest",
    "DraftRequest",
]
