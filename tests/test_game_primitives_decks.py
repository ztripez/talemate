"""Tests for Game Primitives decks."""

from __future__ import annotations

import json

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
from talemate.context import ActiveScene
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.decks import DeckEngine
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


class FixedRng:
    """Deterministic random source for weighted deck tests."""

    def __init__(self, randoms: list[float]):
        self.randoms = list(randoms)

    def random(self) -> float:
        return self.randoms.pop(0)


def test_sample_mode_does_not_deplete_cards():
    """Sample decks select with replacement and keep piles empty."""
    scene = Scene()
    deck = {
        "id": "sample-deck",
        "name": "Sample Deck",
        "mode": "sample",
        "cards": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
        ],
    }
    engine = DeckEngine(FixedRng([0.0, 0.0]))

    first = engine.draw(scene, deck)
    second = engine.draw(scene, deck)
    state = PrimitiveStore.for_scene(scene).get_primitive(
        "scene:main/decks/sample-deck"
    )

    assert first.result_id == "a"
    assert second.result_id == "a"
    assert state["runtime"]["draw_pile"] == []
    assert state["runtime"]["discard"] == []


def test_draw_mode_moves_drawn_card_to_discard():
    """Draw decks remove the selected card from draw pile and discard it."""
    scene = Scene()
    deck = {
        "id": "draw-deck",
        "name": "Draw Deck",
        "mode": "draw",
        "cards": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
        ],
    }

    result = DeckEngine().draw(scene, deck)
    state = PrimitiveStore.for_scene(scene).get_primitive("scene:main/decks/draw-deck")

    assert result.result_id in {"a", "b"}
    assert result.result_id in state["runtime"]["discard"]
    assert result.result_id not in state["runtime"]["draw_pile"]


def test_bag_mode_respects_weights_and_avoid_recent():
    """Bag decks draw by weight and relax recent avoidance only when necessary."""
    scene = Scene()
    deck = {
        "id": "bag-deck",
        "name": "Bag Deck",
        "mode": "bag",
        "cards": [
            {"id": "a", "label": "A", "weight": 10},
            {"id": "b", "label": "B", "weight": 1},
        ],
    }
    engine = DeckEngine(FixedRng([0.0, 0.0]))

    first = engine.draw(scene, deck)
    second = engine.draw(scene, deck, options={"avoid_recent": 1})

    assert first.result_id == "a"
    assert second.result_id == "b"
    assert second.debug["relaxed_avoid_recent"] is False


def test_bag_weighted_selection_can_pick_second_card():
    """Bag mode uses weights rather than list order for selection."""
    scene = Scene()
    deck = {
        "id": "weighted-deck",
        "name": "Weighted Deck",
        "mode": "bag",
        "cards": [
            {"id": "a", "label": "A", "weight": 1},
            {"id": "b", "label": "B", "weight": 9},
        ],
    }

    result = DeckEngine(FixedRng([0.5])).draw(scene, deck)

    assert result.result_id == "b"


def test_bag_avoid_recent_relaxes_when_all_candidates_are_recent():
    """Avoid-recent filtering relaxes instead of failing when all cards are recent."""
    scene = Scene()
    deck = {
        "id": "relax-deck",
        "name": "Relax Deck",
        "mode": "bag",
        "cards": [{"id": "a", "label": "A"}],
    }
    engine = DeckEngine(FixedRng([0.0, 0.0]))

    first = engine.draw(scene, deck)
    second = engine.draw(scene, deck, options={"avoid_recent": 1})

    assert first.result_id == "a"
    assert second.result_id == "a"
    assert second.debug["relaxed_avoid_recent"] is True


def test_physical_mode_maintains_order_until_reset():
    """Physical decks draw in stable order and reset to the original order."""
    scene = Scene()
    deck = {
        "id": "physical-deck",
        "name": "Physical Deck",
        "mode": "physical",
        "cards": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
        ],
    }
    engine = DeckEngine()

    first = engine.draw(scene, deck)
    second = engine.draw(scene, deck)
    reset_state = engine.reset(scene, deck)

    assert [first.result_id, second.result_id] == ["a", "b"]
    assert reset_state.draw_pile == ["a", "b"]
    assert reset_state.discard == []


def test_physical_shuffle_persists_draw_pile_state():
    """Physical deck shuffle updates the persisted draw pile until reset."""
    scene = Scene()
    deck = {
        "id": "shuffle-deck",
        "name": "Shuffle Deck",
        "mode": "physical",
        "cards": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
            {"id": "c", "label": "C"},
        ],
    }
    engine = DeckEngine()

    shuffled = engine.shuffle(scene, deck)
    peeked = engine.peek(scene, deck)
    reset = engine.reset(scene, deck)

    assert sorted(shuffled.draw_pile) == ["a", "b", "c"]
    assert peeked["runtime"]["draw_pile"] == shuffled.draw_pile
    assert reset.draw_pile == ["a", "b", "c"]


def test_deck_tag_and_condition_filtering():
    """Deck draws apply include/exclude tags and card conditions."""
    scene = Scene()
    scene.game_state.set_var("enabled", True)
    deck = {
        "id": "filter-deck",
        "name": "Filter Deck",
        "mode": "sample",
        "cards": [
            {"id": "blocked-tag", "label": "Blocked", "tags": ["portrait", "blocked"]},
            {
                "id": "match",
                "label": "Match",
                "tags": ["portrait"],
                "conditions": [
                    {
                        "conditions": [
                            {"kind": "path", "path": "enabled", "operator": "is_true"}
                        ]
                    }
                ],
            },
            {"id": "wrong-tag", "label": "Wrong", "tags": ["landscape"]},
        ],
    }

    result = DeckEngine(FixedRng([0.0])).draw(
        scene,
        deck,
        options={"include_tags": ["portrait"], "exclude_tags": ["blocked"]},
    )

    assert result.result_id == "match"
    assert result.debug["filtered"] == ["match"]


def test_deck_false_conditions_exclude_cards():
    """Cards with false condition groups are excluded from selection."""
    scene = Scene()
    scene.game_state.set_var("enabled", False)
    deck = {
        "id": "condition-deck",
        "name": "Condition Deck",
        "mode": "sample",
        "cards": [
            {
                "id": "blocked",
                "label": "Blocked",
                "weight": 100,
                "conditions": [
                    {
                        "conditions": [
                            {"kind": "path", "path": "enabled", "operator": "is_true"}
                        ]
                    }
                ],
            },
            {"id": "open", "label": "Open", "weight": 1},
        ],
    }

    result = DeckEngine(FixedRng([0.0])).draw(scene, deck)

    assert result.result_id == "open"
    assert result.debug["filtered"] == ["open"]


def test_deck_cooldown_excludes_recently_drawn_card():
    """Card cooldowns exclude a card for following draw operations."""
    scene = Scene()
    deck = {
        "id": "cooldown-deck",
        "name": "Cooldown Deck",
        "mode": "bag",
        "cards": [
            {"id": "a", "label": "A", "weight": 10, "cooldown_turns": 1},
            {"id": "b", "label": "B", "weight": 1},
        ],
    }
    engine = DeckEngine(FixedRng([0.0, 0.0, 0.0]))

    first = engine.draw(scene, deck)
    second = engine.draw(scene, deck)
    third = engine.draw(scene, deck)

    assert first.result_id == "a"
    assert second.result_id == "b"
    assert third.result_id == "a"


def test_deck_no_candidate_error_is_visible():
    """Deck draws fail visibly when all candidates are filtered out."""
    scene = Scene()
    deck = {
        "id": "empty-deck",
        "name": "Empty Deck",
        "mode": "sample",
        "cards": [{"id": "a", "label": "A", "tags": ["portrait"]}],
    }

    with pytest.raises(Exception, match="no drawable cards"):
        DeckEngine().draw(scene, deck, options={"include_tags": ["landscape"]})


def test_persisted_runtime_state_continues_across_engine_instances():
    """Persisted physical deck state makes repeated draws deterministic."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "physical-definition",
        {
            "id": "physical-definition",
            "name": "Physical Definition",
            "mode": "physical",
            "cards": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
        },
    )

    first = DeckEngine().draw(
        scene, "physical-definition", anchor="object:Tarot", instance_id="tarot"
    )
    second = DeckEngine().draw(scene, "object:Tarot/decks/tarot")
    ledger = [entry for entry in store.recent_ledger(5) if entry["op"] == "deck.draw"]

    assert [first.result_id, second.result_id] == ["a", "b"]
    assert len(ledger) == 2
    assert ledger[-1]["output"]["card_id"] == "b"


async def test_deck_draw_node_returns_json_serializable_output():
    """The Draw node exposes deck selections to graph execution."""
    scene = Scene()
    with ActiveScene(scene):
        node_cls = get_node("primitives/decks/Draw")
    node = node_cls()

    outputs = await run_node(
        node,
        scene=scene,
        inputs={
            "deck": {
                "id": "node-deck",
                "name": "Node Deck",
                "mode": "physical",
                "cards": [
                    {"id": "only", "label": "Only", "variables": {"pose": "still"}}
                ],
            }
        },
    )

    assert outputs["card_id"] == "only"
    assert outputs["label"] == "Only"
    assert outputs["variables"] == {"pose": "still"}
    json.dumps(outputs["result"])
