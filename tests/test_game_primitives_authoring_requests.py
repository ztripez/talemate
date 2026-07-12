"""Tests for primitive authoring request contracts and adapters."""

import pytest

from talemate.game.primitives.authoring.schema import (
    CreateDeckRequest,
    CreateModifierRequest,
    CreateRelationshipRequest,
    CreateRollTableRequest,
    DraftRequest,
)
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_authoring_mutations_require_an_explicit_revision():
    """Request and service boundaries reject revision-less mutations."""
    with pytest.raises(ValueError, match="expected_revision"):
        DraftRequest(draft_id="draft")

    with pytest.raises(TypeError, match="expected_revision"):
        PrimitiveAuthoringService().create_draft(Scene(), "draft")


def test_invalid_nested_deck_and_roll_table_inputs_fail_before_draft_mutation():
    """Canonical nested schemas reject empty cards and rows at the request boundary."""
    with pytest.raises(ValueError):
        CreateDeckRequest(
            draft_id="d",
            expected_revision="revision",
            id="deck",
            name="Deck",
            mode="bag",
            cards=[],
        )
    with pytest.raises(ValueError):
        CreateRollTableRequest(
            draft_id="d",
            expected_revision="revision",
            id="table",
            name="Table",
            mode="weighted",
            rows=[],
        )


def test_optional_authoring_contracts_stage_canonical_instances_and_explanation():
    """Optional instance and explanation fields produce their canonical effects."""
    deck = {
        "draft_id": "d",
        "expected_revision": "revision",
        "id": "deck",
        "name": "Deck",
        "mode": "bag",
        "cards": [{"id": "card", "label": "Card"}],
    }
    table = {
        "draft_id": "d",
        "expected_revision": "revision",
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
    revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
    service.create_draft(scene, "d", expected_revision=revision)
    deck["expected_revision"] = PrimitiveStore.read_snapshot_for_scene(
        scene
    ).revision_token()
    service.create_deck(
        scene, CreateDeckRequest(**deck, anchor="scene:main", instance_id="instance")
    )
    table["expected_revision"] = PrimitiveStore.read_snapshot_for_scene(
        scene
    ).revision_token()
    service.create_roll_table(
        scene, CreateRollTableRequest(**table, anchor="scene:main")
    )
    service.create_modifier(
        scene,
        CreateModifierRequest(
            draft_id="d",
            expected_revision=PrimitiveStore.read_snapshot_for_scene(
                scene
            ).revision_token(),
            id="bonus",
            applies_to="table",
            operation={"add": 1},
            explanation="Because",
        ),
    )

    draft = service.drafts.get(scene, "d")
    assert (
        draft.anchors["scene:main"].primitives["decks"]["instance"].definition == "deck"
    )
    assert (
        draft.anchors["scene:main"].primitives["roll_tables"]["table"].definition
        == "table"
    )
    assert draft.definitions["modifiers"]["bonus"].explanation == "Because"

    service.commit_draft(
        scene,
        "d",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )
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
            expected_revision="revision",
            source="Alice",
            target="Bob",
            dimensions=[
                {"id": "trust", "value": 1},
                {"id": "trust", "value": 2},
            ],
        )


def test_relationship_dimensions_use_canonical_meter_with_request_defaults():
    """Relationship requests default and strictly validate canonical meters."""
    payload = {
        "draft_id": "relations",
        "expected_revision": "revision",
        "source": "Alice",
        "target": "Bob",
    }

    with pytest.raises(ValueError, match="valid number"):
        CreateRelationshipRequest(**payload, dimensions=[{"id": "trust", "value": "2"}])
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        CreateRelationshipRequest(
            **payload, dimensions=[{"id": "trust", "unexpected": True}]
        )

    request = CreateRelationshipRequest(**payload, dimensions=[{"id": "trust"}])
    assert request.dimensions[0].model_dump(mode="json") == {
        "id": "trust",
        "label": None,
        "min": -5,
        "max": 5,
        "value": 0,
        "render_policy": "summary",
    }


def test_modifier_request_adapts_external_operation_to_canonical_model():
    request = CreateModifierRequest(
        draft_id="draft",
        expected_revision="revision",
        id="bonus",
        applies_to="table",
        operation={"add": 2},
        explanation="A situational bonus",
    )

    assert request.canonical_model().add == 2
    assert request.canonical_payload["add"] == 2
    assert request.canonical_payload["explanation"] == "A situational bonus"
    assert "operation" not in request.canonical_payload
