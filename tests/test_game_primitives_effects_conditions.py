"""Tests for Game Primitives effects and conditions."""

from __future__ import annotations

import copy

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
from talemate.context import ActiveScene
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.conditions import evaluate_condition_input
from talemate.game.primitives.effects import Effect, apply_effects
from talemate.game.primitives.schema import GAME_PRIMITIVES_KEY
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_effects_apply_primitive_value_operations_and_ledger():
    """Primitive effects mutate value payloads and record effect ledger entries."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    ref = "scene:main/meters/tension"

    result = apply_effects(
        store,
        [
            {"op": "set", "target": ref, "value": 2},
            {"op": "inc", "target": ref, "by": 3},
            {"op": "dec", "target": ref, "by": 1},
        ],
        reason="unit-test",
    )

    assert result.ok is True
    assert [item.previous for item in result.results] == [None, 2, 5]
    assert [item.current for item in result.results] == [2, 5, 4]
    assert store.get_primitive(ref) == {"value": 4}
    effect_entries = [
        entry for entry in store.recent_ledger(10) if entry["op"].startswith("effect.")
    ]
    assert [entry["op"] for entry in effect_entries] == [
        "effect.set",
        "effect.inc",
        "effect.dec",
    ]
    assert [entry["ref"] for entry in effect_entries] == [ref, ref, ref]
    assert [entry["message"] for entry in effect_entries] == ["unit-test"] * 3
    assert effect_entries[1]["input"] == {"op": "inc", "target": ref, "by": 3}
    assert effect_entries[1]["output"]["previous"] == 2
    assert effect_entries[1]["output"]["current"] == 5


def test_effects_unset_append_extend_and_tags():
    """List effects and anchor tag effects use deterministic semantics."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    list_ref = "character:Model/decks/poses"

    result = apply_effects(
        store,
        [
            {"op": "append", "target": list_ref, "value": "standing"},
            {"op": "extend", "target": list_ref, "value": ["seated", "profile"]},
            {"op": "add_tag", "target": "character:Model", "value": "relaxed"},
            {"op": "add_tag", "target": "character:Model", "value": "relaxed"},
            {"op": "remove_tag", "target": "character:Model", "value": "relaxed"},
            {"op": "unset", "target": list_ref},
        ],
    )

    assert result.ok is True
    assert result.results[1].current == ["standing", "seated", "profile"]
    assert result.results[3].previous == ["relaxed"]
    assert result.results[3].current == ["relaxed"]
    assert store.get_anchor("character:Model")["tags"] == []
    assert store.get_primitive(list_ref) is None
    effect_entries = [
        entry for entry in store.recent_ledger(20) if entry["op"].startswith("effect.")
    ]
    assert effect_entries[2]["anchor"] == "character:Model"
    assert effect_entries[2]["input"] == {
        "op": "add_tag",
        "target": "character:Model",
        "value": "relaxed",
    }
    assert effect_entries[2]["output"]["current"] == ["relaxed"]


def test_effects_stop_on_invalid_target_without_later_mutation():
    """Invalid effects fail clearly and stop the remaining batch."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)

    result = apply_effects(
        store,
        [
            {"op": "set", "target": "scene:main/meters/tension", "value": 1},
            {"op": "inc", "target": "not-a-primitive-ref", "by": 1},
            {"op": "set", "target": "scene:main/meters/after", "value": 99},
        ],
    )

    assert result.ok is False
    assert len(result.results) == 2
    assert result.results[0].ok is True
    assert result.results[1].ok is False
    assert store.get_primitive("scene:main/meters/tension") == {"value": 1}
    assert store.get_primitive("scene:main/meters/after") is None


def test_effects_validate_operation_payloads_and_missing_anchor_removal():
    """Effect models reject invalid operation payloads before mutation."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)

    with pytest.raises(ValueError):
        Effect.model_validate(
            {"op": "extend", "target": "scene:main/decks/poses", "value": "x"}
        )
    with pytest.raises(ValueError):
        Effect.model_validate(
            {"op": "inc", "target": "scene:main/meters/tension", "by": True}
        )

    result = apply_effects(
        store, {"op": "remove_tag", "target": "scene:missing", "value": "danger"}
    )

    assert result.ok is False
    assert "does not exist" in result.results[0].error
    assert store.get_anchor("scene:missing") is None


def test_conditions_evaluate_primitive_path_tags_and_groups():
    """Primitive conditions support primitive values, tags, and group OR logic."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    apply_effects(
        store,
        [
            {"op": "set", "target": "scene:main/meters/tension", "value": 4},
            {"op": "set", "target": "scene:main/meters/flag", "value": True},
            {"op": "add_tag", "target": "scene:main", "value": "danger"},
        ],
    )

    matches, debug = evaluate_condition_input(
        scene,
        [
            {
                "operator": "and",
                "conditions": [
                    {
                        "kind": "primitive",
                        "path": "scene:main/meters/tension",
                        "operator": ">=",
                        "value": 3,
                    },
                    {
                        "kind": "primitive",
                        "path": "scene:main/meters/flag",
                        "operator": "is_true",
                    },
                    {"kind": "anchor_has_tag", "anchor": "scene:main", "tag": "danger"},
                ],
            }
        ],
    )

    assert matches is True
    assert debug[0]["matches"] is True

    matches, debug = evaluate_condition_input(
        scene,
        [
            {
                "operator": "and",
                "conditions": [
                    {
                        "kind": "primitive",
                        "path": "scene:main/meters/tension",
                        "operator": ">",
                        "value": 10,
                    }
                ],
            },
            {
                "conditions": [
                    {
                        "kind": "anchor_missing_tag",
                        "anchor": "scene:main",
                        "tag": "safe",
                    }
                ]
            },
        ],
    )

    assert matches is True
    assert debug[0]["matches"] is False
    assert debug[1]["matches"] is True


def test_conditions_support_primitive_equality_null_and_intragroup_or():
    """Primitive conditions support equality, null checks, and OR groups."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    apply_effects(
        store, {"op": "set", "target": "scene:main/meters/tension", "value": 4}
    )

    matches, debug = evaluate_condition_input(
        scene,
        {
            "operator": "or",
            "conditions": [
                {
                    "kind": "primitive",
                    "path": "scene:main/meters/tension",
                    "operator": "==",
                    "value": "5",
                },
                {
                    "kind": "primitive",
                    "path": "scene:main/meters/missing",
                    "operator": "is_null",
                },
            ],
        },
    )

    assert matches is True
    assert debug[0]["operator"] == "or"
    assert debug[0]["conditions"][0]["matches"] is False
    assert debug[0]["conditions"][1]["matches"] is True

    matches, debug = evaluate_condition_input(
        scene,
        {
            "kind": "primitive",
            "path": "scene:main/meters/tension",
            "operator": "==",
            "value": "4",
        },
    )

    assert matches is True
    assert debug[0]["conditions"][0]["matches"] is True


def test_primitive_conditions_do_not_mutate_existing_store():
    """Primitive-aware condition reads leave anchors, values, and ledger intact."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    apply_effects(
        store,
        [
            {"op": "set", "target": "scene:main/meters/tension", "value": 4},
            {
                "op": "set",
                "target": "scene:main/clocks/warmup",
                "value": {"value": 2, "target": 3},
            },
            {"op": "add_tag", "target": "scene:main", "value": "danger"},
        ],
    )
    before = copy.deepcopy(store.root)

    matches, _ = evaluate_condition_input(
        scene,
        {
            "operator": "and",
            "conditions": [
                {
                    "kind": "primitive",
                    "path": "scene:main/meters/tension",
                    "operator": ">=",
                    "value": 4,
                },
                {
                    "kind": "meter",
                    "anchor": "scene:main",
                    "dimension": "tension",
                    "operator": "==",
                    "value": 4,
                },
                {
                    "kind": "clock_complete",
                    "path": "scene:main/clocks/warmup",
                    "operator": "is_false",
                },
                {"kind": "anchor_has_tag", "anchor": "scene:main", "tag": "danger"},
            ],
        },
    )

    assert matches is True
    assert store.root == before


def test_path_only_conditions_do_not_initialize_primitive_store():
    """Read-only path conditions do not create the Game Primitives root."""
    scene = Scene()
    scene.game_state.set_var("score", 5)
    assert GAME_PRIMITIVES_KEY not in scene.game_state.variables

    matches, debug = evaluate_condition_input(
        scene, {"kind": "path", "path": "score", "operator": "==", "value": 5}
    )

    assert matches is True
    assert debug[0]["conditions"][0]["actual"] == 5
    assert GAME_PRIMITIVES_KEY not in scene.game_state.variables


def test_missing_anchor_tag_conditions_fail_with_debug():
    """Missing anchors do not satisfy missing-tag checks silently."""
    scene = Scene()

    matches, debug = evaluate_condition_input(
        scene,
        {"kind": "anchor_missing_tag", "anchor": "scene:missing", "tag": "safe"},
    )

    assert matches is False
    assert debug[0]["conditions"][0]["message"] == "anchor missing"


def test_effect_runtime_failures_do_not_mutate_or_append_effect_ledger():
    """Mutation-time effect failures leave existing values and ledger unchanged."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    apply_effects(
        store,
        [
            {"op": "set", "target": "scene:main/meters/tension", "value": "high"},
            {"op": "set", "target": "scene:main/decks/poses", "value": "standing"},
        ],
    )
    before = copy.deepcopy(store.root)

    inc_result = apply_effects(
        store, {"op": "inc", "target": "scene:main/meters/tension", "by": 1}
    )
    append_result = apply_effects(
        store, {"op": "append", "target": "scene:main/decks/poses", "value": "seated"}
    )

    assert inc_result.ok is False
    assert "must be numeric" in inc_result.results[0].error
    assert append_result.ok is False
    assert "must be a list" in append_result.results[0].error
    assert store.root == before


def test_conditions_support_game_state_meter_relationship_and_clock():
    """Condition kinds resolve game-state paths and anchored primitive refs."""
    scene = Scene()
    scene.game_state.set_var("score", 5)
    store = PrimitiveStore.for_scene(scene)
    apply_effects(
        store,
        [
            {"op": "set", "target": "character:Model/meters/confidence", "value": 3},
            {
                "op": "set",
                "target": "relationship:Model->Photographer/meters/trust",
                "value": 2,
            },
            {
                "op": "set",
                "target": "scene:main/clocks/warmup",
                "value": {"value": 4, "target": 4},
            },
        ],
    )

    matches, _ = evaluate_condition_input(
        scene,
        [
            {"kind": "path", "path": "score", "operator": "==", "value": "5"},
            {
                "kind": "meter",
                "anchor": "character:Model",
                "dimension": "confidence",
                "operator": ">=",
                "value": 3,
            },
            {
                "kind": "relationship",
                "anchor": "relationship:Model->Photographer",
                "dimension": "trust",
                "operator": "==",
                "value": 2,
            },
            {
                "kind": "clock_complete",
                "path": "scene:main/clocks/warmup",
                "operator": "is_true",
            },
        ],
    )

    assert matches is True


async def test_apply_effects_node_runs_against_active_scene():
    """The ApplyEffects node exposes the effect runtime to graphs."""
    scene = Scene()
    with ActiveScene(scene):
        node_cls = get_node("primitives/effects/ApplyEffects")
    node = node_cls()

    outputs = await run_node(
        node,
        scene=scene,
        inputs={
            "effects": [
                {"op": "set", "target": "scene:main/meters/tension", "value": 7}
            ],
            "reason": "node-test",
        },
    )

    assert outputs["ok"] is True
    assert outputs["results"][0]["current"] == 7
    assert PrimitiveStore.for_scene(scene).get_primitive(
        "scene:main/meters/tension"
    ) == {"value": 7}


async def test_evaluate_condition_node_runs_against_active_scene():
    """The EvaluateCondition node exposes condition evaluation to graphs."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    apply_effects(
        store, {"op": "set", "target": "scene:main/meters/tension", "value": 7}
    )
    with ActiveScene(scene):
        node_cls = get_node("primitives/conditions/EvaluateCondition")
    node = node_cls()

    outputs = await run_node(
        node,
        scene=scene,
        inputs={
            "condition": {
                "kind": "primitive",
                "path": "scene:main/meters/tension",
                "operator": ">=",
                "value": 7,
            }
        },
    )

    assert outputs["matches"] is True
    assert outputs["debug"][0]["matches"] is True
