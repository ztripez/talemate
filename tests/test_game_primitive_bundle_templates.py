"""Round-trip and atomicity tests for Game Primitive bundle templates."""

import copy

import pytest
import yaml
from pydantic import ValidationError

from talemate.game.primitives.authoring.bundles import (
    BundleSelection,
    GamePrimitiveBundleService,
)
from talemate.game.primitives.containers import AnchorPayload
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.store import PrimitiveStore
from talemate.server.world_state_manager.game_primitives_bundle_requests import (
    CaptureGamePrimitiveBundlePayload,
)
from talemate.tale_mate import Scene
from talemate.world_state.templates.base import Group
from talemate.world_state.templates.game_primitive_bundle import GamePrimitiveBundle


def _authored_scene() -> Scene:
    scene = Scene()
    root = PrimitiveStore.read_snapshot_for_scene(scene).detached_root_model()
    root.definitions.set_item(
        "meters", "focus", {"id": "focus", "min": 0, "max": 5, "value": 2}
    )
    root.anchors["project:main"] = AnchorPayload.model_validate({
        "tags": ["global"],
        "primitives": {"meters": {"focus": {"id": "focus", "min": 0, "max": 5, "value": 2}}},
        "meta": {},
    })
    PrimitiveStore.for_scene(scene).replace_validated_root(root)
    return scene


def test_bundle_yaml_and_polymorphic_group_round_trip(tmp_path):
    bundle = GamePrimitiveBundle(name="Core", definitions={"meters": {"focus": {"id": "focus", "min": 0, "max": 5, "value": 2}}})
    group = Group(author="tester", name="bundles", description="", templates={bundle.uid: bundle})
    group.save(str(tmp_path))

    raw = yaml.safe_load((tmp_path / "bundles.yaml").read_text())
    loaded = Group.load(str(tmp_path / "bundles.yaml"))

    assert raw["templates"][bundle.uid]["bundle_schema_version"] == 1
    assert isinstance(loaded.templates[bundle.uid], GamePrimitiveBundle)
    assert loaded.templates[bundle.uid] == bundle.model_copy(update={"group": group.uid})


def test_bundle_rejects_runtime_progress_and_unknown_payloads():
    for field in ("runtime", "ledger", "drafts", "active_adventure"):
        with pytest.raises(ValidationError):
            GamePrimitiveBundle(name="Invalid", **{field: {}})

    with pytest.raises(ValidationError):
        GamePrimitiveBundle(name="Invalid", definitions={"future_group": {}})
    with pytest.raises(ValidationError):
        GamePrimitiveBundle(
            name="Invalid",
            anchors={"project:main": {"primitives": {"future_group": {}}}},
        )
    with pytest.raises(ValidationError):
        GamePrimitiveBundle(
            name="Invalid",
            definitions={"meters": {"focus": {"id": "focus", "value": "2"}}},
        )


def test_bundle_allows_declared_generic_canonical_collections():
    bundle = GamePrimitiveBundle(
        name="Generic",
        definitions={
            "relationship_models": {"trust": {"label": "Trust"}},
            "attribute_sources": {"mood": {"value": "hopeful"}},
        },
    )

    assert bundle.definitions.relationship_models["trust"].root == {
        "label": "Trust"
    }
    assert bundle.definitions.attribute_sources["mood"].root == {
        "value": "hopeful"
    }


@pytest.mark.parametrize(
    ("source", "draft_id"), (("committed", "draft-1"), ("draft", None))
)
def test_capture_request_enforces_source_draft_contract(source, draft_id):
    with pytest.raises(ValidationError):
        CaptureGamePrimitiveBundlePayload.model_validate(
            {
                "type": "world_state_manager",
                "action": "capture_game_primitive_bundle",
                "request_id": "request-1",
                "name": "Core",
                "source": source,
                "expected_revision": "revision",
                "draft_id": draft_id,
                "selection": {},
            }
        )


def test_capture_and_apply_are_detached_and_atomic():
    source = _authored_scene()
    bundle = GamePrimitiveBundleService.capture(
        source,
        name="Core",
        source="committed",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(source).revision_token(),
        selection=BundleSelection(definitions=["meters/focus"], anchors=["project:main"]),
    )
    target = Scene()
    revision = PrimitiveStore.read_snapshot_for_scene(target).revision_token()

    result = GamePrimitiveBundleService.apply(target, bundle, expected_revision=revision)
    draft = PrimitiveStore.read_snapshot_for_scene(target).iter_drafts()[result.draft_id]

    assert draft["definitions"]["meters"]["focus"]["value"] == 2
    assert draft["anchors"]["project:main"]["tags"] == ["global"]
    bundle.definitions.meters["focus"].value = 4
    assert PrimitiveStore.read_snapshot_for_scene(target).iter_drafts()[result.draft_id]["definitions"]["meters"]["focus"]["value"] == 2


def test_collision_and_repeated_apply_never_partially_mutate():
    source = _authored_scene()
    bundle = GamePrimitiveBundleService.capture(
        source,
        name="Core",
        source="committed",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(source).revision_token(),
        selection=BundleSelection(definitions=["meters/focus"], anchors=["project:main"]),
    )
    target = Scene()
    revision = PrimitiveStore.read_snapshot_for_scene(target).revision_token()
    applied = GamePrimitiveBundleService.apply(target, bundle, expected_revision=revision)
    before = copy.deepcopy(target.game_state.variables)
    preview = GamePrimitiveBundleService.preview(
        target, bundle, expected_revision=applied.revision, draft_id=applied.draft_id
    )

    assert {collision.ref for collision in preview.collisions} == {"meters/focus", "project:main"}
    with pytest.raises(PrimitiveStoreError, match="collisions"):
        GamePrimitiveBundleService.apply(
            target, bundle, expected_revision=applied.revision, draft_id=applied.draft_id
        )
    assert target.game_state.variables == before


def test_repeated_apply_without_draft_id_detects_all_persisted_drafts():
    bundle = GamePrimitiveBundle(
        name="Core",
        definitions={
            "meters": {"focus": {"id": "focus", "min": 0, "max": 5, "value": 2}}
        },
    )
    scene = Scene()
    first = GamePrimitiveBundleService.apply(
        scene,
        bundle,
        expected_revision=PrimitiveStore.read_snapshot_for_scene(scene).revision_token(),
    )
    before = copy.deepcopy(scene.game_state.variables)

    preview = GamePrimitiveBundleService.preview(
        scene, bundle, expected_revision=first.revision
    )
    assert [collision.model_dump() for collision in preview.collisions] == [
        {"resource": "definition", "ref": "meters/focus", "location": "draft"}
    ]
    with pytest.raises(PrimitiveStoreError, match="meters/focus"):
        GamePrimitiveBundleService.apply(
            scene, bundle, expected_revision=first.revision
        )
    assert scene.game_state.variables == before


def test_committed_anchor_collision_rejects_preview_and_apply_without_mutation():
    scene = Scene()
    root = PrimitiveStore.read_snapshot_for_scene(scene).detached_root_model()
    root.anchors["project:main"] = AnchorPayload()
    PrimitiveStore.for_scene(scene).replace_validated_root(root)
    bundle = GamePrimitiveBundle(
        name="Core", anchors={"project:main": AnchorPayload()}
    )
    revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
    before = copy.deepcopy(scene.game_state.variables)

    preview = GamePrimitiveBundleService.preview(
        scene, bundle, expected_revision=revision
    )
    assert [collision.model_dump() for collision in preview.collisions] == [
        {"resource": "anchor", "ref": "project:main", "location": "committed"}
    ]
    assert scene.game_state.variables == before
    with pytest.raises(PrimitiveStoreError, match="project:main"):
        GamePrimitiveBundleService.apply(
            scene, bundle, expected_revision=revision
        )
    assert scene.game_state.variables == before


@pytest.mark.parametrize(("source", "draft_id"), (("committed", None), ("draft", "missing")))
def test_capture_rejects_stale_revision_before_selection_without_mutation(
    source, draft_id
):
    scene = _authored_scene()
    before = copy.deepcopy(scene.game_state.variables)

    with pytest.raises(PrimitiveStoreError, match="Stale Game Primitives revision"):
        GamePrimitiveBundleService.capture(
            scene,
            name="Core",
            source=source,
            expected_revision="stale",
            draft_id=draft_id,
            selection=BundleSelection(definitions=["meters/missing"]),
        )

    assert scene.game_state.variables == before


def test_bundle_yaml_ingestion_is_strict(tmp_path):
    bundle = GamePrimitiveBundle(name="Core")
    group = Group(
        author="tester", name="bundles", description="", templates={bundle.uid: bundle}
    )
    group.save(str(tmp_path))
    path = tmp_path / "bundles.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["templates"][bundle.uid]["bundle_schema_version"] = "1"
    path.write_text(yaml.safe_dump(raw))

    with pytest.raises(ValidationError):
        Group.load(str(path))
