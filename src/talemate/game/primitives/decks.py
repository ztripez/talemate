"""Runtime engine for deterministic stateful card-deck primitives."""

from __future__ import annotations

import copy
import random
from typing import TYPE_CHECKING

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.conditions import conditions_match
from talemate.game.primitives.deck_schema import (
    DeckCard,
    DeckDebug,
    DeckDefinition,
    DeckDrawOptions,
    DeckDrawRequest,
    DeckLedgerInput,
    DeckLedgerOutput,
    DeckPeekResult,
    DeckRuntimeState,
    validate_deck_runtime_compatibility,
)
from talemate.game.primitives.deck_state import (
    DeckInstancePayload,
    initial_deck_state as _initial_state,
    shuffled_deck_ids as _shuffled_ids,
)
from talemate.game.primitives.effects import apply_effects
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.selection import SelectionResult
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

__all__ = [
    "DeckCard",
    "DeckDebug",
    "DeckDefinition",
    "DeckDrawOptions",
    "DeckDrawRequest",
    "DeckEngine",
    "DeckInstancePayload",
    "DeckLedgerInput",
    "DeckLedgerOutput",
    "DeckPeekResult",
    "DeckRuntimeState",
    "validate_deck_runtime_compatibility",
]


class DeckEngine:
    """Stateful deck resolver for Talemate scenes."""

    def __init__(self, rng: random.Random | None = None):
        """Create a deck engine with an optional random source."""
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
        """Draw one card, persist runtime state, and append a ledger entry."""
        draw_options = DeckDrawOptions.model_validate(
            {} if options is None else options
        )
        store = PrimitiveStore.for_scene(scene)
        candidate_store = PrimitiveStore(
            copy.deepcopy(store.root), store.max_ledger_length
        )
        definition, ref, state = self._resolve_deck(
            candidate_store, deck, anchor, instance_id
        )
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
        _persist_deck_state(candidate_store, ref, definition, state)
        candidate_store.append_ledger(
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
                candidate_store, result.effects, reason=f"deck:{ref.key()}"
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
        store.replace_validated_root(candidate_store.root)
        return result

    def peek(
        self,
        scene: "Scene",
        deck: str | dict | DeckDefinition,
        *,
        anchor: AnchorRef | str | None = None,
        instance_id: str | None = None,
    ) -> dict[str, pydantic.JsonValue]:
        """Return the current runtime state without drawing."""
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
        """Shuffle and persist the draw pile for a deck instance."""
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
        """Reset and persist a deck instance's initial runtime state."""
        store = PrimitiveStore.for_scene(scene)
        definition, ref, _state = self._resolve_deck(store, deck, anchor, instance_id)
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
            definition, state = _resolve_persisted_instance(store, payload, ref.key())
            return definition, ref, state
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
    instance = _instance_from_payload(payload, seed)
    state = instance.runtime
    _validate_runtime_state(state, definition, seed)
    return state


def _validate_runtime_state(
    state: DeckRuntimeState, definition: DeckDefinition, seed: str
) -> None:
    if state.definition_id != definition.id:
        raise PrimitiveError(
            f"Persisted deck runtime for {seed} has definition_id "
            f"'{state.definition_id}', expected '{definition.id}'"
        )
    if state.mode != definition.mode:
        raise PrimitiveError(
            f"Persisted deck runtime for {seed} has mode '{state.mode}', "
            f"expected '{definition.mode}'"
        )
    card_ids = {card.id for card in definition.cards}
    runtime_card_ids = (
        set(state.draw_pile)
        | set(state.discard)
        | set(state.recent)
        | set(state.cooldowns)
        | set(state.exhausted)
    )
    unknown_ids = sorted(runtime_card_ids - card_ids)
    if unknown_ids:
        raise PrimitiveError(
            f"Persisted deck runtime for {seed} references unknown card IDs "
            f"for definition '{definition.id}': {', '.join(unknown_ids)}"
        )


def _instance_from_payload(payload: dict, seed: str) -> DeckInstancePayload:
    if not isinstance(payload, dict):
        raise PrimitiveError(f"Deck instance {seed} payload must be a dictionary")
    try:
        return DeckInstancePayload.model_validate(payload)
    except pydantic.ValidationError as exc:
        raise PrimitiveError(f"Invalid persisted deck instance {seed}: {exc}") from exc


def _resolve_persisted_instance(
    store: PrimitiveStore, payload: dict, seed: str
) -> tuple[DeckDefinition, DeckRuntimeState]:
    instance = _instance_from_payload(payload, seed)
    definition_payload = store.get_definition("decks", instance.definition)
    if definition_payload is None:
        raise PrimitiveError(f"Deck definition not found: {instance.definition}")
    definition = DeckDefinition.model_validate(definition_payload)
    _validate_runtime_state(instance.runtime, definition, seed)
    return definition, instance.runtime


def _persist_deck_state(
    store: PrimitiveStore,
    ref: PrimitiveRef,
    definition: DeckDefinition,
    state: DeckRuntimeState,
) -> None:
    payload = DeckInstancePayload(
        definition=definition.id,
        runtime=state,
    ).model_dump(mode="json")
    store.set_runtime_primitive(ref, payload)


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
        if not conditions_match(scene, card.conditions):
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
