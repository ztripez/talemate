"""Tests for Game Primitives prompt-context graph nodes."""

from __future__ import annotations

from _game_primitives_test_helpers import seed_prompt_attribute
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401 - loads node registration side effects
from talemate.agents.base import DynamicInstruction
from talemate.agents.conversation import ConversationAgentEmission
from talemate.agents.creator.assistant import ContextualGenerateEmission
from talemate.agents.narrator import NarratorAgentEmission
from talemate.character import Character
from talemate.game.engine.nodes.registry import get_node
from talemate.tale_mate import Scene


def _seed_scene_attribute(scene: Scene) -> None:
    """Store one prompt-visible scene attribute for injection tests."""
    seed_prompt_attribute(scene, "scene:main/attributes/weather")


async def test_render_relevant_context_node_outputs_dynamic_instruction():
    """Render node emits one typed instruction for non-empty primitive context."""
    scene = Scene()
    _seed_scene_attribute(scene)

    outputs = await run_node(
        get_node("primitives/render/RenderRelevantContext")(),
        scene=scene,
        inputs={"audience": "conversation"},
    )

    assert outputs["title"] == "Game Primitives - Relevant State"
    assert "Weather: Rainy" in outputs["content"]
    assert isinstance(outputs["instruction"], DynamicInstruction)


async def test_render_relevant_context_node_omits_empty_instruction():
    """Render node emits no instruction when relevant primitive context is empty."""
    outputs = await run_node(
        get_node("primitives/render/RenderRelevantContext")(),
        scene=Scene(),
        inputs={"audience": "conversation"},
    )

    assert outputs["content"] == ""
    assert outputs["instruction"] is None


async def test_conversation_injection_appends_titled_instruction():
    """Conversation injection appends relevant context to the emission list."""
    scene = Scene()
    _seed_scene_attribute(scene)
    event = ConversationAgentEmission(
        agent=object(),
        actor=None,
        character=Character(name="Model"),
        response="",
    )

    outputs = await run_node(
        get_node("primitives/render/InjectConversationContext")(),
        scene=scene,
        inputs={"event": event},
    )

    assert outputs["injected"] is True
    assert len(event.dynamic_instructions) == 1
    assert event.dynamic_instructions[0].title == "Game Primitives - Relevant State"
    assert "Weather: Rainy" in event.dynamic_instructions[0].content


async def test_narrator_injection_appends_titled_instruction():
    """Narrator injection appends scene-wide primitive context."""
    scene = Scene()
    _seed_scene_attribute(scene)
    event = NarratorAgentEmission(agent=object())

    outputs = await run_node(
        get_node("primitives/render/InjectNarratorContext")(),
        scene=scene,
        inputs={"event": event},
    )

    assert outputs["injected"] is True
    assert len(event.dynamic_instructions) == 1
    assert "Weather: Rainy" in event.dynamic_instructions[0].content


async def test_creator_injection_requires_character_focus():
    """Creator injection skips generic authoring and renders character-focused work."""
    scene = Scene()
    seed_prompt_attribute(
        scene,
        "character:Model/attributes/pose",
        "Relaxed",
    )
    generic = ContextualGenerateEmission(agent=object())
    focused = ContextualGenerateEmission(
        agent=object(), character=Character(name="Model")
    )
    node_cls = get_node("primitives/render/InjectCreatorContext")

    generic_outputs = await run_node(node_cls(), scene=scene, inputs={"event": generic})
    focused_outputs = await run_node(node_cls(), scene=scene, inputs={"event": focused})

    assert generic_outputs["injected"] is False
    assert generic.dynamic_instructions == []
    assert focused_outputs["injected"] is True
    assert "Pose: Relaxed" in focused.dynamic_instructions[0].content
