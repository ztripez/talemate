"""Tests for Game Primitives primitive attribute graph nodes."""

from __future__ import annotations

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401 - loads node registration side effects
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives import (
    AttributeResolution,
    AttributeResolver,
    AttributeSource,
)
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_attribute_public_exports_and_node_registration():
    """Primitive attributes are available through public exports and nodes."""
    assert AttributeResolver is not None
    assert AttributeSource is not None
    assert AttributeResolution is not None
    assert get_node("primitives/attributes/Get") is not None
    assert get_node("primitives/attributes/Render") is not None


async def test_attribute_nodes_set_resolve_and_render():
    """Attribute graph nodes store, resolve, and render primitive sources."""
    scene = Scene()
    set_node = get_node("primitives/attributes/Set")()
    resolve_node = get_node("primitives/attributes/Resolve")()
    render_node = get_node("primitives/attributes/Render")()

    set_outputs = await run_node(
        set_node,
        scene=scene,
        inputs={
            "ref": "character:Model/attributes/current_pose",
            "source": {
                "source": "literal",
                "render_policy": "prompt",
                "value": "Use a relaxed standing pose.",
            },
        },
    )
    resolve_outputs = await run_node(
        resolve_node,
        scene=scene,
        inputs={"ref": "character:Model/attributes/current_pose"},
    )
    render_outputs = await run_node(
        render_node,
        scene=scene,
        inputs={"ref": "character:Model/attributes/current_pose"},
    )

    assert set_outputs["source"]["id"] == "current_pose"
    assert resolve_outputs["value"] == "Use a relaxed standing pose."
    assert render_outputs["rendered"] == "Current Pose: Use a relaxed standing pose."


async def test_attribute_render_node_resolves_mutating_source_once():
    """Render node resolves a deck-backed attribute once and emits matching result."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "poses",
        {
            "id": "poses",
            "name": "Poses",
            "mode": "physical",
            "cards": [
                {"id": "first", "label": "First", "text": "First pose."},
                {"id": "second", "label": "Second", "text": "Second pose."},
            ],
        },
    )
    AttributeResolver().set(
        scene,
        "character:Model/attributes/current_pose",
        {
            "source": "deck",
            "ref": "poses",
            "render_policy": "prompt",
            "options": {
                "anchor": "character:Model",
                "result_field": "text",
            },
        },
    )
    render_node = get_node("primitives/attributes/Render")()

    outputs = await run_node(
        render_node,
        scene=scene,
        inputs={"ref": "character:Model/attributes/current_pose"},
    )
    deck_entries = [
        entry for entry in store.recent_ledger() if entry["op"] == "deck.draw"
    ]

    assert outputs["rendered"] == "First pose."
    assert outputs["result"]["value"] == "First pose."
    assert len(deck_entries) == 1


async def test_attribute_render_node_invalid_audience_does_not_mutate_deck():
    """Render node validates audience before resolving mutating sources."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "poses",
        {
            "id": "poses",
            "name": "Poses",
            "mode": "physical",
            "cards": [{"id": "first", "label": "First", "text": "First pose."}],
        },
    )
    AttributeResolver().set(
        scene,
        "character:Model/attributes/current_pose",
        {
            "source": "deck",
            "ref": "poses",
            "render_policy": "prompt",
            "options": {
                "anchor": "character:Model",
                "result_field": "text",
            },
        },
    )
    render_node = get_node("primitives/attributes/Render")()

    with pytest.raises(ValueError):
        await run_node(
            render_node,
            scene=scene,
            inputs={
                "ref": "character:Model/attributes/current_pose",
                "audience": "promt",
            },
        )

    assert [
        entry for entry in store.recent_ledger() if entry["op"] == "deck.draw"
    ] == []
