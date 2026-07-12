"""End-to-end QA contracts for reusable Game Primitive bundles."""

from __future__ import annotations

import copy
import json
from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from talemate.game.primitives.authoring.bundles import BundleSelection
from talemate.game.primitives.containers import AnchorPayload
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.store import PrimitiveStore
from talemate.server.world_state_manager import WorldStateManagerPlugin
from talemate.server.world_state_manager.game_primitives_request_contracts import (
    GAME_PRIMITIVES_REQUEST_ADAPTER,
)
from talemate.server.world_state_manager.game_primitives_snapshot import (
    build_game_primitives_snapshot,
)
from talemate.tale_mate import Scene
from talemate.world_state.templates.game_primitive_bundle import GamePrimitiveBundle


def _definitions() -> dict:
    return {
        "meters": {
            "focus": {"id": "focus", "min": 0, "max": 5, "value": 2}
        }
    }


def _anchor(value: int = 2) -> dict:
    return {
        "tags": ["authored"],
        "meta": {"chapter": 1},
        "primitives": {
            "meters": {
                "focus": {"id": "focus", "min": 0, "max": 5, "value": value}
            }
        },
    }


def _bundle(uid: str = "bundle") -> GamePrimitiveBundle:
    return GamePrimitiveBundle(
        uid=uid,
        name="Starter",
        group="group",
        definitions=_definitions(),
        anchors={"scene:main": _anchor()},
    )


def _plugin(scene: Scene, monkeypatch, template=None):
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    manager = MagicMock()
    manager.save_template = AsyncMock()
    manager.template_collection.find_template.return_value = template
    monkeypatch.setattr(
        WorldStateManagerPlugin,
        "world_state_manager",
        property(lambda _self: manager),
    )
    return WorldStateManagerPlugin(handler), queued, manager


async def _request(plugin, queued, action: str, request_id: str, **fields):
    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": request_id,
            **fields,
        }
    )
    return copy.deepcopy(queued)


@pytest.mark.asyncio
async def test_websocket_capture_committed_and_draft_are_exact_and_detached(monkeypatch):
    scene = Scene()
    scene.config.game.general.auto_save = False
    store = PrimitiveStore.for_scene(scene)
    store.set_definition("meters", "focus", _definitions()["meters"]["focus"])
    store.set_anchor_tags("scene:main", ["authored"])
    store.set_primitive("scene:main/meters/focus", _definitions()["meters"]["focus"])
    store.root["anchors"]["scene:main"]["meta"] = {"chapter": 1}
    draft = PrimitiveDraft(id="source", definitions=_definitions())
    draft.anchors["scene:draft"] = AnchorPayload.model_validate(_anchor(4))
    candidate = copy.deepcopy(store.root)
    candidate["drafts"][draft.id] = draft.model_dump(mode="json")
    store.replace_validated_root(candidate)
    plugin, queued, _ = _plugin(scene, monkeypatch)

    revision = plugin._primitive_revision()
    committed = await _request(
        plugin,
        queued,
        "capture_game_primitive_bundle",
        "capture-committed",
        name="Committed",
        source="committed",
        expected_revision=revision,
        draft_id=None,
        selection={"definitions": ["meters/focus"], "anchors": ["scene:main"]},
    )
    assert len(committed) == 1
    assert set(committed[0]) == {"type", "action", "request_id", "revision", "data"}
    assert committed[0]["type"] == "world_state_manager"
    assert committed[0]["action"] == "game_primitive_bundle_captured"
    assert committed[0]["request_id"] == "capture-committed"
    assert committed[0]["revision"] == revision
    assert committed[0]["data"] == GamePrimitiveBundle.model_validate(
        committed[0]["data"]
    ).model_dump(mode="json")
    assert committed[0]["data"]["name"] == "Committed"
    assert committed[0]["data"]["definitions"]["meters"]["focus"]["value"] == 2
    assert committed[0]["data"]["anchors"]["scene:main"]["meta"] == {"chapter": 1}

    drafted = await _request(
        plugin,
        queued,
        "capture_game_primitive_bundle",
        "capture-draft",
        name="Draft",
        source="draft",
        expected_revision=revision,
        draft_id="source",
        selection={"definitions": ["meters/focus"], "anchors": ["scene:draft"]},
    )
    assert drafted[0]["action"] == "game_primitive_bundle_captured"
    assert drafted[0]["request_id"] == "capture-draft"
    assert drafted[0]["revision"] == revision
    assert drafted[0]["data"]["anchors"] == {
        "scene:draft": AnchorPayload.model_validate(_anchor(4)).model_dump(mode="json")
    }
    drafted[0]["data"]["anchors"]["scene:draft"]["meta"]["chapter"] = 99
    assert PrimitiveStore.for_scene(scene).root["drafts"]["source"]["anchors"][
        "scene:draft"
    ]["meta"] == {"chapter": 1}


@pytest.mark.asyncio
async def test_websocket_preview_apply_validate_commit_and_snapshot(monkeypatch):
    scene = Scene()
    scene.config.game.general.auto_save = False
    plugin, queued, manager = _plugin(scene, monkeypatch, _bundle())
    revision = plugin._primitive_revision()
    common = {
        "group_uid": "group",
        "template_uid": "bundle",
        "expected_revision": revision,
        "draft_id": None,
    }

    preview = await _request(
        plugin, queued, "preview_game_primitive_bundle", "preview", **common
    )
    assert preview == [
        {
            "type": "world_state_manager",
            "action": "game_primitive_bundle_application",
            "request_id": "preview",
            "data": {
                "applied": False,
                "draft_id": None,
                "revision": revision,
                "definition_count": 1,
                "anchor_count": 1,
                "collisions": [],
            },
        }
    ]
    assert scene.game_state.variables == {}

    applied = await _request(
        plugin, queued, "apply_game_primitive_bundle", "apply", **common
    )
    assert [message["action"] for message in applied] == [
        "game_primitive_bundle_application",
        "operation_done",
    ]
    application = applied[0]["data"]
    assert application["applied"] is True
    assert application["collisions"] == []
    assert application["revision"] != revision
    assert applied[0]["request_id"] == applied[1]["request_id"] == "apply"
    draft_id = application["draft_id"]

    validated = await _request(
        plugin,
        queued,
        "validate_game_primitive_draft",
        "validate",
        draft_id=draft_id,
        expected_revision=application["revision"],
    )
    assert validated[0]["data"]["status"] == "validated"
    assert validated[0]["data"]["validation"] == {
        "ok": True,
        "errors": [],
        "warnings": [],
    }
    committed = await _request(
        plugin,
        queued,
        "commit_game_primitive_draft",
        "commit",
        draft_id=draft_id,
        expected_revision=validated[0]["revision"],
    )
    assert committed[0] == {
        "type": "world_state_manager",
        "action": "game_primitives",
        "request_id": "commit",
        "data": build_game_primitives_snapshot(scene).model_dump(mode="json"),
    }
    assert committed[0]["data"]["definitions"][0]["id"] == "focus"
    assert committed[0]["data"]["anchors"][0]["ref"] == "scene:main"
    persisted = PrimitiveDraft.model_validate(
        PrimitiveStore.for_scene(scene).root["drafts"][draft_id]
    )
    assert persisted.status == "committed"
    manager.template_collection.find_template.assert_called_with("group", "bundle")


@pytest.mark.asyncio
async def test_websocket_repeated_new_draft_apply_fails_without_mutation(monkeypatch):
    scene = Scene()
    scene.config.game.general.auto_save = False
    plugin, queued, _ = _plugin(scene, monkeypatch, _bundle())
    fields = {
        "group_uid": "group",
        "template_uid": "bundle",
        "draft_id": None,
    }
    first = await _request(
        plugin,
        queued,
        "apply_game_primitive_bundle",
        "first",
        expected_revision=plugin._primitive_revision(),
        **fields,
    )
    before = copy.deepcopy(scene.game_state.variables)
    second = await _request(
        plugin,
        queued,
        "apply_game_primitive_bundle",
        "second",
        expected_revision=first[0]["data"]["revision"],
        **fields,
    )

    assert second[0]["action"] == "game_primitives_failed"
    assert second[0]["request_id"] == "second"
    assert second[0]["error"]["message"] == (
        "Game Primitive bundle collisions: meters/focus, scene:main"
    )
    assert scene.game_state.variables == before


@pytest.mark.asyncio
@pytest.mark.parametrize("template", [None, MagicMock()])
async def test_websocket_missing_or_wrong_template_is_correlated_and_atomic(
    monkeypatch, template
):
    scene = Scene()
    before = copy.deepcopy(scene.game_state.variables)
    plugin, queued, _ = _plugin(scene, monkeypatch, template)
    response = await _request(
        plugin,
        queued,
        "preview_game_primitive_bundle",
        "missing-template",
        group_uid="group",
        template_uid="missing",
        expected_revision=plugin._primitive_revision(),
        draft_id=None,
    )
    assert response == [
        {
            "type": "world_state_manager",
            "action": "game_primitives_failed",
            "request_id": "missing-template",
            "request_action": "preview_game_primitive_bundle",
            "error": {"message": "Game Primitive bundle template not found"},
        }
    ]
    assert scene.game_state.variables == before


@pytest.mark.asyncio
async def test_websocket_malformed_bundle_request_has_strict_correlated_failure(monkeypatch):
    scene = Scene()
    plugin, queued, _ = _plugin(scene, monkeypatch)
    before = copy.deepcopy(scene.game_state.variables)
    response = await _request(
        plugin,
        queued,
        "capture_game_primitive_bundle",
        "malformed-capture",
        name="Bad",
        source="committed",
        expected_revision=plugin._primitive_revision(),
        draft_id="not-allowed",
        selection={"definitions": [], "anchors": [], "unknown": True},
    )
    assert len(response) == 1
    assert set(response[0]) == {
        "type",
        "action",
        "request_id",
        "request_action",
        "error",
    }
    assert response[0]["action"] == "game_primitives_failed"
    assert response[0]["request_id"] == "malformed-capture"
    assert response[0]["request_action"] == "capture_game_primitive_bundle"
    assert "validation error" in response[0]["error"]["message"]
    assert scene.game_state.variables == before


@pytest.mark.parametrize(
    ("selection", "message"),
    [
        ({"definitions": ["meters/focus", "meters/focus"]}, "Duplicate definition"),
        ({"anchors": ["scene:main", "scene:main"]}, "Duplicate anchor"),
        ({"definitions": ["meters"]}, "kind/id"),
    ],
)
def test_selection_contract_rejects_duplicates_and_malformed_refs(selection, message):
    with pytest.raises(pydantic.ValidationError, match=message):
        BundleSelection.model_validate(selection)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selection",
    [
        {"definitions": ["meters/missing"], "anchors": []},
        {"definitions": [], "anchors": ["scene:missing"]},
    ],
)
async def test_unknown_capture_selections_fail_without_mutation(monkeypatch, selection):
    scene = Scene()
    plugin, queued, _ = _plugin(scene, monkeypatch)
    before = copy.deepcopy(scene.game_state.variables)
    response = await _request(
        plugin,
        queued,
        "capture_game_primitive_bundle",
        "unknown-selection",
        name="Unknown",
        source="committed",
        expected_revision=plugin._primitive_revision(),
        draft_id=None,
        selection=selection,
    )
    assert response[0]["action"] == "game_primitives_failed"
    assert "Selected " in response[0]["error"]["message"]
    assert scene.game_state.variables == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(bundle_schema_version=2),
        lambda value: value["definitions"].update(unknown={}),
        lambda value: value["definitions"]["meters"].update(
            bad={"id": "bad", "min": 0, "max": 5, "value": 2, "nested": {}}
        ),
        lambda value: value.update(anchors={"scene:main/": _anchor()}),
    ],
)
def test_bundle_rejects_schema_nested_definition_and_noncanonical_anchor(mutation):
    value = _bundle().model_dump(mode="json")
    mutation(value)
    with pytest.raises(pydantic.ValidationError):
        GamePrimitiveBundle.model_validate(value)


@pytest.mark.asyncio
async def test_collisions_cover_committed_draft_and_mixed_locations_atomically(monkeypatch):
    scene = Scene()
    scene.config.game.general.auto_save = False
    store = PrimitiveStore.for_scene(scene)
    store.set_definition("meters", "focus", _definitions()["meters"]["focus"])
    draft = PrimitiveDraft(id="target", definitions=_definitions())
    draft.anchors["scene:main"] = AnchorPayload.model_validate(_anchor())
    candidate = copy.deepcopy(store.root)
    candidate["drafts"]["target"] = draft.model_dump(mode="json")
    store.replace_validated_root(candidate)
    plugin, queued, _ = _plugin(scene, monkeypatch, _bundle())
    before = json.dumps(store.root, sort_keys=True, separators=(",", ":"))
    fields = {
        "group_uid": "group",
        "template_uid": "bundle",
        "expected_revision": plugin._primitive_revision(),
        "draft_id": "target",
    }

    preview = await _request(
        plugin, queued, "preview_game_primitive_bundle", "collision-preview", **fields
    )
    assert preview[0]["data"]["collisions"] == [
        {"resource": "definition", "ref": "meters/focus", "location": "committed"},
        {"resource": "definition", "ref": "meters/focus", "location": "draft"},
        {"resource": "anchor", "ref": "scene:main", "location": "draft"},
    ]
    failed = await _request(
        plugin, queued, "apply_game_primitive_bundle", "collision-apply", **fields
    )
    assert failed == [
        {
            "type": "world_state_manager",
            "action": "game_primitives_failed",
            "request_id": "collision-apply",
            "request_action": "apply_game_primitive_bundle",
            "error": {
                "message": "Game Primitive bundle collisions: meters/focus, meters/focus, scene:main"
            },
        }
    ]
    assert json.dumps(store.root, sort_keys=True, separators=(",", ":")) == before


@pytest.mark.asyncio
async def test_applied_draft_is_immutable_when_global_template_is_edited(monkeypatch):
    scene = Scene()
    scene.config.game.general.auto_save = False
    global_template = _bundle()
    plugin, queued, manager = _plugin(scene, monkeypatch, global_template)
    applied = await _request(
        plugin,
        queued,
        "apply_game_primitive_bundle",
        "detach",
        group_uid="group",
        template_uid="bundle",
        expected_revision=plugin._primitive_revision(),
        draft_id=None,
    )
    draft_id = applied[0]["data"]["draft_id"]
    root_before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)
    scene_before = copy.deepcopy(scene.game_state.variables)

    global_template.definitions.meters["focus"].value = 5
    global_template.anchors["scene:main"].meta["chapter"] = 99
    await manager.save_template(global_template)

    assert PrimitiveStore.for_scene(scene).root == root_before
    assert scene.game_state.variables == scene_before
    persisted = PrimitiveDraft.model_validate(root_before["drafts"][draft_id])
    assert persisted.definitions.meters["focus"].value == 2
    assert persisted.anchors["scene:main"].meta == {"chapter": 1}


def test_bundle_actions_are_in_strict_request_union():
    payload = {
        "type": "world_state_manager",
        "action": "apply_game_primitive_bundle",
        "request_id": "strict",
        "group_uid": "group",
        "template_uid": "bundle",
        "expected_revision": "revision",
        "draft_id": None,
    }
    assert GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(
        payload, strict=True
    ).request_id == "strict"
    with pytest.raises(pydantic.ValidationError, match="Extra inputs"):
        GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(
            {**payload, "unexpected": True}, strict=True
        )
