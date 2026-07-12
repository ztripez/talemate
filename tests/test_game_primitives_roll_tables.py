"""Tests for Game Primitives roll tables and selection results."""

from __future__ import annotations

import json
import threading

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
import talemate.game.engine.nodes.primitives.roll_tables as roll_table_nodes
import talemate.game.primitives.roll_tables as roll_table_primitives
from talemate.context import ActiveScene
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.primitive_payloads import RollTableInstancePayload
from talemate.game.primitives.roll_tables import (
    MAX_DICE_COUNT,
    MAX_DICE_SIDES,
    RollTableDefinition,
    RollTableEngine,
    _range_gaps,
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


@pytest.mark.parametrize(
    ("dice", "message"),
    [
        (f"{MAX_DICE_COUNT + 1}d6", "Dice count cannot exceed 100"),
        (f"1d{MAX_DICE_SIDES + 1}", "Dice sides cannot exceed 1000"),
    ],
)
def test_roll_table_definition_rejects_excessive_dice(dice, message):
    with pytest.raises(ValueError, match=message):
        RollTableDefinition.model_validate(
            {
                "id": "excessive",
                "name": "Excessive",
                "dice": dice,
                "rows": [{"id": "result", "label": "Result", "range": 1}],
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


def test_roll_table_instance_payload_contains_only_definition_id():
    payload = RollTableInstancePayload(definition=" weather ")

    assert payload.model_dump(mode="json") == {"definition": "weather"}
    with pytest.raises(ValueError):
        RollTableInstancePayload.model_validate(
            {
                "definition": {
                    "id": "weather",
                    "name": "Weather",
                    "mode": "weighted",
                    "rows": [{"id": "sun", "label": "Sunny", "weight": 1}],
                }
            }
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
                        {"op": "inc", "target": "scene:main/flags/tension", "by": 2}
                    ],
                }
            ],
        },
        apply_effects=True,
    )

    assert result.result_id == "hit"
    assert store.get_primitive("scene:main/flags/tension") == {"value": 2}
    assert result.debug["applied_effects"]["ok"] is True


def test_failed_roll_effects_restore_state_and_all_ledger_entries():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_runtime_primitive("scene:main/flags/tension", {"value": 10})
    store.set_runtime_primitive("scene:main/lists/events", {"value": "not-a-list"})
    previous_root = json.loads(json.dumps(store.root))

    with pytest.raises(PrimitiveError, match="Roll table effects failed"):
        RollTableEngine(FixedRng(rolls=[1])).roll(
            scene,
            {
                "id": "effectful",
                "name": "Effectful",
                "dice": "1d1",
                "rows": [
                    {
                        "id": "hit",
                        "label": "Hit",
                        "range": 1,
                        "effects": [
                            {
                                "op": "inc",
                                "target": "scene:main/flags/tension",
                                "by": 2,
                            },
                            {
                                "op": "append",
                                "target": "scene:main/lists/events",
                                "value": "event",
                            },
                        ],
                    }
                ],
            },
            apply_effects=True,
        )

    assert store.root == previous_root


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
                        {"op": "inc", "target": "scene:main/flags/tension", "by": 2}
                    ],
                    "variables": {"severity": "minor"},
                }
            ],
        },
    )

    assert result.effects[0].op == "inc"
    assert result.variables == {"severity": "minor"}
    assert store.get_primitive("scene:main/flags/tension") is None


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


def test_dice_gap_diagnostics_exclude_condition_failed_rows():
    scene = Scene()
    scene.game_state.set_var("enabled", False)
    table = {
        "id": "conditional",
        "name": "Conditional",
        "dice": "1d6",
        "rows": [
            {
                "id": "blocked",
                "label": "Blocked",
                "range": "1-3",
                "conditions": [
                    {
                        "conditions": [
                            {"kind": "path", "path": "enabled", "operator": "is_true"}
                        ]
                    }
                ],
            },
            {"id": "open", "label": "Open", "range": "4-6"},
        ],
    }

    result = RollTableEngine(FixedRng(rolls=[4])).roll(scene, table)
    odds = RollTableEngine().preview_odds(scene, table)

    assert result.result_id == "open"
    assert result.debug["inactive_rows"] == ["blocked"]
    assert result.debug["gaps"] == [[1, 3]]
    assert odds["inactive_rows"] == ["blocked"]
    assert odds["gaps"] == [[1, 3]]


def test_preview_odds_uses_exact_distribution_for_large_dice_pool():
    odds = RollTableEngine().preview_odds(
        Scene(),
        {
            "id": "large-pool",
            "name": "Large Pool",
            "dice": "20d20",
            "rows": [{"id": "all", "label": "All", "range": "20-400"}],
        },
    )

    assert odds["rows"][0]["outcomes"] == 20**20
    assert odds["rows"][0]["probability"] == 1.0


def test_range_gaps_operates_on_intervals_without_materializing_values():
    table = RollTableDefinition.model_validate(
        {
            "id": "intervals",
            "name": "Intervals",
            "dice": "1d6",
            "rows": [
                {"id": "low", "label": "Low", "range": "1-10"},
                {
                    "id": "high",
                    "label": "High",
                    "range": "999999991-1000000000",
                },
            ],
        }
    )

    assert _range_gaps(table.rows, 1, 1_000_000_000) == [[11, 999_999_990]]


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


async def test_preview_odds_node_runs_exact_computation_off_event_loop(monkeypatch):
    scene = Scene()
    with ActiveScene(scene):
        node_cls = get_node("primitives/roll_tables/PreviewOdds")
    node = node_cls()
    event_loop_thread = threading.get_ident()
    execution_threads = []
    computation_inputs = []
    compute_odds = roll_table_nodes._compute_odds_preview
    conditions_match = roll_table_primitives.conditions_match
    condition_threads = []

    def tracked_conditions_match(*args, **kwargs):
        condition_threads.append(threading.get_ident())
        return conditions_match(*args, **kwargs)

    def tracked_compute_odds(prepared):
        execution_threads.append(threading.get_ident())
        computation_inputs.append(prepared.model_dump(mode="json"))
        return compute_odds(prepared)

    monkeypatch.setattr(roll_table_nodes, "_compute_odds_preview", tracked_compute_odds)
    monkeypatch.setattr(
        roll_table_primitives, "conditions_match", tracked_conditions_match
    )

    outputs = await run_node(
        node,
        scene=scene,
        inputs={
            "table": {
                "id": "node-table",
                "name": "Node Table",
                "dice": "20d20",
                "rows": [{"id": "all", "label": "All", "range": "20-400"}],
            }
        },
    )

    assert execution_threads
    assert execution_threads[0] != event_loop_thread
    assert condition_threads
    assert set(condition_threads) == {event_loop_thread}
    assert computation_inputs == [
        {
            "source_id": "node-table",
            "mode": "dice",
            "dice": "20d20",
            "rows": [
                {
                    "id": "all",
                    "label": "All",
                    "weight": None,
                    "range": "20-400",
                }
            ],
            "inactive_rows": [],
        }
    ]
    assert outputs["odds"]["source_id"] == "node-table"
    assert outputs["odds"]["rows"][0]["outcomes"] == 20**20
    assert outputs["odds"]["rows"][0]["probability"] == 1.0
