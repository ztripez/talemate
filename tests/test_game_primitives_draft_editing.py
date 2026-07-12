"""Domain contracts for UI draft replacement and deletion change sets."""

import copy

import pydantic
import pytest

from talemate.character import Character
from talemate.game.primitives.adventure import AdventureEngine
from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.authoring.deletion_preview import (
    PrimitiveDeletionPreviewService,
)
from talemate.game.primitives.authoring.editing import PrimitiveDraftEditingService
from talemate.game.primitives.authoring.relationships import RelationshipAuthoringService
from talemate.game.primitives.authoring.schema import CreateMeterRequest
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.decks import DeckEngine
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.store import PrimitiveStore
from talemate.server.world_state_manager.game_primitives_relationship_requests import (
    UpsertRelationshipDimensionChange,
)
from talemate.tale_mate import Scene


def _revision(scene: Scene) -> str:
    return PrimitiveStore.read_snapshot_for_scene(scene).revision_token()


def test_deletion_preview_service_builds_detached_typed_candidates():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 2},
    )
    before = copy.deepcopy(store.root)
    service = PrimitiveDeletionPreviewService()

    anchor_preview = service.preview_anchor(
        scene,
        AnchorRef.parse("scene:main"),
        expected_revision=_revision(scene),
    )
    primitive_preview = service.preview_primitive(
        scene,
        PrimitiveRef.parse("scene:main/meters/focus"),
        expected_revision=_revision(scene),
    )

    assert anchor_preview.draft.deletions.anchors == ["scene:main"]
    assert anchor_preview.candidate.get_anchor("scene:main") is None
    assert primitive_preview.draft.deletions.primitives == [
        "scene:main/meters/focus"
    ]
    assert primitive_preview.candidate.get_primitive(
        "scene:main/meters/focus"
    ) is None
    assert store.root == before


def test_relationship_authoring_service_commits_cleared_draft_atomically():
    scene = Scene()
    scene.character_data.update(
        {"Alice": Character(name="Alice"), "Bob": Character(name="Bob")}
    )
    service = RelationshipAuthoringService()

    committed = service.author(
        scene,
        "Alice",
        "Bob",
        UpsertRelationshipDimensionChange(
            operation="upsert_dimension",
            dimension={"id": "trust", "min": -5, "max": 5, "value": 2},
        ),
        expected_revision=_revision(scene),
    )

    assert committed.status == "committed"
    assert committed.anchors == {}
    assert RelationshipGraph().get(scene, "Alice", "Bob", "trust") == 2


def test_ui_upsert_replaces_one_primitive_without_replacing_its_anchor():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_anchor_tags("scene:main", ["committed"])
    store.set_primitive(
        "scene:main/meters/focus", {"id": "focus", "min": 0, "max": 5, "value": 1}
    )
    store.set_primitive("scene:main/lists/notes", {"value": ["keep"]})
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "edit", expected_revision=_revision(scene))

    draft = editing.upsert_primitive(
        scene,
        "edit",
        PrimitiveRef.model_validate("scene:main/meters/focus"),
        {"id": "focus", "min": 0, "max": 5, "value": 4},
        expected_revision=_revision(scene),
    )

    assert draft.replacements.primitives == ["scene:main/meters/focus"]
    editing.commit_draft(scene, "edit", expected_revision=_revision(scene))
    assert store.get_primitive("scene:main/meters/focus")["value"] == 4
    assert store.get_primitive("scene:main/lists/notes") == {"value": ["keep"]}
    assert store.get_anchor("scene:main")["tags"] == ["committed"]


def test_deleting_staged_only_primitive_removes_implicit_empty_anchor():
    """Cancelling a primitive create does not commit an empty parent anchor."""
    scene = Scene()
    service = PrimitiveDraftEditingService()
    service.create_draft(scene, "cancel-create", expected_revision=_revision(scene))
    ref = PrimitiveRef.parse("object:Box/meters/focus")
    service.upsert_primitive(
        scene,
        "cancel-create",
        ref,
        {"id": "focus", "min": 0, "max": 5, "value": 1},
        expected_revision=_revision(scene),
    )

    draft = service.delete_primitive(
        scene,
        "cancel-create",
        ref,
        expected_revision=_revision(scene),
    )

    assert "object:Box" not in draft.anchors
    service.commit_draft(scene, "cancel-create", expected_revision=_revision(scene))
    assert PrimitiveStore.for_scene(scene).get_anchor("object:Box") is None


def test_intentional_definition_and_anchor_metadata_replacements_commit_cleanly():
    """UI upserts replace named targets while preserving unrelated anchor primitives."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "meters", "focus", {"id": "focus", "min": 0, "max": 5, "value": 1}
    )
    store.set_anchor_tags("scene:main", ["old"])
    store.ensure_anchor("scene:main")["meta"] = {"chapter": 1, "remove": True}
    store.set_primitive("scene:main/lists/notes", {"value": ["keep"]})
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "replace", expected_revision=_revision(scene))

    editing.upsert_definition(
        scene,
        "replace",
        "meters",
        "focus",
        {"id": "focus", "min": 0, "max": 10, "value": 7},
        expected_revision=_revision(scene),
    )
    draft = editing.upsert_anchor(
        scene,
        "replace",
        AnchorRef.parse("scene:main"),
        tags=["new"],
        meta={"chapter": 2},
        expected_revision=_revision(scene),
    )

    assert [(item.kind, item.id) for item in draft.replacements.definitions] == [
        ("meters", "focus")
    ]
    assert draft.replacements.anchors == ["scene:main"]
    committed = editing.commit_draft(
        scene, "replace", expected_revision=_revision(scene)
    )
    assert committed.status == "committed"
    assert store.get_definition("meters", "focus")["value"] == 7
    assert store.get_anchor("scene:main")["tags"] == ["new"]
    assert store.get_anchor("scene:main")["meta"] == {"chapter": 2}
    assert store.get_primitive("scene:main/lists/notes") == {"value": ["keep"]}


def test_accidental_primitive_collision_is_rejected_without_committed_mutation():
    """A staged create cannot overwrite a committed primitive absent replacement intent."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 1},
    )
    authoring = PrimitiveAuthoringService()
    authoring.create_draft(scene, "collision", expected_revision=_revision(scene))
    authoring.create_meter(
        scene,
        CreateMeterRequest(
            draft_id="collision",
            anchor="scene:main",
            id="focus",
            min=0,
            max=5,
            value=4,
            expected_revision=_revision(scene),
        ),
    )
    committed_before = copy.deepcopy(store.get_primitive("scene:main/meters/focus"))

    validation = authoring.validate_draft(
        scene, "collision", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert "Primitive already exists: scene:main/meters/focus" in validation.errors
    with pytest.raises(ValueError, match="validation failed"):
        authoring.commit_draft(scene, "collision", expected_revision=_revision(scene))
    assert store.get_primitive("scene:main/meters/focus") == committed_before


def test_definition_tombstone_rejects_dangling_refs_without_cascade_or_mutation():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "roll_tables",
        "weather",
        {
            "id": "weather",
            "name": "Weather",
            "mode": "weighted",
            "rows": [{"id": "sun", "label": "Sun", "weight": 1}],
        },
    )
    store.set_primitive("scene:main/roll_tables/local", {"definition": "weather"})
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "delete", expected_revision=_revision(scene))
    draft = editing.delete_definition(
        scene,
        "delete",
        "roll_tables",
        "weather",
        expected_revision=_revision(scene),
    )
    before = copy.deepcopy(store.root)

    assert [(item.kind, item.id) for item in draft.deletions.definitions] == [
        ("roll_tables", "weather")
    ]
    with pytest.raises(ValueError, match="validation failed"):
        editing.commit_draft(scene, "delete", expected_revision=_revision(scene))

    assert store.root == before
    assert store.get_definition("roll_tables", "weather") is not None
    assert store.get_primitive("scene:main/roll_tables/local") is not None


def test_explicit_unreferenced_tombstones_commit_without_implicit_cascades():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "meters", "unused", {"id": "unused", "min": 0, "max": 1, "value": 0}
    )
    store.set_primitive(
        "scene:main/meters/focus", {"id": "focus", "min": 0, "max": 5, "value": 2}
    )
    store.set_primitive("object:Box/lists/contents", {"value": ["coin"]})
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "delete-safe", expected_revision=_revision(scene))

    editing.delete_definition(
        scene,
        "delete-safe",
        "meters",
        "unused",
        expected_revision=_revision(scene),
    )
    editing.delete_primitive(
        scene,
        "delete-safe",
        PrimitiveRef.model_validate("scene:main/meters/focus"),
        expected_revision=_revision(scene),
    )
    draft = editing.delete_anchor(
        scene,
        "delete-safe",
        AnchorRef.model_validate("object:Box"),
        expected_revision=_revision(scene),
    )

    assert draft.deletions.primitives == ["scene:main/meters/focus"]
    assert draft.deletions.anchors == ["object:Box"]
    editing.commit_draft(scene, "delete-safe", expected_revision=_revision(scene))
    assert store.get_definition("meters", "unused") is None
    assert store.get_primitive("scene:main/meters/focus") is None
    assert store.get_anchor("object:Box") is None
    assert store.get_anchor("scene:main") is not None


def test_deck_replacement_checks_existing_runtime_card_ids():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "events",
        {
            "id": "events",
            "name": "Events",
            "mode": "physical",
            "cards": [
                {"id": "first", "label": "First"},
                {"id": "second", "label": "Second"},
            ],
        },
    )
    DeckEngine().reset(scene, "events")
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "deck-edit", expected_revision=_revision(scene))
    editing.upsert_definition(
        scene,
        "deck-edit",
        "decks",
        "events",
        {
            "id": "events",
            "name": "Events",
            "mode": "physical",
            "cards": [{"id": "first", "label": "First"}],
        },
        expected_revision=_revision(scene),
    )

    validation = editing.validate_draft(
        scene, "deck-edit", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert any("unknown card IDs" in error for error in validation.errors)


def test_deck_replacement_rejects_runtime_mode_incompatible_with_definition():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "events",
        {
            "id": "events",
            "name": "Events",
            "mode": "physical",
            "cards": [{"id": "first", "label": "First"}],
        },
    )
    DeckEngine().reset(scene, "events")
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "mode", expected_revision=_revision(scene))
    editing.upsert_definition(
        scene,
        "mode",
        "decks",
        "events",
        {
            "id": "events",
            "name": "Events",
            "mode": "sample",
            "cards": [{"id": "first", "label": "First"}],
        },
        expected_revision=_revision(scene),
    )

    validation = editing.validate_draft(
        scene, "mode", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert validation.errors == [
        "Deck runtime mode for scene:main/decks/events is 'physical', expected 'sample'"
    ]


def test_active_adventure_replacement_checks_complete_runtime_history():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "adventures",
        "demo",
        {
            "id": "demo",
            "title": "Demo",
            "start_scene": "start",
            "scenes": {
                "start": {"id": "start", "title": "Start"},
                "next": {"id": "next", "title": "Next"},
            },
            "transitions": {
                "continue": {
                    "id": "continue",
                    "from_scene": "start",
                    "to_scene": "next",
                    "label": "Continue",
                }
            },
        },
    )
    AdventureEngine().activate(scene, "demo")
    AdventureEngine().take_transition(scene, "continue")
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "adventure-edit", expected_revision=_revision(scene))
    editing.upsert_definition(
        scene,
        "adventure-edit",
        "adventures",
        "demo",
        {
            "id": "demo",
            "title": "Demo",
            "start_scene": "start",
            "scenes": {"start": {"id": "start", "title": "Start"}},
        },
        expected_revision=_revision(scene),
    )

    errors = editing.validate_draft(
        scene, "adventure-edit", expected_revision=_revision(scene)
    ).validation.errors

    assert any("current story scene does not exist: next" in error for error in errors)
    assert any("visited story scene does not exist: next" in error for error in errors)
    assert any("transition does not exist: continue" in error for error in errors)

    editing.create_draft(
        scene, "adventure-history-edit", expected_revision=_revision(scene)
    )
    editing.upsert_definition(
        scene,
        "adventure-history-edit",
        "adventures",
        "demo",
        {
            "id": "demo",
            "title": "Demo",
            "start_scene": "next",
            "scenes": {"next": {"id": "next", "title": "Next"}},
        },
        expected_revision=_revision(scene),
    )
    history_errors = editing.validate_draft(
        scene, "adventure-history-edit", expected_revision=_revision(scene)
    ).validation.errors
    assert any(
        "visited story scene does not exist: start" in error for error in history_errors
    )
    assert any(
        "completed story scene does not exist: start" in error
        for error in history_errors
    )


def test_active_adventure_definition_deletion_is_rejected():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "adventures",
        "demo",
        {
            "id": "demo",
            "title": "Demo",
            "start_scene": "start",
            "scenes": {"start": {"id": "start", "title": "Start"}},
        },
    )
    AdventureEngine().activate(scene, "demo")
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "delete-active", expected_revision=_revision(scene))
    editing.delete_definition(
        scene,
        "delete-active",
        "adventures",
        "demo",
        expected_revision=_revision(scene),
    )

    validation = editing.validate_draft(
        scene, "delete-active", expected_revision=_revision(scene)
    ).validation

    assert validation.ok is False
    assert validation.errors == ["Active adventure definition not found: demo"]


@pytest.mark.parametrize(
    ("transition_change", "expected"),
    [
        (
            {"from_scene": "next"},
            "Active adventure transition log is incompatible: continue",
        ),
        (
            {"to_scene": "start"},
            "Active adventure transition log is incompatible: continue",
        ),
        (
            {"carry_anchors": []},
            "Active adventure transition log is incompatible: continue",
        ),
    ],
    ids=["history-source", "history-destination", "history-carry-anchors"],
)
def test_active_adventure_replacement_preserves_transition_history_contract(
    transition_change: dict, expected: str
):
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.ensure_anchor("character:Hero")
    definition = {
        "id": "demo",
        "title": "Demo",
        "start_scene": "start",
        "scenes": {
            "start": {"id": "start", "title": "Start"},
            "next": {"id": "next", "title": "Next"},
        },
        "transitions": {
            "continue": {
                "id": "continue",
                "from_scene": "start",
                "to_scene": "next",
                "label": "Continue",
                "carry_anchors": ["character:Hero"],
            }
        },
    }
    store.set_definition("adventures", "demo", definition)
    AdventureEngine().activate(scene, "demo")
    AdventureEngine().take_transition(scene, "continue")
    replacement = copy.deepcopy(definition)
    replacement["transitions"]["continue"].update(transition_change)
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "history", expected_revision=_revision(scene))
    editing.upsert_definition(
        scene,
        "history",
        "adventures",
        "demo",
        replacement,
        expected_revision=_revision(scene),
    )

    validation = editing.validate_draft(
        scene, "history", expected_revision=_revision(scene)
    ).validation

    assert expected in validation.errors


def test_deleting_adventure_local_and_carry_anchors_is_rejected_without_cascade():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.ensure_anchor("location:Camp")
    store.ensure_anchor("character:Hero")
    store.set_definition(
        "adventures",
        "demo",
        {
            "id": "demo",
            "title": "Demo",
            "start_scene": "start",
            "scenes": {
                "start": {
                    "id": "start",
                    "title": "Start",
                    "local_anchors": ["location:Camp"],
                },
                "next": {"id": "next", "title": "Next"},
            },
            "transitions": {
                "continue": {
                    "id": "continue",
                    "from_scene": "start",
                    "to_scene": "next",
                    "label": "Continue",
                    "carry_anchors": ["character:Hero"],
                }
            },
        },
    )
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "anchors", expected_revision=_revision(scene))
    editing.delete_anchor(
        scene,
        "anchors",
        AnchorRef.parse("location:Camp"),
        expected_revision=_revision(scene),
    )
    editing.delete_anchor(
        scene,
        "anchors",
        AnchorRef.parse("character:Hero"),
        expected_revision=_revision(scene),
    )
    before = copy.deepcopy(store.root)

    validation = editing.validate_draft(
        scene, "anchors", expected_revision=_revision(scene)
    ).validation

    assert "Missing adventure local anchor: location:Camp" in validation.errors
    assert "Missing adventure carried anchor: character:Hero" in validation.errors
    with pytest.raises(ValueError, match="validation failed"):
        editing.commit_draft(scene, "anchors", expected_revision=_revision(scene))
    assert store.get_anchor("location:Camp") is not None
    assert store.get_anchor("character:Hero") is not None
    assert store.root["definitions"] == before["definitions"]


def test_stale_commit_and_missing_changes_fail_without_mutation():
    scene = Scene()
    editing = PrimitiveDraftEditingService()
    editing.create_draft(scene, "stale", expected_revision=_revision(scene))
    stale_revision = _revision(scene)
    editing.upsert_primitive(
        scene,
        "stale",
        PrimitiveRef.model_validate("scene:main/meters/focus"),
        {"id": "focus", "min": 0, "max": 1, "value": 1},
        expected_revision=stale_revision,
    )
    store = PrimitiveStore.for_scene(scene)
    before = copy.deepcopy(store.root)

    with pytest.raises(PrimitiveStoreError, match="Stale Game Primitives revision"):
        editing.commit_draft(scene, "stale", expected_revision=stale_revision)
    assert store.root == before

    with pytest.raises(PrimitiveStoreError, match="not found"):
        editing.delete_primitive(
            scene,
            "stale",
            PrimitiveRef.model_validate("scene:main/clocks/does-not-exist"),
            expected_revision=_revision(scene),
        )
    assert store.root == before


def test_persisted_draft_models_revalidate_mutated_instances():
    from talemate.game.primitives.draft_schema import (
        DraftChangeTargets,
        PrimitiveDraft,
    )

    targets = DraftChangeTargets(anchors=["scene:main"])
    targets.anchors.append("malformed")
    with pytest.raises(pydantic.ValidationError):
        PrimitiveDraft(id="strict", replacements=targets)


def test_snapshot_root_copy_is_detached_from_snapshot_and_scene():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    snapshot = PrimitiveStore.read_snapshot_for_scene(scene)
    candidate = snapshot.detached_root_model()

    candidate.runtime["changed"] = True

    assert snapshot.get_runtime("changed") is None
    assert store.get_runtime("changed") is None


def test_every_ui_draft_mutation_rejects_a_stale_revision_without_mutation():
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "meters", "focus", {"id": "focus", "min": 0, "max": 5, "value": 1}
    )
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 1},
    )
    editing = PrimitiveDraftEditingService()
    editing.create_draft(
        scene,
        "edit",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )
    stale = _revision(scene)
    store.set_anchor_tags("scene:main", ["newer"])
    before = copy.deepcopy(store.root)
    anchor = AnchorRef.model_validate("scene:main")
    ref = PrimitiveRef.model_validate("scene:main/meters/focus")

    mutations = [
        lambda: editing.create_draft(scene, "other", expected_revision=stale),
        lambda: editing.delete_draft(scene, "edit", expected_revision=stale),
        lambda: editing.upsert_definition(
            scene,
            "edit",
            "meters",
            "focus",
            {"id": "focus", "min": 0, "max": 5, "value": 2},
            expected_revision=stale,
        ),
        lambda: editing.upsert_anchor(
            scene,
            "edit",
            anchor,
            tags=[],
            meta={},
            expected_revision=stale,
        ),
        lambda: editing.upsert_primitive(
            scene,
            "edit",
            ref,
            {"id": "focus", "min": 0, "max": 5, "value": 2},
            expected_revision=stale,
        ),
        lambda: editing.delete_definition(
            scene, "edit", "meters", "focus", expected_revision=stale
        ),
        lambda: editing.delete_anchor(scene, "edit", anchor, expected_revision=stale),
        lambda: editing.delete_primitive(scene, "edit", ref, expected_revision=stale),
        lambda: editing.validate_draft(scene, "edit", expected_revision=stale),
        lambda: editing.commit_draft(scene, "edit", expected_revision=stale),
    ]
    for mutate in mutations:
        with pytest.raises(PrimitiveStoreError, match="Stale Game Primitives revision"):
            mutate()
        assert store.root == before
