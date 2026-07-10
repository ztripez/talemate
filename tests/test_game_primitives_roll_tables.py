"""Tests for Game Primitives roll tables and selection results."""

from __future__ import annotations

import json

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
from talemate.context import ActiveScene
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.roll_tables import (
    RollTableDefinition,
    RollTableEngine,
    parse_dice,
    parse_range,
)
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


class FixedRng:
    """Deterministic random source for roll table tests."""

    def __init__(
        self, rolls: list[int] | None = None, randoms: list[float] | None = None
    ):
        self.rolls = list(rolls or [])
        self.randoms = list(randoms or [])

    def randint(self, start: int, end: int) -> int:
        value = self.rolls.pop(0)
        assert start <= value <= end
        return value

    def random(self) -> float:
        return self.randoms.pop(0)


def test_dice_and_range_parsing_validate_mvp_shapes():
    """Dice and range parsers accept MVP syntax and reject invalid values."""
    assert parse_dice("1d6") == (1, 6)
    assert parse_dice("2d6") == (2, 6)
    assert parse_range(1) == (1, 1)
    assert parse_range("2-4") == (2, 4)

    for dice in ["", "d6", "1d", "0d6", "1d0", "1d20+2"]:
        with pytest.raises(ValueError):
            parse_dice(dice)
    for row_range in [True, "4-2", "a-b"]:
        with pytest.raises(ValueError):
            parse_range(row_range)


def test_roll_table_definition_rejects_overlapping_ranges():
    """Dice roll table definitions fail loudly on overlapping row ranges."""
    with pytest.raises(ValueError):
        RollTableDefinition.model_validate(
            {
                "id": "reaction",
                "name": "Reaction",
                "dice": "1d6",
                "rows": [
                    {"id": "low", "label": "Low", "range": "1-3"},
                    {"id": "mid", "label": "Mid", "range": "3-5"},
                ],
            }
        )


def test_roll_table_definition_rejects_duplicate_row_ids():
    with pytest.raises(ValueError, match="row ids must be unique"):
        RollTableDefinition.model_validate(
            {
                "id": "duplicate",
                "name": "Duplicate",
                "mode": "weighted",
                "rows": [
                    {"id": "same", "label": "First", "weight": 1},
                    {"id": "same", "label": "Second", "weight": 1},
                ],
            }
        )


def test_dice_roll_applies_active_modifiers_and_records_ledger():
    """Dice tables include raw rolls, modifiers, final total, result, and ledger."""
    scene = Scene()
    scene.game_state.set_var("bonus", True)
    scene.game_state.set_var("inactive_bonus", False)
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "modifiers",
        "bonus",
        {
            "id": "bonus",
            "label": "Bonus",
            "applies_to": "reaction",
            "when": [
                {
                    "conditions": [
                        {"kind": "path", "path": "bonus", "operator": "is_true"}
                    ]
                }
            ],
            "add": 2,
        },
    )
    store.set_definition(
        "modifiers",
        "inactive_bonus",
        {
            "id": "inactive_bonus",
            "label": "Inactive Bonus",
            "applies_to": "reaction",
            "when": [
                {
                    "conditions": [
                        {
                            "kind": "path",
                            "path": "inactive_bonus",
                            "operator": "is_true",
                        }
                    ]
                }
            ],
            "add": 10,
        },
    )
    table = {
        "id": "reaction",
        "name": "Reaction",
        "dice": "1d6",
        "modifiers": ["bonus", "inactive_bonus"],
        "rows": [
            {"id": "low", "label": "Low", "range": "1-3"},
            {"id": "high", "label": "High", "range": "4-6"},
        ],
    }

    result = RollTableEngine(FixedRng(rolls=[3])).roll(
        scene, table, context={"source": "unit-test"}
    )

    assert result.result_id == "high"
    assert result.label == "High"
    assert result.debug["raw"] == 3
    assert result.debug["final"] == 5
    assert result.debug["modifiers"] == [
        {
            "id": "bonus",
            "label": "Bonus",
            "value": 2,
            "active": True,
            "reason": "active",
        },
        {
            "id": "inactive_bonus",
            "label": "Inactive Bonus",
            "value": 0,
            "active": False,
            "reason": "inactive",
        },
    ]
    assert result.debug["context"] == {"source": "unit-test"}
    roll_entry = store.recent_ledger(1)[0]
    assert roll_entry["op"] == "roll_table.roll"
    assert roll_entry["output"]["raw"] == 3
    assert roll_entry["output"]["final"] == 5
    assert roll_entry["output"]["result_id"] == "high"
    assert roll_entry["input"]["context"] == {"source": "unit-test"}


def test_weighted_roll_excludes_condition_failed_rows():
    """Weighted tables filter failed condition rows before selection."""
    scene = Scene()
    scene.game_state.set_var("enabled", False)
    table = {
        "id": "weighted",
        "name": "Weighted",
        "mode": "weighted",
        "rows": [
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

    result = RollTableEngine(FixedRng(randoms=[0.0])).roll(scene, table)

    assert result.result_id == "open"
    assert result.debug["total_weight"] == 1.0
    assert result.debug["inactive_rows"] == ["blocked"]


def test_roll_resolves_canonical_anchored_instance_payload():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "roll_tables",
        "weather",
        {
            "id": "weather",
            "name": "Weather",
            "mode": "weighted",
            "rows": [{"id": "sun", "label": "Sunny", "weight": 1}],
        },
    )
    store.set_runtime_primitive(
        "scene:main/roll_tables/local-weather", {"definition": "weather"}
    )

    result = RollTableEngine(FixedRng(randoms=[0.0])).roll(
        scene, "scene:main/roll_tables/local-weather"
    )

    assert result.result_id == "sun"
    assert result.source_id == "scene:main/roll_tables/local-weather"


def test_roll_resolves_strict_legacy_value_payload():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_runtime_primitive(
        "scene:main/roll_tables/weather",
        {
            "value": {
                "id": "weather",
                "name": "Weather",
                "mode": "weighted",
                "rows": [{"id": "sun", "label": "Sunny", "weight": 1}],
            }
        },
    )

    result = RollTableEngine(FixedRng(randoms=[0.0])).roll(
        scene, "scene:main/roll_tables/weather"
    )

    assert result.result_id == "sun"


def test_roll_rejects_unknown_legacy_value_payload_fields():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_runtime_primitive(
        "scene:main/roll_tables/weather",
        {
            "value": {
                "id": "weather",
                "name": "Weather",
                "mode": "weighted",
                "rows": [{"id": "sun", "label": "Sunny", "weight": 1}],
            },
            "unknown": True,
        },
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        RollTableEngine(FixedRng(randoms=[0.0])).roll(
            scene, "scene:main/roll_tables/weather"
        )


def test_no_matching_dice_row_returns_clear_debug_error():
    """A final dice total outside all row ranges raises a clear error."""
    scene = Scene()

    with pytest.raises(Exception, match="no matching row"):
        RollTableEngine(FixedRng(rolls=[6])).roll(
            scene,
            {
                "id": "gapped",
                "name": "Gapped",
                "dice": "1d6",
                "rows": [{"id": "only-one", "label": "Only One", "range": 1}],
            },
        )


def test_dice_range_matching_includes_boundaries():
    """Inclusive range boundaries match during actual roll resolution."""
    scene = Scene()
    table = {
        "id": "boundary",
        "name": "Boundary",
        "dice": "1d6",
        "rows": [{"id": "middle", "label": "Middle", "range": "2-4"}],
    }

    low = RollTableEngine(FixedRng(rolls=[2])).roll(scene, table)
    high = RollTableEngine(FixedRng(rolls=[4])).roll(scene, table)

    assert low.result_id == "middle"
    assert high.result_id == "middle"


def test_roll_can_optionally_apply_row_effects():
    """Roll table selections can apply row effects through the common engine."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)

    result = RollTableEngine(FixedRng(rolls=[1])).roll(
        scene,
        {
            "id": "effectful",
            "name": "Effectful",
            "dice": "1d6",
            "rows": [
                {
                    "id": "hit",
                    "label": "Hit",
                    "range": "1-6",
                    "effects": [
                        {"op": "inc", "target": "scene:main/meters/tension", "by": 2}
                    ],
                }
            ],
        },
        apply_effects=True,
    )

    assert result.result_id == "hit"
    assert store.get_primitive("scene:main/meters/tension") == {"value": 2}
    assert result.debug["applied_effects"]["ok"] is True


def test_roll_omits_effect_application_by_default():
    """Rolls return row effects without mutating when apply_effects is false."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)

    result = RollTableEngine(FixedRng(rolls=[1])).roll(
        scene,
        {
            "id": "effectful",
            "name": "Effectful",
            "dice": "1d6",
            "rows": [
                {
                    "id": "hit",
                    "label": "Hit",
                    "range": "1-6",
                    "effects": [
                        {"op": "inc", "target": "scene:main/meters/tension", "by": 2}
                    ],
                    "variables": {"severity": "minor"},
                }
            ],
        },
    )

    assert result.effects[0].op == "inc"
    assert result.variables == {"severity": "minor"}
    assert store.get_primitive("scene:main/meters/tension") is None


def test_preview_odds_supports_dice_and_weighted_tables():
    """Odds preview reports dice probabilities, weighted probabilities, and gaps."""
    scene = Scene()
    engine = RollTableEngine()

    dice_odds = engine.preview_odds(
        scene,
        {
            "id": "dice",
            "name": "Dice",
            "dice": "1d6",
            "rows": [{"id": "low", "label": "Low", "range": "1-3"}],
        },
    )
    weighted_odds = engine.preview_odds(
        scene,
        {
            "id": "weighted",
            "name": "Weighted",
            "mode": "weighted",
            "rows": [
                {"id": "a", "label": "A", "weight": 1},
                {"id": "b", "label": "B", "weight": 3},
            ],
        },
    )

    assert dice_odds["rows"][0]["probability"] == 0.5
    assert dice_odds["gaps"] == [[4, 6]]
    assert weighted_odds["total_weight"] == 4.0
    assert weighted_odds["rows"][1]["probability"] == 0.75


async def test_roll_table_node_returns_json_serializable_output():
    """The Roll node exposes roll table results to graph execution."""
    scene = Scene()
    with ActiveScene(scene):
        node_cls = get_node("primitives/roll_tables/Roll")
    node = node_cls()

    outputs = await run_node(
        node,
        scene=scene,
        inputs={
            "table": {
                "id": "node-table",
                "name": "Node Table",
                "dice": "1d1",
                "rows": [{"id": "only", "label": "Only", "range": 1}],
            }
        },
    )

    assert outputs["result_id"] == "only"
    assert outputs["label"] == "Only"
    assert outputs["result"]["source_type"] == "roll_table"
    json.dumps(outputs["result"])
