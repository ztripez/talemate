"""Stateful card-deck primitives for deterministic scene gameplay.

Deck primitives are JSON-serializable selection sources persisted in a Talemate
scene's Game Primitives store. The models in this module define authored deck
content, per-instance runtime state, draw options, debug payloads, and
``DeckEngine`` operations that draw cards, update runtime state, and record deck
ledger entries.
"""

from __future__ import annotations

import copy
import random
from typing import TYPE_CHECKING, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.conditions import (
    PrimitiveConditionGroup,
    evaluate_condition_input,
)
from talemate.game.primitives.effects import Effect, apply_effects
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.selection import SelectionResult
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.values import primitive_payload_value

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class DeckCard(pydantic.BaseModel):
    """JSON-serializable card definition used by deck selection.

    Attributes:
        id: Unique non-empty card identifier within one deck definition.
        label: Human-readable non-empty label returned in selection results.
        text: Optional narrative text returned with the selected card.
        weight: Positive numeric selection weight used by weighted modes.
        tags: Tag strings used by include and exclude draw filters.
        variables: JSON-compatible values copied into the selection result.
        effects: Primitive effects optionally applied after selection.
        conditions: Condition groups that must match before the card can draw.
        cooldown_turns: Non-negative later draws that exclude the card.
        unique: Whether selecting the card exhausts it for the deck instance.
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
            The validated deck card model.

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
    """JSON-serializable deck definition for stateful card selection.

    Attributes:
        id: Stable non-empty deck identifier.
        name: Human-readable non-empty deck name.
        mode: Selection mode controlling replacement and runtime state behavior.
        shuffle: Shuffle strategy used for draw piles.
        reshuffle: Exhaustion policy for draw-pile modes.
        cards: Non-empty list of uniquely identified cards.
        tags: Metadata tags associated with the deck.
        variables: JSON-compatible metadata associated with the deck.
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
        """Validate cards and unique card ids.

        Returns:
            The validated deck definition model.

        Raises:
            ValueError: If the deck has no cards or card ids are duplicated.
        """
        if not self.cards:
            raise ValueError("Deck requires at least one card")
        ids = [card.id for card in self.cards]
        if len(ids) != len(set(ids)):
            raise ValueError("Deck card ids must be unique")
        return self


class DeckRuntimeState(pydantic.BaseModel):
    """Persisted runtime state for one deck primitive instance.

    The runtime stores draw piles, discard piles, recent draws, cooldowns, and a
    deterministic draw counter for one anchored deck primitive.

    Attributes:
        definition_id: Optional deck definition id used to initialize the state.
        mode: Deck mode copied from the definition.
        draw_pile: Ordered card ids available to draw-pile modes.
        discard: Card ids already drawn from draw-pile modes.
        recent: Recent card ids used by avoid-recent filtering.
        cooldowns: Non-negative remaining cooldown turns keyed by card id.
        exhausted: Unique card ids no longer available to this instance.
        draw_count: Non-negative number of completed draws.
        seed: Optional deterministic seed for shuffle operations.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    definition_id: str | None = None
    mode: Literal["sample", "draw", "bag", "physical"]
    draw_pile: list[str] = pydantic.Field(default_factory=list)
    discard: list[str] = pydantic.Field(default_factory=list)
    recent: list[str] = pydantic.Field(default_factory=list)
    cooldowns: dict[str, pydantic.NonNegativeInt] = pydantic.Field(default_factory=dict)
    exhausted: list[str] = pydantic.Field(default_factory=list)
    draw_count: pydantic.NonNegativeInt = 0
    seed: str | None = None


class DeckDrawOptions(pydantic.BaseModel):
    """Validated deck draw options.

    ``context`` is trace metadata copied into debug and ledger output; it does
    not affect card filtering or selection.

    Attributes:
        include_tags: Tags every drawable card must contain.
        exclude_tags: Tags drawable cards must not contain.
        avoid_recent: Optional non-negative count of recent card ids to avoid.
        context: JSON-compatible trace metadata copied to debug and ledger data.
        apply_effects: Whether selected card effects should run immediately.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    include_tags: list[str] = pydantic.Field(default_factory=list)
    exclude_tags: list[str] = pydantic.Field(default_factory=list)
    avoid_recent: pydantic.StrictInt | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    apply_effects: pydantic.StrictBool = False

    @pydantic.model_validator(mode="after")
    def validate_options(self) -> "DeckDrawOptions":
        """Validate draw option constraints.

        Returns:
            The validated draw options model.

        Raises:
            ValueError: If ``avoid_recent`` is negative.
        """
        if self.avoid_recent is not None and self.avoid_recent < 0:
            raise ValueError("avoid_recent must be >= 0")
        return self


class DeckDrawRequest(pydantic.BaseModel):
    """Validated graph/runtime request for drawing from a deck.

    Attributes:
        deck: Deck definition payload/model or deck reference string.
        anchor: Optional anchor for resolving definition-id runtime instances.
        instance_id: Optional primitive id for the runtime deck instance.
        include_tags: Tags every drawable card must contain.
        exclude_tags: Tags drawable cards must not contain.
        avoid_recent: Optional non-negative count of recent card ids to avoid.
        context: JSON-compatible trace metadata copied to debug and ledger data.
        apply_effects: Whether selected card effects should run immediately.
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
        """Return validated draw options from request fields.

        Returns:
            Draw options copied from this request.

        Raises:
            pydantic.ValidationError: If copied option fields are invalid.
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
    """Validated deck draw debug payload.

    Attributes:
        mode: Deck mode used for the draw.
        candidates: Candidate card ids before filters.
        filtered: Candidate card ids after filters.
        relaxed_avoid_recent: Whether avoid-recent filtering was relaxed.
        draw_pile: Runtime draw pile after candidate computation.
        discard: Runtime discard pile after candidate computation.
        recent: Recent card ids before the selected card is appended.
        cooldowns: Active cooldowns before selected-card state updates.
        context: JSON-compatible trace metadata.
        applied_effects: Optional effect-application result payload.
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


class DeckInstancePayload(pydantic.BaseModel):
    """Validated persisted payload for one deck primitive instance.

    Attributes:
        definition: Stored definition id or inline deck definition payload.
        runtime: Persisted runtime state for this deck instance.
        render_policy: Rendering hint for prompt/UI integrations.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    definition: str | DeckDefinition
    runtime: DeckRuntimeState
    render_policy: str = "hidden"


class DeckPeekResult(pydantic.BaseModel):
    """Validated output returned when inspecting a deck instance.

    Attributes:
        source_type: Constant source type, always ``"deck"``.
        source_id: Deck definition id.
        ref: Primitive reference for the runtime deck instance.
        runtime: Current runtime state for the deck instance.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    source_type: Literal["deck"] = "deck"
    source_id: str
    ref: str
    runtime: DeckRuntimeState


class DeckLedgerInput(pydantic.BaseModel):
    """Validated deck draw ledger input payload.

    Attributes:
        include_tags: Tags required by the draw request.
        exclude_tags: Tags excluded by the draw request.
        avoid_recent: Recent-card avoidance window requested by the draw.
        context: JSON-compatible trace metadata supplied by the caller.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    include_tags: list[str] = pydantic.Field(default_factory=list)
    exclude_tags: list[str] = pydantic.Field(default_factory=list)
    avoid_recent: int | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class DeckLedgerOutput(pydantic.BaseModel):
    """Validated deck draw ledger output payload.

    Attributes:
        card_id: Selected card id.
        mode: Deck mode used for selection.
        candidate_count: Number of candidates before filtering.
        filtered_count: Number of candidates after filtering.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    card_id: str
    mode: str
    candidate_count: int
    filtered_count: int


class DeckEngine:
    """Stateful deck resolver for Talemate scenes.

    The engine resolves inline deck definitions, stored definition ids, and deck
    primitive references. Draw operations persist runtime state and append deck
    ledger entries through ``PrimitiveStore``.
    """

    def __init__(self, rng: random.Random | None = None):
        """Create a deck engine with an optional random source.

        Args:
            rng: Random source implementing ``random`` for weighted sample and
                bag selections. When omitted, a new ``random.Random`` is used.
        """
        self.rng = rng if rng is not None else random.Random()

    def draw(
        self,
        scene: "Scene",
        deck: str | dict | DeckDefinition,
        *,
        anchor: AnchorRef | str | None = None,
        instance_id: str | None = None,
        options: DeckDrawOptions | dict | None = None,
    ) -> SelectionResult:
        """Draw one card, persist runtime state, and append a deck ledger entry.

        Args:
            scene: Talemate scene containing the Game Primitives store.
            deck: Deck definition object, dictionary, stored definition id, or
                full deck primitive reference string.
            anchor: Optional anchor used for definition-id runtime instances.
            instance_id: Optional deck primitive id. Defaults to the definition id.
            options: Optional draw filters and effect-application options.

        Returns:
            Selection result containing selected card data, copied variables,
            copied effects, and deck debug metadata.

        Raises:
            PrimitiveError: If the deck cannot be resolved, persisted runtime is
                invalid, no card is drawable, RNG output is invalid, or requested
                card effects fail.
            pydantic.ValidationError: If deck data or draw options are invalid.

        Side Effects:
            Persists deck runtime state, appends a ``deck.draw`` ledger entry,
            and applies card effects when ``options.apply_effects`` is true.
        """
        draw_options = DeckDrawOptions.model_validate(
            {} if options is None else options
        )
        store = PrimitiveStore.for_scene(scene)
        definition, ref, state = self._resolve_deck(store, deck, anchor, instance_id)
        candidates = _mode_candidates(definition, state)
        filtered, relaxed = _filter_cards(
            scene, definition, state, candidates, draw_options
        )
        if not filtered:
            raise PrimitiveError(f"Deck {ref.key()} has no drawable cards")
        card = self._select_card(definition, state, filtered)
        debug = _debug(definition, state, candidates, filtered, relaxed, draw_options)
        _apply_state_transition(definition, state, card, filtered)
        result = _selection_from_card(definition, ref, card, debug)
        _persist_deck_state(store, ref, definition, state)
        store.append_ledger(
            LedgerEntry(
                op="deck.draw",
                ref=ref.key(),
                input=DeckLedgerInput(
                    include_tags=draw_options.include_tags,
                    exclude_tags=draw_options.exclude_tags,
                    avoid_recent=draw_options.avoid_recent,
                    context=draw_options.context,
                ).model_dump(mode="json", exclude_none=True),
                output=DeckLedgerOutput(
                    card_id=card.id,
                    mode=definition.mode,
                    candidate_count=len(candidates),
                    filtered_count=len(filtered),
                ).model_dump(mode="json"),
            )
        )
        if draw_options.apply_effects and result.effects:
            effect_result = apply_effects(
                store, result.effects, reason=f"deck:{ref.key()}"
            )
            result.debug["applied_effects"] = effect_result.model_dump(
                mode="json", exclude_none=True
            )
            result_payload = result.model_dump(mode="python")
            result_payload["debug"] = DeckDebug.model_validate(result.debug).model_dump(
                mode="json", exclude_none=True
            )
            result = SelectionResult.model_validate(result_payload)
            if not effect_result.ok:
                raise PrimitiveError(f"Deck effects failed: {effect_result.results}")
        return result

    def peek(
        self,
        scene: "Scene",
        deck: str | dict | DeckDefinition,
        *,
        anchor: AnchorRef | str | None = None,
        instance_id: str | None = None,
    ) -> dict[str, pydantic.JsonValue]:
        """Return the current runtime state without drawing.

        Args:
            scene: Talemate scene containing the Game Primitives store.
            deck: Deck definition object, dictionary, definition id, or primitive
                reference to inspect.
            anchor: Optional anchor used for definition-id runtime instances.
            instance_id: Optional deck primitive id.

        Returns:
            JSON-compatible peek result containing source id, primitive ref, and
            runtime state.

        Raises:
            PrimitiveError: If the deck cannot be resolved or persisted runtime
                state is invalid.
            pydantic.ValidationError: If deck data is invalid.
        """
        store = PrimitiveStore.for_scene(scene)
        definition, ref, state = self._resolve_deck(store, deck, anchor, instance_id)
        return DeckPeekResult(
            source_id=definition.id, ref=ref.key(), runtime=state
        ).model_dump(mode="json")

    def shuffle(
        self,
        scene: "Scene",
        deck: str | dict | DeckDefinition,
        *,
        anchor: AnchorRef | str | None = None,
        instance_id: str | None = None,
    ) -> DeckRuntimeState:
        """Shuffle the draw pile for a persisted deck instance.

        Args:
            scene: Talemate scene containing the Game Primitives store.
            deck: Deck definition object, dictionary, definition id, or primitive
                reference to shuffle.
            anchor: Optional anchor used for definition-id runtime instances.
            instance_id: Optional deck primitive id.

        Returns:
            Updated persisted runtime state after shuffling.

        Raises:
            PrimitiveError: If the deck cannot be resolved or persisted runtime
                state is invalid.
            pydantic.ValidationError: If deck data is invalid.

        Side Effects:
            Persists the shuffled runtime state in the Game Primitives store.
        """
        store = PrimitiveStore.for_scene(scene)
        definition, ref, state = self._resolve_deck(store, deck, anchor, instance_id)
        state.draw_pile = _shuffled_ids(
            definition, state, preserve_physical_order=False
        )
        state.discard = []
        _persist_deck_state(store, ref, definition, state)
        return state

    def reset(
        self,
        scene: "Scene",
        deck: str | dict | DeckDefinition,
        *,
        anchor: AnchorRef | str | None = None,
        instance_id: str | None = None,
    ) -> DeckRuntimeState:
        """Reset a persisted deck instance to its initial runtime state.

        Args:
            scene: Talemate scene containing the Game Primitives store.
            deck: Deck definition object, dictionary, definition id, or primitive
                reference to reset.
            anchor: Optional anchor used for definition-id runtime instances.
            instance_id: Optional deck primitive id.

        Returns:
            Fresh runtime state for the deck instance.

        Raises:
            PrimitiveError: If the deck cannot be resolved or persisted runtime
                state is invalid.
            pydantic.ValidationError: If deck data is invalid.

        Side Effects:
            Persists the reset runtime state in the Game Primitives store.
        """
        store = PrimitiveStore.for_scene(scene)
        definition, ref, state = self._resolve_deck(store, deck, anchor, instance_id)
        state = _initial_state(definition, ref.key())
        _persist_deck_state(store, ref, definition, state)
        return state

    def _resolve_deck(
        self,
        store: PrimitiveStore,
        deck: str | dict | DeckDefinition,
        anchor: AnchorRef | str | None,
        instance_id: str | None,
    ) -> tuple[DeckDefinition, PrimitiveRef, DeckRuntimeState]:
        if isinstance(deck, (DeckDefinition, dict)):
            definition = DeckDefinition.model_validate(deck)
            ref = _instance_ref(anchor, instance_id or definition.id)
            return definition, ref, _runtime_for_ref(store, ref, definition)
        if not isinstance(deck, str) or not deck.strip():
            raise PrimitiveError("Deck must be a definition, dict, or string")
        deck_text = deck.strip()
        if "/" in deck_text:
            ref = PrimitiveRef.parse(deck_text)
            payload = store.get_primitive(ref)
            if payload is None:
                raise PrimitiveError(f"Deck primitive not found: {ref.key()}")
            definition = _definition_from_instance(store, payload)
            return (
                definition,
                ref,
                _runtime_from_payload(payload, definition, ref.key()),
            )
        payload = store.get_definition("decks", deck_text)
        if payload is None:
            raise PrimitiveError(f"Deck definition not found: {deck_text}")
        definition = DeckDefinition.model_validate(payload)
        ref = _instance_ref(anchor, instance_id or definition.id)
        return definition, ref, _runtime_for_ref(store, ref, definition)

    def _select_card(
        self, definition: DeckDefinition, state: DeckRuntimeState, card_ids: list[str]
    ) -> DeckCard:
        cards = {card.id: card for card in definition.cards}
        if definition.mode in {"draw", "physical"}:
            return cards[card_ids[0]]
        total = sum(float(cards[card_id].weight) for card_id in card_ids)
        value = _weighted_random(self.rng, definition.id) * total
        cumulative = 0.0
        for card_id in card_ids:
            cumulative += float(cards[card_id].weight)
            if value < cumulative:
                return cards[card_id]
        raise PrimitiveError(f"Deck {definition.id} failed weighted card selection")


def _instance_ref(anchor: AnchorRef | str | None, instance_id: str) -> PrimitiveRef:
    owner = (
        AnchorRef.model_validate(anchor)
        if anchor is not None
        else AnchorRef.parse("scene:main")
    )
    return PrimitiveRef(anchor=owner, kind="decks", id=instance_id)


def _initial_state(definition: DeckDefinition, seed: str) -> DeckRuntimeState:
    state = DeckRuntimeState(
        definition_id=definition.id,
        mode=definition.mode,
        seed=seed,
    )
    if definition.mode in {"draw", "physical"}:
        state.draw_pile = _shuffled_ids(definition, state)
    return state


def _runtime_for_ref(
    store: PrimitiveStore, ref: PrimitiveRef, definition: DeckDefinition
) -> DeckRuntimeState:
    payload = store.get_primitive(ref)
    if payload is None:
        return _initial_state(definition, ref.key())
    return _runtime_from_payload(payload, definition, ref.key())


def _runtime_from_payload(
    payload: dict, definition: DeckDefinition, seed: str
) -> DeckRuntimeState:
    if not isinstance(payload, dict):
        raise PrimitiveError(f"Deck instance {seed} payload must be a dictionary")
    instance = DeckInstancePayload.model_validate(payload)
    state = instance.runtime
    if state.mode != definition.mode:
        raise PrimitiveError("Persisted deck runtime mode does not match definition")
    return state


def _definition_from_instance(store: PrimitiveStore, payload: dict) -> DeckDefinition:
    if not isinstance(payload, dict):
        candidate = primitive_payload_value(payload)
        return DeckDefinition.model_validate(candidate)
    if "runtime" not in payload:
        return DeckDefinition.model_validate(primitive_payload_value(payload))
    instance = DeckInstancePayload.model_validate(payload)
    definition_ref = instance.definition
    if isinstance(definition_ref, DeckDefinition):
        return definition_ref
    definition = store.get_definition("decks", definition_ref)
    if definition is None:
        raise PrimitiveError(f"Deck definition not found: {definition_ref}")
    return DeckDefinition.model_validate(definition)


def _persist_deck_state(
    store: PrimitiveStore,
    ref: PrimitiveRef,
    definition: DeckDefinition,
    state: DeckRuntimeState,
) -> None:
    payload = DeckInstancePayload(
        definition=definition.id,
        runtime=state,
        render_policy="hidden",
    ).model_dump(mode="json")
    store.set_runtime_primitive(
        ref,
        payload,
    )


def _mode_candidates(definition: DeckDefinition, state: DeckRuntimeState) -> list[str]:
    if definition.mode in {"draw", "physical"}:
        if (
            not state.draw_pile
            and definition.reshuffle == "when_empty"
            and state.discard
        ):
            state.draw_pile = _shuffled_ids(definition, state, source=state.discard)
            state.discard = []
        return list(state.draw_pile)
    return [card.id for card in definition.cards if card.id not in state.exhausted]


def _filter_cards(
    scene: "Scene",
    definition: DeckDefinition,
    state: DeckRuntimeState,
    candidate_ids: list[str],
    options: DeckDrawOptions,
) -> tuple[list[str], bool]:
    cards = {card.id: card for card in definition.cards}
    filtered = []
    for card_id in candidate_ids:
        card = cards[card_id]
        if card_id in state.exhausted or state.cooldowns.get(card_id, 0) > 0:
            continue
        if not _conditions_match(scene, card.conditions):
            continue
        if options.include_tags and not set(options.include_tags).issubset(card.tags):
            continue
        if options.exclude_tags and set(options.exclude_tags).intersection(card.tags):
            continue
        filtered.append(card_id)
    relaxed = False
    if options.avoid_recent and filtered:
        recent = set(state.recent[-options.avoid_recent :])
        without_recent = [card_id for card_id in filtered if card_id not in recent]
        if without_recent:
            filtered = without_recent
        else:
            relaxed = True
    return filtered, relaxed


def _apply_state_transition(
    definition: DeckDefinition,
    state: DeckRuntimeState,
    card: DeckCard,
    filtered: list[str],
) -> None:
    if definition.mode in {"draw", "physical"}:
        state.draw_pile = [card_id for card_id in state.draw_pile if card_id != card.id]
        if card.unique:
            state.exhausted.append(card.id)
        else:
            state.discard.append(card.id)
    elif card.unique:
        state.exhausted.append(card.id)
    _decrement_cooldowns(state, selected=card.id)
    if card.cooldown_turns:
        state.cooldowns[card.id] = card.cooldown_turns
    state.recent.append(card.id)
    state.recent = state.recent[-max(len(filtered), 10) :]
    state.draw_count += 1


def _decrement_cooldowns(state: DeckRuntimeState, *, selected: str) -> None:
    next_cooldowns = {}
    for card_id, turns in state.cooldowns.items():
        if card_id == selected:
            continue
        remaining = turns - 1
        if remaining > 0:
            next_cooldowns[card_id] = remaining
    state.cooldowns = next_cooldowns


def _conditions_match(scene: "Scene", groups: list[PrimitiveConditionGroup]) -> bool:
    if not groups:
        return True
    payload = [group.model_dump(mode="json", exclude_none=True) for group in groups]
    matches, _ = evaluate_condition_input(scene, payload)
    return matches


def _debug(
    definition: DeckDefinition,
    state: DeckRuntimeState,
    candidates: list[str],
    filtered: list[str],
    relaxed: bool,
    options: DeckDrawOptions,
) -> dict[str, pydantic.JsonValue]:
    return DeckDebug(
        mode=definition.mode,
        candidates=candidates,
        filtered=filtered,
        relaxed_avoid_recent=relaxed,
        draw_pile=state.draw_pile,
        discard=state.discard,
        recent=state.recent,
        cooldowns=state.cooldowns,
        context=options.context,
    ).model_dump(mode="json", exclude_none=True)


def _selection_from_card(
    definition: DeckDefinition,
    ref: PrimitiveRef,
    card: DeckCard,
    debug: dict[str, pydantic.JsonValue],
) -> SelectionResult:
    return SelectionResult(
        source_type="deck",
        source_id=definition.id,
        anchor=ref.anchor.key(),
        result_id=card.id,
        label=card.label,
        text=card.text,
        effects=copy.deepcopy(card.effects),
        variables=copy.deepcopy(card.variables),
        debug=debug,
    )


def _shuffled_ids(
    definition: DeckDefinition,
    state: DeckRuntimeState,
    source: list[str] | None = None,
    *,
    preserve_physical_order: bool = True,
) -> list[str]:
    ids = list(source if source is not None else [card.id for card in definition.cards])
    if (
        preserve_physical_order
        and definition.mode == "physical"
        and state.draw_count == 0
    ):
        return ids
    rng = (
        random.Random(f"{state.seed}:{state.draw_count}")
        if definition.shuffle == "seeded"
        else random.Random()
    )
    rng.shuffle(ids)
    return ids


def _weighted_random(rng: random.Random, source_id: str) -> float:
    value = rng.random()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PrimitiveError(
            f"Deck {source_id} RNG produced non-numeric value: {value}"
        )
    if not 0 <= value < 1:
        raise PrimitiveError(
            f"Deck {source_id} RNG value must be >= 0 and < 1: {value}"
        )
    return float(value)
