"""Tests for narrow primitive authoring tools and validated commit."""

import json

import pytest

from talemate.game.primitives.authoring.schema import (
    CreateAnchorRequest,
    CreateAttributeSourceRequest,
    CreateClockRequest,
    CreateDeckRequest,
    CreateMeterRequest,
    CreateModifierRequest,
    CreateRelationshipRequest,
    CreateRollTableRequest,
)
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.definitions import DEFINITION_KINDS
from talemate.game.primitives.roll_tables import RollTableEngine
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_authoring_tools_build_isolated_valid_draft_and_commit():
    """Narrow tools stage canonical payloads and commit them only after validation."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "session")
    service.create_anchor(
        scene,
        CreateAnchorRequest(
            draft_id="session", kind="character", id="Model", tags=["active"]
        ),
    )
    service.create_meter(
        scene,
        CreateMeterRequest(
            draft_id="session",
            anchor="character:Model",
            id="focus",
            min=0,
            max=5,
            value=3,
        ),
    )
    service.create_deck(
        scene,
        CreateDeckRequest(
            draft_id="session",
            id="poses",
            name="Poses",
            mode="bag",
            cards=[{"id": "calm", "label": "Calm"}],
        ),
    )
    service.create_attribute_source(
        scene,
        CreateAttributeSourceRequest(
            draft_id="session",
            anchor="character:Model",
            id="pose",
            source="deck",
            ref="poses",
            render_policy="hidden",
            options={"mode": "peek"},
        ),
    )
    store = PrimitiveStore.for_scene(scene)
    assert store.get_definition("decks", "poses") is None
    assert store.get_anchor("character:Model") is None

    validated = service.validate_draft(scene, "session")
    assert validated.status == "validated"
    committed = service.commit_draft(scene, "session")

    assert committed.status == "committed"
    assert store.get_definition("decks", "poses")["cards"][0]["id"] == "calm"
    assert store.get_primitive("character:Model/meters/focus")["value"] == 3
    assert dict(committed.definitions) == {kind: {} for kind in DEFINITION_KINDS}
    assert committed.anchors == {}
    assert store.root["drafts"]["session"]["definitions"] == {
        kind: {} for kind in DEFINITION_KINDS
    }
    assert store.root["drafts"]["session"]["anchors"] == {}
    json.dumps(store.root)


def test_authored_modifier_explanations_appear_in_runtime_roll_debug():
    scene = Scene()
    scene.game_state.set_var("active", True)
    scene.game_state.set_var("inactive", False)
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "runtime-modifiers")
    service.create_roll_table(
        scene,
        CreateRollTableRequest(
            draft_id="runtime-modifiers",
            id="table",
            name="Table",
            dice="1d1",
            rows=[{"id": "result", "label": "Result", "range": "1-2"}],
            modifiers=["active", "inactive"],
        ),
    )
    for modifier_id, explanation in [
        ("active", "The active condition matched."),
        ("inactive", "The inactive condition did not match."),
    ]:
        service.create_modifier(
            scene,
            CreateModifierRequest(
                draft_id="runtime-modifiers",
                id=modifier_id,
                applies_to="table",
                when=[
                    {
                        "conditions": [
                            {
                                "kind": "path",
                                "path": modifier_id,
                                "operator": "is_true",
                            }
                        ]
                    }
                ],
                operation={"add": 1},
                explanation=explanation,
            ),
        )
    service.commit_draft(scene, "runtime-modifiers")

    result = RollTableEngine().roll(scene, "table")

    assert [
        (modifier["active"], modifier["explanation"])
        for modifier in result.debug["modifiers"]
    ] == [
        (True, "The active condition matched."),
        (False, "The inactive condition did not match."),
    ]


def test_relationship_tool_creates_directional_anchor_dimensions():
    """Relationship authoring stages the canonical directional meter representation."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "relations")

    draft = service.create_relationship(
        scene,
        CreateRelationshipRequest(
            draft_id="relations",
            source="Alice",
            target="Bob",
            dimensions=[{"id": "trust", "value": 2}],
            tags=["party"],
        ),
    )

    anchor = draft.anchors["relationship:Alice->Bob"]
    assert anchor.tags == ["party"]
    assert anchor.primitives["meters"]["trust"] == {
        "id": "trust",
        "label": None,
        "min": -5,
        "max": 5,
        "value": 2,
        "render_policy": "summary",
    }


def test_create_anchor_updates_metadata_without_discarding_primitives():
    """Re-declaring a staged anchor preserves primitives already attached to it."""
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "anchor-update")
    service.create_meter(
        scene,
        CreateMeterRequest(
            draft_id="anchor-update",
            anchor="character:Model",
            id="focus",
            min=0,
            max=5,
            value=2,
        ),
    )

    draft = service.create_anchor(
        scene,
        CreateAnchorRequest(
            draft_id="anchor-update",
            kind="character",
            id="Model",
            tags=["active"],
            meta={"role": "lead"},
        ),
    )

    anchor = draft.anchors["character:Model"]
    assert anchor.tags == ["active"]
    assert anchor.meta == {"role": "lead"}
    assert anchor.primitives["meters"]["focus"]["value"] == 2


@pytest.mark.parametrize(
    ("category", "stage"),
    [
        (
            "deck",
            lambda service, scene: service.create_deck(
                scene,
                CreateDeckRequest(
                    draft_id="duplicates",
                    id="same",
                    name="Deck",
                    mode="bag",
                    cards=[{"id": "card", "label": "Card"}],
                ),
            ),
        ),
        (
            "roll table",
            lambda service, scene: service.create_roll_table(
                scene,
                CreateRollTableRequest(
                    draft_id="duplicates",
                    id="same",
                    name="Table",
                    mode="weighted",
                    rows=[{"id": "row", "label": "Row", "weight": 1}],
                ),
            ),
        ),
        (
            "modifier",
            lambda service, scene: service.create_modifier(
                scene,
                CreateModifierRequest(
                    draft_id="duplicates",
                    id="same",
                    applies_to="table",
                    operation={"add": 1},
                ),
            ),
        ),
        (
            "relationship anchor",
            lambda service, scene: service.create_relationship(
                scene,
                CreateRelationshipRequest(
                    draft_id="duplicates",
                    source="Alice",
                    target="Bob",
                    dimensions=[{"id": "trust", "value": 1}],
                ),
            ),
        ),
        (
            "meter",
            lambda service, scene: service.create_meter(
                scene,
                CreateMeterRequest(
                    draft_id="duplicates",
                    anchor="scene:main",
                    id="same",
                    min=0,
                    max=5,
                    value=1,
                ),
            ),
        ),
        (
            "clock",
            lambda service, scene: service.create_clock(
                scene,
                CreateClockRequest(
                    draft_id="duplicates",
                    anchor="scene:main",
                    id="same",
                    max=4,
                ),
            ),
        ),
        (
            "attribute",
            lambda service, scene: service.create_attribute_source(
                scene,
                CreateAttributeSourceRequest(
                    draft_id="duplicates",
                    anchor="scene:main",
                    id="same",
                    source="literal",
                    value="value",
                    render_policy="hidden",
                ),
            ),
        ),
    ],
)
def test_duplicate_staged_ids_are_rejected_for_each_category(category, stage):
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "duplicates")

    stage(service, scene)

    with pytest.raises(ValueError, match=f"Duplicate staged {category} id"):
        stage(service, scene)
