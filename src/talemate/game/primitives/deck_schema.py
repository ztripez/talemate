"""Canonical schemas and compatibility checks for deck primitives."""

from __future__ import annotations

from typing import Literal

import pydantic

from talemate.game.primitives.conditions import PrimitiveConditionGroup
from talemate.game.primitives.effects import Effect


class DeckCard(pydantic.BaseModel):
    """Define one weighted, conditionally eligible card in a deck.

    Attributes:
        id: Non-empty identifier unique within the containing deck.
        label: Non-empty display name.
        text: Optional narrative content returned with the card.
        weight: Positive finite selection weight.
        tags: Labels used by include and exclude filters.
        variables: Arbitrary JSON values available to card consumers.
        effects: State changes optionally applied when the card is selected.
        conditions: Condition groups that determine card eligibility.
        cooldown_turns: Optional non-negative number of draws before reuse.
        unique: Whether selection permanently exhausts the card.

    Invariants:
        Unknown fields and non-finite numbers are rejected. String whitespace is
        stripped, ``weight`` is greater than zero, and ``cooldown_turns`` is
        either ``None`` or non-negative.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    text: str | None = None
    weight: pydantic.StrictInt | pydantic.StrictFloat = 1
    tags: list[str] = pydantic.Field(default_factory=list)
    variables: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    effects: list[Effect] = pydantic.Field(default_factory=list)
    conditions: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)
    cooldown_turns: pydantic.StrictInt | None = None
    unique: bool = False

    @pydantic.model_validator(mode="after")
    def validate_card_rules(self) -> "DeckCard":
        """Validate deck-card weight and cooldown invariants.

        Returns:
            The validated card.

        Raises:
            ValueError: If ``weight`` is not positive or ``cooldown_turns`` is
                negative.

        """
        if self.weight <= 0:
            raise ValueError("Deck card weight must be > 0")
        if self.cooldown_turns is not None and self.cooldown_turns < 0:
            raise ValueError("Deck card cooldown_turns must be >= 0")
        return self


class DeckDefinition(pydantic.BaseModel):
    """Define a reusable deck and its stateful selection policy.

    Attributes:
        id: Non-empty reusable definition identifier.
        name: Non-empty display name.
        mode: Selection semantics: replacement sampling, draw pile, bag, or
            physical-order drawing.
        shuffle: Seeded deterministic or nondeterministic shuffle policy.
        reshuffle: Whether an empty draw source remains empty or is replenished.
        cards: Non-empty card collection.
        tags: Labels available to definition consumers.
        variables: Arbitrary JSON metadata owned by the definition.

    Invariants:
        Card identifiers are unique within ``cards``. Unknown fields,
        non-finite numbers, and unsupported policy values are rejected.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    name: str = pydantic.Field(min_length=1)
    mode: Literal["sample", "draw", "bag", "physical"] = "bag"
    shuffle: Literal["seeded", "random"] = "seeded"
    reshuffle: Literal["never", "when_empty"] = "when_empty"
    cards: list[DeckCard]
    tags: list[str] = pydantic.Field(default_factory=list)
    variables: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_deck_rules(self) -> "DeckDefinition":
        """Require at least one card and unique card identifiers.

        Returns:
            The validated deck definition.

        Raises:
            ValueError: If the deck is empty or card identifiers are duplicated.

        """
        if not self.cards:
            raise ValueError("Deck requires at least one card")
        ids = [card.id for card in self.cards]
        if len(ids) != len(set(ids)):
            raise ValueError("Deck card ids must be unique")
        return self


class DeckRuntimeState(pydantic.BaseModel):
    """Persist mutable selection state for one anchored deck instance.

    Attributes:
        definition_id: Non-empty identifier of the owning deck definition.
        mode: Selection mode copied from the owning definition.
        draw_pile: Card identifiers available in draw order.
        discard: Card identifiers already drawn and eligible for reshuffling.
        recent: Card identifiers retained for recent-selection avoidance.
        cooldowns: Remaining non-negative cooldown draws by card identifier.
        exhausted: Permanently unavailable unique card identifiers.
        draw_count: Non-negative number of selections attempted by the instance.
        seed: Optional stable input for deterministic shuffling.

    Invariants:
        Unknown fields and non-finite numbers are rejected. Compatibility with a
        particular definition is checked by ``validate_deck_runtime_compatibility``.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    definition_id: str = pydantic.Field(min_length=1)
    mode: Literal["sample", "draw", "bag", "physical"]
    draw_pile: list[str] = pydantic.Field(default_factory=list)
    discard: list[str] = pydantic.Field(default_factory=list)
    recent: list[str] = pydantic.Field(default_factory=list)
    cooldowns: dict[str, pydantic.NonNegativeInt] = pydantic.Field(default_factory=dict)
    exhausted: list[str] = pydantic.Field(default_factory=list)
    draw_count: pydantic.NonNegativeInt = 0
    seed: str | None = None


class DeckDrawOptions(pydantic.BaseModel):
    """Control filtering and side effects for one deck selection.

    Attributes:
        include_tags: Tags of which at least one must occur on eligible cards.
        exclude_tags: Tags that make a card ineligible.
        avoid_recent: Optional non-negative recent-selection window.
        context: JSON condition-evaluation context.
        apply_effects: Whether selected-card effects mutate game state.

    Invariants:
        Unknown fields and non-finite numbers are rejected, and ``avoid_recent``
        is either ``None`` or non-negative.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    include_tags: list[str] = pydantic.Field(default_factory=list)
    exclude_tags: list[str] = pydantic.Field(default_factory=list)
    avoid_recent: pydantic.StrictInt | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    apply_effects: pydantic.StrictBool = False

    @pydantic.model_validator(mode="after")
    def validate_options(self) -> "DeckDrawOptions":
        """Require a non-negative avoid-recent window when supplied.

        Returns:
            The validated draw options.

        Raises:
            ValueError: If ``avoid_recent`` is negative.

        """
        if self.avoid_recent is not None and self.avoid_recent < 0:
            raise ValueError("avoid_recent must be >= 0")
        return self


class DeckDrawRequest(pydantic.BaseModel):
    """Describe a graph or runtime request to select from a deck.

    Attributes:
        deck: Inline definition or identifier of a stored definition.
        anchor: Optional canonical owner address used to resolve state.
        instance_id: Optional anchored instance identifier.
        include_tags: Tags of which at least one must occur on eligible cards.
        exclude_tags: Tags that make a card ineligible.
        avoid_recent: Optional recent-selection window validated by ``options``.
        context: JSON condition-evaluation context.
        apply_effects: Whether selected-card effects mutate game state.

    Invariants:
        Unknown fields and non-finite numbers are rejected. ``options`` performs
        the non-negative ``avoid_recent`` validation before selection.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    deck: DeckDefinition | str
    anchor: str | None = None
    instance_id: str | None = None
    include_tags: list[str] = pydantic.Field(default_factory=list)
    exclude_tags: list[str] = pydantic.Field(default_factory=list)
    avoid_recent: pydantic.StrictInt | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    apply_effects: pydantic.StrictBool = False

    def options(self) -> DeckDrawOptions:
        """Validate and return the selection-specific request fields.

        Returns:
            Detached deck draw options containing filters, context, and the
            effect-application flag.

        Raises:
            pydantic.ValidationError: If ``avoid_recent`` is negative or another
                option violates the strict draw-option schema.

        """
        return DeckDrawOptions.model_validate(
            {
                "include_tags": self.include_tags,
                "exclude_tags": self.exclude_tags,
                "avoid_recent": self.avoid_recent,
                "context": self.context,
                "apply_effects": self.apply_effects,
            }
        )


class DeckDebug(pydantic.BaseModel):
    """Report selection decisions and resulting deck state for diagnostics.

    Attributes:
        mode: Selection mode used by the operation.
        candidates: Card identifiers considered before filtering.
        filtered: Card identifiers remaining after filtering.
        relaxed_avoid_recent: Whether recent-card avoidance had to be relaxed.
        draw_pile: Card identifiers remaining in draw order.
        discard: Card identifiers currently discarded.
        recent: Card identifiers retained by recent-card tracking.
        cooldowns: Remaining cooldown draws by card identifier.
        context: JSON condition context used for the selection.
        applied_effects: Optional JSON report from effect application.

    Invariants:
        Unknown fields and non-finite numeric values are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: str
    candidates: list[str]
    filtered: list[str]
    relaxed_avoid_recent: bool = False
    draw_pile: list[str] = pydantic.Field(default_factory=list)
    discard: list[str] = pydantic.Field(default_factory=list)
    recent: list[str] = pydantic.Field(default_factory=list)
    cooldowns: dict[str, int] = pydantic.Field(default_factory=dict)
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    applied_effects: dict[str, pydantic.JsonValue] | None = None


class DeckPeekResult(pydantic.BaseModel):
    """Expose the identity and runtime state of one inspected deck instance.

    Attributes:
        source_type: Constant ``"deck"`` discriminator.
        source_id: Identifier of the source deck definition.
        ref: Canonical reference of the anchored deck instance.
        runtime: Current validated runtime state.

    Invariants:
        Unknown fields and non-finite numbers are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    source_type: Literal["deck"] = "deck"
    source_id: str
    ref: str
    runtime: DeckRuntimeState


class DeckLedgerInput(pydantic.BaseModel):
    """Record the caller-controlled inputs of a deck selection.

    Attributes:
        include_tags: Inclusion tags supplied to selection.
        exclude_tags: Exclusion tags supplied to selection.
        avoid_recent: Optional recent-card avoidance window.
        context: JSON condition context supplied to selection.

    Invariants:
        Unknown fields and non-finite numbers are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    include_tags: list[str] = pydantic.Field(default_factory=list)
    exclude_tags: list[str] = pydantic.Field(default_factory=list)
    avoid_recent: int | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class DeckLedgerOutput(pydantic.BaseModel):
    """Record the selected card and filtering counts of a deck operation.

    Attributes:
        card_id: Identifier of the selected card.
        mode: Selection mode used by the operation.
        candidate_count: Number of cards considered before filtering.
        filtered_count: Number of cards remaining after filtering.

    Invariants:
        Unknown fields and non-finite numbers are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    card_id: str
    mode: str
    candidate_count: int
    filtered_count: int


def validate_deck_runtime_compatibility(
    ref: str,
    runtime: DeckRuntimeState,
    definition: DeckDefinition,
) -> list[str]:
    """Find retained runtime values incompatible with a deck definition.

    Args:
        ref: Canonical instance reference included in diagnostic messages.
        runtime: Retained state to compare.
        definition: Current definition expected to own the state.

    Returns:
        Diagnostic messages for a changed mode or references to removed cards;
        an empty list means the retained state is compatible.

    Side Effects:
        None; the runtime and definition are not modified.

    """
    errors = []
    if runtime.mode != definition.mode:
        errors.append(
            f"Deck runtime mode for {ref} is '{runtime.mode}', expected "
            f"'{definition.mode}'"
        )
    card_ids = {card.id for card in definition.cards}
    runtime_ids = (
        set(runtime.draw_pile)
        | set(runtime.discard)
        | set(runtime.recent)
        | set(runtime.cooldowns)
        | set(runtime.exhausted)
    )
    unknown = sorted(runtime_ids - card_ids)
    if unknown:
        errors.append(
            f"Deck runtime for {ref} references unknown card IDs: " + ", ".join(unknown)
        )
    return errors
