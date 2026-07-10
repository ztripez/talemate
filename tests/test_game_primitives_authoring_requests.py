"""Tests for primitive authoring request contracts and adapters."""

import pytest

from talemate.game.primitives.authoring.schema import (
    CreateDeckRequest,
    CreateModifierRequest,
    CreateRelationshipRequest,
    CreateRollTableRequest,
)
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_invalid_nested_deck_and_roll_table_inputs_fail_before_draft_mutation():
    """Canonical nested schemas reject empty cards and rows at the request boundary."""
    with pytest.raises(ValueError):
        CreateDeckRequest(draft_id="d", id="deck", name="Deck", mode="bag", cards=[])
    with pytest.raises(ValueError):
        CreateRollTableRequest(
            draft_id="d", id="table", name="Table", mode="weighted", rows=[]
        )


def test_optional_authoring_contracts_stage_canonical_instances_and_explanation():
    """Optional instance and explanation fields produce their canonical effects."""
    deck = {
        "draft_id": "d",
        "id": "deck",
        "name": "Deck",
        "mode": "bag",
        "cards": [{"id": "card", "label": "Card"}],
    }
    table = {
        "draft_id": "d",
        "id": "table",
        "name": "Table",
        "mode": "weighted",
        "rows": [{"id": "row", "label": "Row", "weight": 1}],
    }

    with pytest.raises(ValueError, match="instance_id requires anchor"):
        CreateDeckRequest(**deck, instance_id="instance")
    with pytest.raises(ValueError, match="instance_id requires anchor"):
        CreateRollTableRequest(**table, instance_id="instance")

    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "d")
    service.create_deck(
        scene, CreateDeckRequest(**deck, anchor="scene:main", instance_id="instance")
    )
    service.create_roll_table(
        scene, CreateRollTableRequest(**table, anchor="scene:main")
    )
    service.create_modifier(
        scene,
        CreateModifierRequest(
            draft_id="d",
            id="bonus",
            applies_to="table",
            operation={"add": 1},
            explanation="Because",
        ),
    )

    draft = service.drafts.get(scene, "d")
    assert (
        draft.anchors["scene:main"].primitives["decks"]["instance"]["definition"]
        == "deck"
    )
    assert draft.anchors["scene:main"].primitives["roll_tables"]["table"] == {
        "definition": "table"
    }
    assert draft.definitions["modifiers"]["bonus"]["explanation"] == "Because"

    service.commit_draft(scene, "d")
    store = PrimitiveStore.for_scene(scene)
    assert (
        store.get_primitive("scene:main/decks/instance")["runtime"]["definition_id"]
        == "deck"
    )
    assert store.get_primitive("scene:main/roll_tables/table") == {
        "definition": "table"
    }


def test_duplicate_relationship_dimensions_are_rejected():
    """Relationship requests reject duplicate IDs before dict conversion loses one."""
    with pytest.raises(ValueError, match="must be unique"):
        CreateRelationshipRequest(
            draft_id="relations",
            source="Alice",
            target="Bob",
            dimensions=[
                {"id": "trust", "value": 1},
                {"id": "trust", "value": 2},
            ],
        )


def test_relationship_dimension_input_is_strict_and_forbids_extra_fields():
    """Relationship authoring rejects coercion and unknown dimension fields."""
    payload = {
        "draft_id": "relations",
        "source": "Alice",
        "target": "Bob",
    }

    with pytest.raises(ValueError, match="valid number"):
        CreateRelationshipRequest(**payload, dimensions=[{"id": "trust", "value": "2"}])
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        CreateRelationshipRequest(
            **payload, dimensions=[{"id": "trust", "unexpected": True}]
        )


def test_modifier_request_adapts_external_operation_to_canonical_model():
    request = CreateModifierRequest(
        draft_id="draft",
        id="bonus",
        applies_to="table",
        operation={"add": 2},
        explanation="A situational bonus",
    )

    assert request.canonical_model().add == 2
    assert request.canonical_payload["add"] == 2
    assert request.canonical_payload["explanation"] == "A situational bonus"
    assert "operation" not in request.canonical_payload
