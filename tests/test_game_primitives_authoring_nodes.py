"""Tests for primitive authoring graph nodes."""

import json

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401 - node registration side effects
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene

AUTHORING_NODES = (
    "CreateDraft",
    "CreateAnchor",
    "CreateMeter",
    "CreateClock",
    "CreateDeck",
    "CreateRollTable",
    "CreateRelationshipModel",
    "CreateModifier",
    "CreateAttributeSource",
    "ValidateDraft",
    "CommitDraft",
)


def test_authoring_nodes_are_registered():
    """Every narrow primitive authoring operation is registered."""
    for name in AUTHORING_NODES:
        assert get_node(f"primitives/authoring/{name}") is not None


def test_definition_node_sockets_include_optional_contract_fields():
    deck_inputs = {
        socket.name for socket in get_node("primitives/authoring/CreateDeck")().inputs
    }
    table_inputs = {
        socket.name
        for socket in get_node("primitives/authoring/CreateRollTable")().inputs
    }
    modifier_inputs = {
        socket.name
        for socket in get_node("primitives/authoring/CreateModifier")().inputs
    }

    assert {"anchor", "instance_id"} <= deck_inputs
    assert {"anchor", "instance_id"} <= table_inputs
    assert "explanation" in modifier_inputs


async def _run(scene, name, inputs):
    outputs = await run_node(
        get_node(f"primitives/authoring/{name}")(), scene=scene, inputs=inputs
    )
    json.dumps(outputs["draft"])
    return outputs["draft"]


async def test_authoring_nodes_build_validate_and_commit_json_safe_draft():
    """Authoring nodes stage all supported payload types and commit after validation."""
    scene = Scene()
    draft = await _run(scene, "CreateDraft", {"draft_id": "node-draft"})
    assert draft["id"] == "node-draft"

    await _run(
        scene,
        "CreateAnchor",
        {"draft_id": "node-draft", "kind": "character", "id": "Model"},
    )
    await _run(
        scene,
        "CreateMeter",
        {
            "draft_id": "node-draft",
            "anchor": "character:Model",
            "id": "focus",
            "min": 0,
            "max": 5,
            "value": 3,
        },
    )
    await _run(
        scene,
        "CreateClock",
        {
            "draft_id": "node-draft",
            "anchor": "character:Model",
            "id": "escape",
            "max": 4,
        },
    )
    await _run(
        scene,
        "CreateDeck",
        {
            "draft_id": "node-draft",
            "id": "poses",
            "name": "Poses",
            "mode": "bag",
            "cards": [{"id": "calm", "label": "Calm"}],
            "anchor": "character:Model",
        },
    )
    await _run(
        scene,
        "CreateRollTable",
        {
            "draft_id": "node-draft",
            "id": "reactions",
            "name": "Reactions",
            "mode": "weighted",
            "rows": [{"id": "smile", "label": "Smile", "weight": 1}],
            "anchor": "character:Model",
            "instance_id": "local-reactions",
        },
    )
    await _run(
        scene,
        "CreateRelationshipModel",
        {
            "draft_id": "node-draft",
            "source": "Alice",
            "target": "Bob",
            "dimensions": [{"id": "trust", "value": 1}],
        },
    )
    await _run(
        scene,
        "CreateModifier",
        {
            "draft_id": "node-draft",
            "id": "steady",
            "applies_to": "reactions",
            "operation": {"add": 1},
            "explanation": "A steady approach helps.",
        },
    )
    await _run(
        scene,
        "CreateAttributeSource",
        {
            "draft_id": "node-draft",
            "anchor": "character:Model",
            "id": "pose",
            "source": "deck",
            "render_policy": "hidden",
            "ref": "poses",
        },
    )

    validated = await _run(scene, "ValidateDraft", {"draft_id": "node-draft"})
    assert validated["status"] == "validated"
    committed = await _run(scene, "CommitDraft", {"draft_id": "node-draft"})

    store = PrimitiveStore.for_scene(scene)
    assert committed["status"] == "committed"
    assert store.get_primitive("character:Model/meters/focus")["value"] == 3
    assert store.get_definition("decks", "poses")["cards"][0]["id"] == "calm"
    assert store.get_primitive("character:Model/decks/poses")["definition"] == "poses"
    assert store.get_primitive("character:Model/roll_tables/local-reactions") == {
        "definition": "reactions"
    }
    assert store.get_definition("modifiers", "steady")["explanation"] == (
        "A steady approach helps."
    )


async def test_authoring_node_request_validation_precedes_draft_mutation():
    """Invalid nested request payloads fail without changing the target draft."""
    scene = Scene()
    await _run(scene, "CreateDraft", {"draft_id": "invalid"})
    before = PrimitiveStore.for_scene(scene).root["drafts"]["invalid"].copy()

    with pytest.raises(ValueError):
        await _run(
            scene,
            "CreateDeck",
            {
                "draft_id": "invalid",
                "id": "empty",
                "name": "Empty",
                "mode": "bag",
                "cards": [],
            },
        )

    assert PrimitiveStore.for_scene(scene).root["drafts"]["invalid"] == before
