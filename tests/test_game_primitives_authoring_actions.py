"""Contract tests for Game Primitives Director authoring actions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import talemate.game.engine.nodes.load_definitions  # noqa: F401 - register modules
from talemate.agents.director.chat.nodes import DirectorChatActionArgument
from talemate.context import ActiveScene
from talemate.game.engine.nodes.core import GraphState
from talemate.game.engine.nodes.primitives.authoring_base import CreateDraftRequest
from talemate.game.engine.nodes.registry import (
    get_node,
    import_initial_node_definitions,
)
from talemate.game.primitives.authoring.schema import (
    CreateAttributeSourceRequest,
    CreateDeckRequest,
    CreateMeterRequest,
    CreateModifierRequest,
    CreateRelationshipRequest,
    CreateRollTableRequest,
    DraftRequest,
)
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene

MODULE_DIR = Path("templates/modules/game-primitives")
ACTION_ARGUMENT = "agents/director/chat/ActionArgument"
DIRECTOR_SUBACTION = "agents/director/chat/DirectorChatSubAction"
RETURN = "core/functions/Return"
OBJECT_ARGUMENT_TYPE = (
    "dict" if "dict" in DirectorChatActionArgument.Fields.typ.choices else "any"
)

ACTION_CONTRACTS = {
    "primitive-authoring-actions.json": (
        "agents/director/chat/createPrimitiveDraft",
        "primitives/authoring/CreateDraft",
        {"draft_id": "str"},
    ),
    "create-deck-action.json": (
        "agents/director/chat/addPrimitiveDeck",
        "primitives/authoring/CreateDeck",
        {
            "draft_id": "str",
            "id": "str",
            "name": "str",
            "mode": "str",
            "cards": "list",
            "anchor": "str",
            "instance_id": "str",
        },
    ),
    "create-roll-table-action.json": (
        "agents/director/chat/addPrimitiveRollTable",
        "primitives/authoring/CreateRollTable",
        {
            "draft_id": "str",
            "id": "str",
            "name": "str",
            "mode": "str",
            "rows": "list",
            "dice": "str",
            "anchor": "str",
            "instance_id": "str",
        },
    ),
    "create-meter-action.json": (
        "agents/director/chat/addPrimitiveMeter",
        "primitives/authoring/CreateMeter",
        {
            "draft_id": "str",
            "anchor": "str",
            "id": "str",
            "label": "str",
            "min": "float",
            "max": "float",
            "value": "float",
            "render_policy": "str",
        },
    ),
    "create-relationship-action.json": (
        "agents/director/chat/addPrimitiveRelationship",
        "primitives/authoring/CreateRelationshipModel",
        {
            "draft_id": "str",
            "source": "str",
            "target": "str",
            "dimensions": "list",
            "tags": "list",
        },
    ),
    "create-modifier-action.json": (
        "agents/director/chat/addPrimitiveModifier",
        "primitives/authoring/CreateModifier",
        {
            "draft_id": "str",
            "id": "str",
            "label": "str",
            "applies_to": "str",
            "when": "list",
            "operation": OBJECT_ARGUMENT_TYPE,
            "explanation": "str",
        },
    ),
    "create-attribute-source-action.json": (
        "agents/director/chat/addPrimitiveAttributeSource",
        "primitives/authoring/CreateAttributeSource",
        {
            "draft_id": "str",
            "anchor": "str",
            "id": "str",
            "source": "str",
            "render_policy": "str",
            "ref": "str",
            "value": "any",
            "options": OBJECT_ARGUMENT_TYPE,
        },
    ),
    "validate-draft-action.json": (
        "agents/director/chat/validatePrimitiveDraft",
        "primitives/authoring/ValidateDraft",
        {"draft_id": "str"},
    ),
    "commit-draft-action.json": (
        "agents/director/chat/commitPrimitiveDraft",
        "primitives/authoring/CommitDraft",
        {"draft_id": "str"},
    ),
}

REQUEST_MODELS = {
    "primitive-authoring-actions.json": CreateDraftRequest,
    "create-deck-action.json": CreateDeckRequest,
    "create-roll-table-action.json": CreateRollTableRequest,
    "create-meter-action.json": CreateMeterRequest,
    "create-relationship-action.json": CreateRelationshipRequest,
    "create-modifier-action.json": CreateModifierRequest,
    "create-attribute-source-action.json": CreateAttributeSourceRequest,
    "validate-draft-action.json": DraftRequest,
    "commit-draft-action.json": DraftRequest,
}

import_initial_node_definitions()


def _nodes_with_registry(graph: dict, registry: str) -> list[dict]:
    return [node for node in graph["nodes"].values() if node["registry"] == registry]


def test_authoring_action_files_are_exactly_the_issue_targets():
    """The issue's nine action modules exist without replacing the package manifest."""
    action_files = {
        path.name for path in MODULE_DIR.glob("*.json") if path.name in ACTION_CONTRACTS
    }

    assert action_files == set(ACTION_CONTRACTS)
    assert (MODULE_DIR / "game-primitives-package.json").is_file()


def test_authoring_actions_are_valid_discoverable_direct_wrappers():
    """Each action directly wires its arguments, authoring node, gate, and return."""
    for filename, (
        registry,
        operation_registry,
        expected_arguments,
    ) in ACTION_CONTRACTS.items():
        graph = json.loads((MODULE_DIR / filename).read_text(encoding="utf-8"))

        assert graph["base_type"] == "agents/director/DirectorChatAction"
        assert graph["registry"] == registry
        assert get_node(registry) is not None

        operations = _nodes_with_registry(graph, operation_registry)
        subactions = _nodes_with_registry(graph, DIRECTOR_SUBACTION)
        returns = _nodes_with_registry(graph, RETURN)
        arguments = _nodes_with_registry(graph, ACTION_ARGUMENT)

        assert len(operations) == 1
        assert len(subactions) == 1
        assert len(returns) == 1
        argument_types = {
            node["properties"]["name"]: node["properties"]["typ"] for node in arguments
        }
        assert argument_types == expected_arguments

        operation = operations[0]
        subaction = subactions[0]
        return_node = returns[0]
        for argument in arguments:
            name = argument["properties"]["name"]
            assert graph["edges"][f"{argument['id']}.value"] == [
                f"{operation['id']}.{name}"
            ]

        assert graph["edges"][f"{operation['id']}.draft"] == [
            f"{subaction['id']}.state"
        ]
        assert graph["edges"][f"{subaction['id']}.state"] == [
            f"{return_node['id']}.value"
        ]


def test_authoring_action_examples_match_canonical_request_models():
    """Every advertised payload is accepted by its operation's request boundary."""
    assert set(REQUEST_MODELS) == set(ACTION_CONTRACTS)

    for filename, request_model in REQUEST_MODELS.items():
        graph = json.loads((MODULE_DIR / filename).read_text(encoding="utf-8"))
        examples = json.loads(graph["properties"]["example_json"])

        assert isinstance(examples, list) and examples
        for example in examples:
            payload = {"draft_id": "example-draft", **example}
            request_model.model_validate(payload)


def test_object_action_arguments_use_any_only_without_dict_support():
    """The function-argument framework currently has no dict property choice."""
    assert "dict" not in DirectorChatActionArgument.Fields.typ.choices
    assert OBJECT_ARGUMENT_TYPE == "any"


@pytest.mark.asyncio
async def test_dynamic_create_draft_director_action_executes_end_to_end(monkeypatch):
    """A registered dynamic wrapper executes its operation graph, not just its shape."""
    monkeypatch.setattr(
        "talemate.agents.director.chat.nodes.is_action_id_enabled",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "talemate.agents.director.chat.nodes.get_agent", lambda name: object()
    )
    scene = Scene()
    with ActiveScene(scene):
        action = get_node("agents/director/chat/createPrimitiveDraft")()
        await action.execute_action(GraphState(), draft_id="director-e2e")

    assert "director-e2e" in PrimitiveStore.for_scene(scene).root["drafts"]
