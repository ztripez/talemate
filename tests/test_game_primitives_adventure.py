"""Tests for the Game Primitives adventure and story-scene graph."""

from __future__ import annotations

import copy

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.adventure import (
    AdventureEngine,
    current_adventure_message_metadata,
    tag_message_with_current_adventure,
)
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.store import PrimitiveStore
from talemate.scene_message import NarratorMessage
from talemate.tale_mate import Scene


def _adventure(*, blocked: bool = False, failing_effect: bool = False) -> dict:
    """Return a two-scene adventure fixture with observable ordered effects."""
    transition_conditions = (
        [{"operator": "and", "conditions": [{"kind": "never"}]}] if blocked else []
    )
    destination_effects = [
        {"op": "append", "target": "scene:main/lists/order", "value": "scene-entry"}
    ]
    if failing_effect:
        destination_effects.append(
            {"op": "inc", "target": "scene:main/lists/order", "by": 1}
        )
    return {
        "id": "demo",
        "title": "Demo Adventure",
        "start_scene": "arrival",
        "scenes": {
            "arrival": {
                "id": "arrival",
                "title": "Arrival",
                "goals": ["Establish the setting"],
                "exit_effects": [
                    {
                        "op": "append",
                        "target": "scene:main/lists/order",
                        "value": "scene-exit",
                    }
                ],
            },
            "main": {
                "id": "main",
                "title": "Main Scene",
                "intro": "The main scene begins.",
                "entry_effects": destination_effects,
            },
        },
        "transitions": {
            "begin": {
                "id": "begin",
                "from_scene": "arrival",
                "to_scene": "main",
                "label": "Begin the main scene",
                "conditions": transition_conditions,
                "carry_anchors": ["character:Hero"],
                "exit_effects": [
                    {
                        "op": "append",
                        "target": "scene:main/lists/order",
                        "value": "transition-exit",
                    }
                ],
                "entry_effects": [
                    {
                        "op": "append",
                        "target": "scene:main/lists/order",
                        "value": "transition-entry",
                    }
                ],
            }
        },
    }


def _active_scene(*, blocked: bool = False, failing_effect: bool = False) -> Scene:
    """Create a scene with one stored and active adventure."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "adventures", "demo", _adventure(blocked=blocked, failing_effect=failing_effect)
    )
    store.set_primitive("scene:main/lists/order", {"value": []})
    AdventureEngine().activate(scene, "demo")
    return scene


def test_activate_and_get_current_story_scene():
    """Adventure activation persists initial state and resolves its start scene."""
    scene = _active_scene()
    engine = AdventureEngine()

    assert engine.get_current(scene).id == "arrival"
    assert engine.get_state(scene).visited == ["arrival"]

    with pytest.raises(PrimitiveError, match="already active"):
        engine.activate(scene, "demo")


def test_list_and_reject_condition_failed_transition():
    """Failed transition conditions produce unavailable and rejection results."""
    scene = _active_scene(blocked=True)
    engine = AdventureEngine()

    availability = engine.list_transitions(scene)
    result = engine.take_transition(scene, "begin")

    assert availability[0].available is False
    assert availability[0].reasons == ["Transition conditions are not met"]
    assert result.ok is False
    assert engine.get_current(scene).id == "arrival"


def test_transition_availability_reads_primitive_clock_state():
    """Adventure conditions resolve primitive clock state through the shared engine."""
    scene = _active_scene()
    store = PrimitiveStore.for_scene(scene)
    definition = _adventure()
    definition["transitions"]["begin"]["conditions"] = [
        {
            "operator": "and",
            "conditions": [
                {
                    "kind": "clock_complete",
                    "path": "story_scene:arrival/clocks/ready",
                }
            ],
        }
    ]
    store.set_definition("adventures", "demo", definition)
    store.set_primitive(
        "story_scene:arrival/clocks/ready",
        {"id": "ready", "value": 1, "max": 2},
    )
    engine = AdventureEngine()

    assert engine.can_take_transition(scene, "begin").available is False
    store.set_primitive(
        "story_scene:arrival/clocks/ready",
        {"id": "ready", "value": 2, "max": 2},
    )
    assert engine.can_take_transition(scene, "begin").available is True


def test_successful_transition_is_ordered_and_persisted():
    """A successful transition applies effects in order and updates all runtime logs."""
    scene = _active_scene()
    engine = AdventureEngine()

    result = engine.take_transition(scene, "begin")
    state = engine.get_state(scene)
    store = PrimitiveStore.for_scene(scene)

    assert result.ok is True
    assert result.intro == "The main scene begins."
    assert store.get_primitive("scene:main/lists/order")["value"] == [
        "scene-exit",
        "transition-exit",
        "transition-entry",
        "scene-entry",
    ]
    assert state.current_story_scene == "main"
    assert state.visited == ["arrival", "main"]
    assert state.completed == ["arrival"]
    assert state.transition_log[0].carry_anchors == ["character:Hero"]
    assert store.recent_ledger(1)[0]["op"] == "adventure.transition"


def test_failed_effect_rolls_back_entire_transition():
    """A late effect failure leaves primitive and adventure runtime state unchanged."""
    scene = _active_scene(failing_effect=True)
    engine = AdventureEngine()
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)

    result = engine.take_transition(scene, "begin")

    assert result.ok is False
    assert PrimitiveStore.for_scene(scene).root == before
    assert [effect.ok for effect in result.effects] == [True, True, True, True, False]


def test_current_context_and_message_metadata_are_prompt_safe():
    """Current-scene prose and namespaced message metadata expose only public state."""
    scene = _active_scene(blocked=True)
    engine = AdventureEngine()
    message = NarratorMessage("Hello")

    context = engine.render_current_context(scene)
    tag_message_with_current_adventure(scene, message)

    assert "Current adventure: Demo Adventure" in context
    assert "Establish the setting" in context
    assert "Begin the main scene (currently unavailable)" in context
    assert "kind" not in context
    assert current_adventure_message_metadata(scene) == {
        "game_primitives": {
            "adventure_id": "demo",
            "story_scene_id": "arrival",
        }
    }
    assert message.meta == current_adventure_message_metadata(scene)


def test_scene_without_adventure_returns_empty_results_without_mutation():
    """Adventure reads on a plain scene remain empty and do not create a store."""
    scene = Scene()
    engine = AdventureEngine()
    message = NarratorMessage("Hello", meta={"existing": True})

    assert engine.get_current(scene) is None
    assert engine.list_transitions(scene) == []
    assert engine.render_current_context(scene) == ""
    assert engine.can_take_transition(scene, "missing").reasons == [
        "No active adventure"
    ]
    assert engine.take_transition(scene, "missing").error == "No active adventure"
    assert current_adventure_message_metadata(scene) == {}
    tag_message_with_current_adventure(scene, message)
    assert message.meta == {"existing": True}
    assert "game_primitives" not in scene.game_state.variables


@pytest.mark.asyncio
async def test_adventure_nodes_are_registered_and_delegate_to_engine():
    """Adventure wrappers serialize current state and successful transition output."""
    scene = _active_scene()
    current_cls = get_node("primitives/adventure/GetCurrentScene")
    list_cls = get_node("primitives/adventure/ListTransitions")
    can_take_cls = get_node("primitives/adventure/CanTakeTransition")
    transition_cls = get_node("primitives/adventure/TakeTransition")
    render_cls = get_node("primitives/adventure/RenderCurrentSceneContext")

    current = await run_node(current_cls(), scene=scene)
    transitions = await run_node(list_cls(), scene=scene)
    availability = await run_node(
        can_take_cls(), scene=scene, inputs={"transition_id": "begin"}
    )
    rendered = await run_node(render_cls(), scene=scene)
    transition = await run_node(
        transition_cls(),
        scene=scene,
        inputs={"transition_id": "begin", "render_intro": False},
    )

    assert current["scene"]["id"] == "arrival"
    assert transitions["transitions"][0]["id"] == "begin"
    assert availability["available"] is True
    assert "Current story scene: Arrival" in rendered["context"]
    assert transition["ok"] is True
    assert transition["from_scene"] == "arrival"
    assert transition["to_scene"] == "main"
    assert transition["intro"] == ""
