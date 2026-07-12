"""Tests for primitive authoring reference, condition, and warning validation."""

import copy

import pytest

from talemate.game.primitives.authoring.schema import (
    CreateAnchorRequest,
    CreateAttributeSourceRequest,
    CreateDeckRequest,
    CreateModifierRequest,
    CreateRollTableRequest,
)
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def _revision(scene: Scene) -> str:
    return PrimitiveStore.read_snapshot_for_scene(scene).revision_token()


def test_missing_attribute_reference_blocks_commit_without_mutating_store():
    """Reference validation prevents invalid drafts from changing committed state."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "bad", expected_revision=_revision(scene))
    service.create_attribute_source(
        scene,
        CreateAttributeSourceRequest(
            draft_id="bad",
            expected_revision=_revision(scene),
            anchor="scene:main",
            id="missing",
            source="deck",
            ref="absent",
            render_policy="hidden",
        ),
    )
    store = PrimitiveStore.for_scene(scene)
    before = copy.deepcopy(store.root["definitions"])

    validated = service.validate_draft(scene, "bad", expected_revision=_revision(scene))

    assert validated.status == "draft"
    assert "Missing deck definition" in validated.validation.errors[0]
    with pytest.raises(ValueError, match="validation failed"):
        service.commit_draft(scene, "bad", expected_revision=_revision(scene))
    assert store.root["definitions"] == before
    assert store.get_anchor("scene:main") is None
    persisted = service.drafts.get(scene, "bad")
    assert persisted.status == "draft"
    assert persisted.validation.ok is False
    assert "Missing deck definition" in persisted.validation.errors[0]


def test_validation_rejects_committed_definition_and_anchor_collisions():
    """Drafts cannot overwrite committed IDs while building a candidate root."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "poses",
        {
            "id": "poses",
            "name": "Poses",
            "mode": "bag",
            "cards": [{"id": "old", "label": "Old"}],
        },
    )
    store.ensure_anchor("character:Model")
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "collisions", expected_revision=_revision(scene))
    service.create_deck(
        scene,
        CreateDeckRequest(
            draft_id="collisions",
            expected_revision=_revision(scene),
            id="poses",
            name="Replacement",
            mode="bag",
            cards=[{"id": "new", "label": "New"}],
        ),
    )
    service.create_anchor(
        scene,
        CreateAnchorRequest(
            draft_id="collisions",
            expected_revision=_revision(scene),
            kind="character",
            id="Model",
        ),
    )

    validation = service.validate_draft(
        scene, "collisions", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert "Definition already exists: decks/poses" in validation.errors
    assert "Anchor already exists: character:Model" in validation.errors


def test_validation_checks_all_candidate_attribute_reference_kinds():
    """Candidate validation rejects missing meter, clock, modifier, and relationship refs."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "refs", expected_revision=_revision(scene))
    sources = {
        "meter": "scene:main/meters/missing",
        "clock": "scene:main/clocks/missing",
        "modifier": "missing-modifier",
        "relationship": "relationship:Alice->Bob/meters/trust",
    }
    for source, ref in sources.items():
        service.create_attribute_source(
            scene,
            CreateAttributeSourceRequest(
                draft_id="refs",
                expected_revision=_revision(scene),
                anchor="scene:main",
                id=source,
                source=source,
                ref=ref,
                render_policy="hidden",
            ),
        )

    validation = service.validate_draft(
        scene, "refs", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert "Missing meter primitive: scene:main/meters/missing" in validation.errors
    assert "Missing clock primitive: scene:main/clocks/missing" in validation.errors
    assert "Missing modifier: missing-modifier" in validation.errors
    assert (
        "Missing meter primitive: relationship:Alice->Bob/meters/trust"
        in validation.errors
    )


def test_validation_rejects_missing_modifier_target():
    """Authored modifiers must target a candidate roll table definition or instance."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "modifier-target", expected_revision=_revision(scene))
    service.create_modifier(
        scene,
        CreateModifierRequest(
            draft_id="modifier-target",
            expected_revision=_revision(scene),
            id="bonus",
            applies_to="missing-table",
            operation={"add": 1},
        ),
    )

    validation = service.validate_draft(
        scene, "modifier-target", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert "Missing modifier target: missing-table" in validation.errors


def test_validation_rejects_dangling_anchored_roll_table_definition():
    """Anchored roll-table instances must reference a candidate definition."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "dangling-table", expected_revision=_revision(scene))
    service.create_anchor(
        scene,
        CreateAnchorRequest(
            draft_id="dangling-table",
            expected_revision=_revision(scene),
            kind="scene",
            id="main",
        ),
    )
    draft = service.drafts.get(scene, "dangling-table")
    draft.anchors["scene:main"].primitives.set_item(
        "roll_tables", "local", {"definition": "missing"}
    )
    service.drafts.put(
        scene,
        draft,
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )

    validation = service.validate_draft(
        scene, "dangling-table", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert (
        "Missing roll table definition for scene:main/roll_tables/local: missing"
        in validation.errors
    )


def test_validation_traverses_attribute_and_modifier_condition_references():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "condition-refs", expected_revision=_revision(scene))
    service.create_roll_table(
        scene,
        CreateRollTableRequest(
            draft_id="condition-refs",
            expected_revision=_revision(scene),
            id="table",
            name="Table",
            mode="weighted",
            rows=[{"id": "row", "label": "Row", "weight": 1}],
        ),
    )
    service.create_attribute_source(
        scene,
        CreateAttributeSourceRequest(
            draft_id="condition-refs",
            expected_revision=_revision(scene),
            anchor="scene:main",
            id="conditional",
            source="literal",
            value="value",
            conditions=[
                {
                    "conditions": [
                        {
                            "kind": "primitive",
                            "path": "scene:main/attributes/missing",
                        },
                        {
                            "kind": "meter",
                            "anchor": "scene:main",
                            "dimension": "missing-meter",
                        },
                        {
                            "kind": "clock_complete",
                            "anchor": "scene:main",
                            "dimension": "missing-clock",
                        },
                        {
                            "kind": "relationship",
                            "anchor": "relationship:Alice->Bob",
                            "dimension": "trust",
                        },
                        {
                            "kind": "anchor_has_tag",
                            "anchor": "character:Missing",
                            "tag": "active",
                        },
                    ]
                }
            ],
        ),
    )
    service.create_modifier(
        scene,
        CreateModifierRequest(
            draft_id="condition-refs",
            expected_revision=_revision(scene),
            id="conditional-modifier",
            applies_to="table",
            operation={"add": 1},
            when=[
                {
                    "conditions": [
                        {
                            "kind": "meter",
                            "path": "scene:main/meters/modifier-missing",
                        }
                    ]
                }
            ],
        ),
    )

    errors = service.validate_draft(
        scene, "condition-refs", expected_revision=_revision(scene)
    ).validation.errors

    assert "Missing attribute primitive: scene:main/attributes/missing" in errors
    assert "Missing meter primitive: scene:main/meters/missing-meter" in errors
    assert "Missing clock primitive: scene:main/clocks/missing-clock" in errors
    assert "Missing meter primitive: relationship:Alice->Bob/meters/trust" in errors
    assert "Missing anchor for tag condition: character:Missing" in errors
    assert "Missing meter primitive: scene:main/meters/modifier-missing" in errors


def test_validation_traverses_deck_card_and_roll_table_row_conditions():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(
        scene, "definition-condition-refs", expected_revision=_revision(scene)
    )
    service.create_deck(
        scene,
        CreateDeckRequest(
            draft_id="definition-condition-refs",
            expected_revision=_revision(scene),
            id="deck",
            name="Deck",
            mode="bag",
            cards=[
                {
                    "id": "card",
                    "label": "Card",
                    "conditions": [
                        {
                            "conditions": [
                                {
                                    "kind": "meter",
                                    "path": "scene:main/meters/card-missing",
                                }
                            ]
                        }
                    ],
                }
            ],
        ),
    )
    service.create_roll_table(
        scene,
        CreateRollTableRequest(
            draft_id="definition-condition-refs",
            expected_revision=_revision(scene),
            id="table",
            name="Table",
            mode="weighted",
            rows=[
                {
                    "id": "row",
                    "label": "Row",
                    "weight": 1,
                    "conditions": [
                        {
                            "conditions": [
                                {
                                    "kind": "clock_complete",
                                    "path": "scene:main/clocks/row-missing",
                                }
                            ]
                        }
                    ],
                }
            ],
        ),
    )

    errors = service.validate_draft(
        scene,
        "definition-condition-refs",
        expected_revision=_revision(scene),
    ).validation.errors

    assert "Missing meter primitive: scene:main/meters/card-missing" in errors
    assert "Missing clock primitive: scene:main/clocks/row-missing" in errors


def test_validation_traverses_adventure_transition_condition_references():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(
        scene, "adventure-condition-refs", expected_revision=_revision(scene)
    )
    draft = service.drafts.get(scene, "adventure-condition-refs")
    draft.definitions.set_item(
        "adventures",
        "adventure",
        {
            "id": "adventure",
            "title": "Adventure",
            "start_scene": "start",
            "scenes": {
                "start": {"id": "start", "title": "Start"},
                "end": {"id": "end", "title": "End"},
            },
            "transitions": {
                "continue": {
                    "id": "continue",
                    "from_scene": "start",
                    "to_scene": "end",
                    "label": "Continue",
                    "conditions": [
                        {
                            "conditions": [
                                {
                                    "kind": "meter",
                                    "path": "scene:main/meters/missing-meter",
                                },
                                {
                                    "kind": "clock_complete",
                                    "path": "scene:main/clocks/missing-clock",
                                },
                                {
                                    "kind": "relationship",
                                    "anchor": "relationship:Alice->Bob",
                                    "dimension": "trust",
                                },
                                {
                                    "kind": "primitive",
                                    "path": "scene:main/attributes/missing-attribute",
                                },
                                {
                                    "kind": "anchor_has_tag",
                                    "anchor": "character:Missing",
                                    "tag": "active",
                                },
                            ]
                        }
                    ],
                }
            },
        },
    )
    service.drafts.put(
        scene,
        draft,
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )

    validation = service.validate_draft(
        scene, "adventure-condition-refs", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert (
        "Missing meter primitive: scene:main/meters/missing-meter" in validation.errors
    )
    assert (
        "Missing clock primitive: scene:main/clocks/missing-clock" in validation.errors
    )
    assert (
        "Missing meter primitive: relationship:Alice->Bob/meters/trust"
        in validation.errors
    )
    assert (
        "Missing attribute primitive: scene:main/attributes/missing-attribute"
        in validation.errors
    )
    assert "Missing anchor for tag condition: character:Missing" in validation.errors


def test_validation_warns_for_deck_avoid_recent_and_unrenderable_prompt_source():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "warnings", expected_revision=_revision(scene))
    service.create_deck(
        scene,
        CreateDeckRequest(
            draft_id="warnings",
            expected_revision=_revision(scene),
            id="deck",
            name="Deck",
            mode="bag",
            cards=[{"id": "card", "label": "Card"}],
        ),
    )
    service.create_attribute_source(
        scene,
        CreateAttributeSourceRequest(
            draft_id="warnings",
            expected_revision=_revision(scene),
            anchor="scene:main",
            id="draw",
            source="deck",
            ref="deck",
            render_policy="prompt",
            options={"avoid_recent": 1},
        ),
    )

    warnings = service.validate_draft(
        scene, "warnings", expected_revision=_revision(scene)
    ).validation.warnings

    assert any("avoid_recent" in warning for warning in warnings)
    assert any("lacks guaranteed renderable text" in warning for warning in warnings)


def test_prompt_visible_null_literal_warns_and_is_preserved_on_commit():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "null-literal", expected_revision=_revision(scene))
    request = CreateAttributeSourceRequest(
        draft_id="null-literal",
        expected_revision=_revision(scene),
        anchor="scene:main",
        id="unknown",
        source="literal",
        value=None,
        render_policy="prompt",
    )

    assert "value" in request.canonical_payload
    assert request.canonical_payload["value"] is None
    service.create_attribute_source(scene, request)

    validated = service.validate_draft(
        scene, "null-literal", expected_revision=_revision(scene)
    )
    assert validated.validation.ok is True
    assert any(
        "scene:main/attributes/unknown lacks guaranteed renderable text" in warning
        for warning in validated.validation.warnings
    )

    service.commit_draft(scene, "null-literal", expected_revision=_revision(scene))
    stored = PrimitiveStore.for_scene(scene).get_primitive(
        "scene:main/attributes/unknown"
    )
    assert "value" in stored
    assert stored["value"] is None


def test_validation_rejects_base_attribute_destinations_and_refs():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "leak", expected_revision=_revision(scene))
    service.create_deck(
        scene,
        CreateDeckRequest(
            draft_id="leak",
            expected_revision=_revision(scene),
            id="deck",
            name="Deck",
            mode="bag",
            cards=[
                {
                    "id": "card",
                    "label": "Card",
                    "effects": [
                        {
                            "op": "set",
                            "target": "character:Alice/base_attributes/mood",
                            "value": "happy",
                        }
                    ],
                }
            ],
        ),
    )
    service.create_attribute_source(
        scene,
        CreateAttributeSourceRequest(
            draft_id="leak",
            expected_revision=_revision(scene),
            anchor="scene:main",
            id="legacy",
            source="state_ref",
            ref="Character.base_attributes.mood",
            render_policy="hidden",
        ),
    )

    errors = service.validate_draft(
        scene, "leak", expected_revision=_revision(scene)
    ).validation.errors

    assert len([error for error in errors if "Character.base_attributes" in error]) == 2


def test_validation_rejects_missing_roll_table_modifier_reference():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "table-modifier", expected_revision=_revision(scene))
    service.create_roll_table(
        scene,
        CreateRollTableRequest(
            draft_id="table-modifier",
            expected_revision=_revision(scene),
            id="table",
            name="Table",
            mode="weighted",
            rows=[{"id": "row", "label": "Row", "weight": 1}],
            modifiers=["missing"],
        ),
    )

    errors = service.validate_draft(
        scene, "table-modifier", expected_revision=_revision(scene)
    ).validation.errors

    assert "Missing modifier: missing" in errors
