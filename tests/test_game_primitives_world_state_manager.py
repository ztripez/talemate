"""Domain and websocket contracts for the Game Primitives editor snapshot."""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from talemate.character import Character
from talemate.game.primitives.adventure import (
    AdventureDefinition,
    AdventureEngine,
    StorySceneDefinition,
)
from talemate.game.primitives.containers import PrimitiveDefinitions
from talemate.game.primitives.constants import GAME_PRIMITIVES_KEY
from talemate.game.primitives.definitions import (
    DEFINITION_KINDS,
    EDITABLE_DEFINITION_KINDS,
    MeterPayload,
)
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.exceptions import PrimitiveError, PrimitiveStoreError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.primitive_payloads import (
    EDITABLE_PRIMITIVE_KINDS,
    PRIMITIVE_KINDS,
)
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.schema import AnchorPayload
from talemate.game.primitives.store import PrimitiveStore
from talemate.server.world_state_manager import WorldStateManagerPlugin
from talemate.server.world_state_manager.game_primitives_request_contracts import (
    GAME_PRIMITIVES_REQUEST_ADAPTER,
    assert_game_primitives_transport_kind_coverage,
)
from talemate.server.world_state_manager.game_primitives_adventure_requests import (
    GetGamePrimitivesPayload,
)
from talemate.server.world_state_manager.game_primitives_anchor_instance_requests import (
    UpsertGamePrimitivePayload,
)
from talemate.server.world_state_manager.game_primitives_draft_definition_requests import (
    UpsertGamePrimitiveDefinitionPayload,
)
from talemate.server.world_state_manager.game_primitives_relationship_requests import (
    AuthorGamePrimitiveRelationshipPayload,
)
from talemate.server.world_state_manager.game_primitives_snapshot import (
    build_game_primitives_snapshot,
    get_game_primitive_editor_metadata,
)
from talemate.server.world_state_manager.game_primitives_common_responses import (
    GamePrimitivesIndeterminateResponse,
    GamePrimitivesResponse,
)
from talemate.server.world_state_manager.game_primitives_snapshot_projections import (
    AdventureStateSnapshot,
    DefinitionSnapshot,
    GamePrimitivesSnapshot,
)
from talemate.tale_mate import Scene


def _adventure() -> dict:
    return {
        "id": "demo",
        "title": "Demo Adventure",
        "description": "A test journey.",
        "start_scene": "arrival",
        "scenes": {
            "arrival": {
                "id": "arrival",
                "title": "Arrival",
                "goals": ["Find the path"],
            },
            "alpha": {"id": "alpha", "title": "Alpha"},
            "zeta": {"id": "zeta", "title": "Zeta"},
        },
        "transitions": {
            "z-transition": {
                "id": "z-transition",
                "from_scene": "arrival",
                "to_scene": "zeta",
                "label": "Zeta",
            },
            "a-transition": {
                "id": "a-transition",
                "from_scene": "arrival",
                "to_scene": "alpha",
                "label": "Alpha",
            },
        },
    }


def _populated_scene() -> Scene:
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "meters", "health", {"id": "health", "min": 0, "max": 10, "value": 7}
    )
    store.set_definition("adventures", "demo", _adventure())
    store.set_primitive(
        "character:Zed/meters/health",
        {"id": "health", "min": 0, "max": 10, "value": 7},
    )
    store.set_primitive("character:Ada/lists/clues", {"value": ["map"]})
    candidate = copy.deepcopy(store.root)
    candidate["drafts"]["pending"] = PrimitiveDraft(
        id="pending",
        validation={"ok": False, "errors": ["missing anchor"], "warnings": []},
    ).model_dump(mode="json")
    store.replace_validated_root(candidate)
    AdventureEngine().activate(scene, "demo")
    store.append_ledger(LedgerEntry(id="ledger-fixed", op="test.snapshot"))
    return scene


def _add_character(scene: Scene, name: str) -> None:
    """Attach an active character without agent-backed scene setup."""
    character = Character(name=name)
    actor = scene.Actor(character, None)
    actor.scene = scene
    scene.actors.append(actor)
    scene.character_data[name] = character


def test_canonical_kind_registries_drive_defaults_and_transport_coverage():
    assert tuple(PrimitiveDefinitions()) == DEFINITION_KINDS
    assert tuple(AnchorPayload().primitives) == PRIMITIVE_KINDS
    assert set(EDITABLE_DEFINITION_KINDS) < set(DEFINITION_KINDS)
    assert EDITABLE_PRIMITIVE_KINDS == PRIMITIVE_KINDS
    assert_game_primitives_transport_kind_coverage(DefinitionSnapshot)


def test_snapshot_editor_metadata_is_strict_and_registry_backed():
    metadata = build_game_primitives_snapshot(Scene()).editor_metadata

    assert metadata.definition_kinds == list(DEFINITION_KINDS)
    assert metadata.editable_definition_kinds == list(EDITABLE_DEFINITION_KINDS)
    assert metadata.primitive_kinds == list(PRIMITIVE_KINDS)
    assert metadata.editable_primitive_kinds == list(EDITABLE_PRIMITIVE_KINDS)
    assert metadata.render_policies == ["hidden", "prompt", "summary", "memory"]
    with pytest.raises(pydantic.ValidationError):
        type(metadata).model_validate(
            {**metadata.model_dump(mode="json"), "effect_kinds": ["unknown"]}
        )
    with pytest.raises(pydantic.ValidationError):
        type(metadata).model_validate(
            {**metadata.model_dump(mode="json"), "render_policies": ["unknown"]}
        )

    assert (
        StorySceneDefinition(
            id="memory", title="Memory", render_policy="memory"
        ).render_policy
        == "memory"
    )


def test_absent_snapshot_is_deterministic_and_does_not_initialize_state():
    scene = Scene()
    before = copy.deepcopy(scene.game_state.variables)

    first = build_game_primitives_snapshot(scene)
    second = build_game_primitives_snapshot(scene)

    assert first.initialized is False
    assert first.version is None
    assert first.revision == second.revision
    assert first.definitions == []
    assert first.anchors == []
    assert first.drafts == []
    assert first.current_adventure is None
    assert first.recent_ledger == []
    assert scene.game_state.variables == before
    assert GAME_PRIMITIVES_KEY not in scene.game_state.variables


def test_snapshot_is_sorted_detached_and_revision_tracks_canonical_state():
    scene = _populated_scene()
    before = copy.deepcopy(scene.game_state.variables[GAME_PRIMITIVES_KEY])

    snapshot = build_game_primitives_snapshot(scene)
    dumped = snapshot.model_dump(mode="json")

    assert [(item.kind, item.id) for item in snapshot.definitions] == [
        ("adventures", "demo"),
        ("meters", "health"),
    ]
    assert [anchor.ref for anchor in snapshot.anchors] == [
        "character:Ada",
        "character:Zed",
    ]
    assert snapshot.anchor_count == 2
    assert snapshot.primitive_count == 2
    assert snapshot.definition_counts["adventures"] == 1
    assert snapshot.definition_counts["meters"] == 1
    assert isinstance(snapshot.definitions[0].details, AdventureDefinition)
    assert snapshot.definitions[0].details.title == "Demo Adventure"
    assert isinstance(snapshot.definitions[1].details, MeterPayload)
    assert snapshot.anchors[0].primitive_counts["lists"] == 1
    assert snapshot.anchors[0].meta == {}
    assert snapshot.anchors[0].primitives["lists"]["clues"].model_dump() == {
        "value": ["map"]
    }
    assert snapshot.anchors[0].primitive_refs == ["character:Ada/lists/clues"]
    assert snapshot.anchors[1].primitive_refs == ["character:Zed/meters/health"]
    assert sum(snapshot.anchors[0].primitive_counts.values()) == 1
    assert snapshot.drafts[0].status == "draft"
    assert snapshot.drafts[0].anchor_count == 0
    assert snapshot.drafts[0].primitive_count == 0
    assert snapshot.drafts[0].validation.errors == ["missing anchor"]
    assert snapshot.current_adventure.id == "demo"
    assert snapshot.current_adventure.current_story_scene.id == "arrival"
    assert snapshot.current_adventure.state.visited == ["arrival"]
    assert snapshot.current_adventure.state.completed == []
    assert snapshot.recent_ledger[-1].id == "ledger-fixed"
    assert GamePrimitivesSnapshot.model_validate(dumped) == snapshot

    dumped["definitions"][0]["details"]["title"] = "Mutated transport"
    assert scene.game_state.variables[GAME_PRIMITIVES_KEY] == before
    assert build_game_primitives_snapshot(scene).revision == snapshot.revision

    PrimitiveStore.for_scene(scene).set_anchor_tags("character:Ada", ["changed"])
    assert build_game_primitives_snapshot(scene).revision != snapshot.revision


def test_snapshot_sorts_nested_catalogs_and_bounds_recent_ledger():
    scene = _populated_scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_anchor_tags("character:Ada", ["zeta", "alpha"])
    candidate = copy.deepcopy(store.root)
    candidate["drafts"]["alpha"] = PrimitiveDraft(id="alpha").model_dump(mode="json")
    store.replace_validated_root(candidate)
    for index in range(55):
        store.append_ledger(LedgerEntry(id=f"ledger-{index:02}", op="test.order"))

    snapshot = build_game_primitives_snapshot(scene)

    assert [draft.id for draft in snapshot.drafts] == ["alpha", "pending"]
    ada = next(anchor for anchor in snapshot.anchors if anchor.ref == "character:Ada")
    assert ada.tags == ["alpha", "zeta"]
    assert [item.id for item in snapshot.current_adventure.transitions] == [
        "a-transition",
        "z-transition",
    ]
    assert len(snapshot.recent_ledger) == 50
    assert snapshot.recent_ledger[0].id == "ledger-05"
    assert snapshot.recent_ledger[-1].id == "ledger-54"


def test_snapshot_projects_canonical_relationship_directions_and_dimensions():
    scene = Scene()
    _add_character(scene, "Alice")
    _add_character(scene, "Bob")
    graph = RelationshipGraph()
    graph.set(scene, "Alice", "Bob", "trust", 3, label="Trust")
    graph.set(scene, "Bob", "Alice", "trust", -2)

    snapshot = build_game_primitives_snapshot(scene)

    assert snapshot.active_characters == ["Alice", "Bob"]
    assert [item.anchor for item in snapshot.relationships] == [
        "relationship:Alice->Bob",
        "relationship:Bob->Alice",
    ]
    assert snapshot.relationships[0].source == "Alice"
    assert snapshot.relationships[0].target == "Bob"
    assert snapshot.relationships[0].dimensions[0].model_dump(mode="json") == {
        "id": "trust",
        "label": "Trust",
        "min": -5,
        "max": 5,
        "value": 3,
        "render_policy": "summary",
    }
    assert snapshot.relationships[0].summary == "Alice trusts Bob."
    assert snapshot.relationships[1].dimensions[0].value == -2


def test_snapshot_and_draft_validation_reject_dangling_relationship_characters():
    scene = Scene()
    _add_character(scene, "Alice")
    RelationshipGraph().set(scene, "Alice", "Missing", "trust", 1)

    with pytest.raises(
        ValueError, match="references missing character\\(s\\): Missing"
    ):
        build_game_primitives_snapshot(scene)

    service = WorldStateManagerPlugin(MagicMock(scene=scene))._primitive_authoring()
    revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
    service.create_draft(scene, "dangling", expected_revision=revision)
    draft = service.validate_draft(
        scene,
        "dangling",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )
    assert draft.validation.ok is False
    assert "references missing character(s): Missing" in draft.validation.errors[0]


def test_malformed_persisted_state_fails_instead_of_becoming_uninitialized():
    scene = Scene()
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = {"version": "1"}
    before = copy.deepcopy(scene.game_state.variables[GAME_PRIMITIVES_KEY])

    with pytest.raises(PrimitiveStoreError, match="Invalid Game Primitives root"):
        build_game_primitives_snapshot(scene)

    assert scene.game_state.variables[GAME_PRIMITIVES_KEY] == before


def test_transport_models_reject_coercion_and_unknown_request_fields():
    with pytest.raises(
        pydantic.ValidationError, match="Input should be a valid boolean"
    ):
        GamePrimitivesSnapshot.model_validate(
            {
                "initialized": "false",
                "version": None,
                "revision": "token",
                "definition_counts": {},
                "definitions": [],
                "anchor_count": 0,
                "primitive_count": 0,
                "anchors": [],
                "drafts": [],
                "current_adventure": None,
                "recent_ledger": [],
            }
        )

    with pytest.raises(pydantic.ValidationError):
        GamePrimitivesResponse.model_validate(
            {
                "type": "wrong",
                "action": "game_primitives",
                "data": build_game_primitives_snapshot(Scene()).model_dump(mode="json"),
                "extra": True,
            }
        )

    with pytest.raises(pydantic.ValidationError):
        AdventureStateSnapshot.model_validate(
            {
                "visited": [],
                "completed": [],
                "transition_log": [{"transition_id": "missing-fields"}],
            }
        )

    with pytest.raises(
        pydantic.ValidationError, match="Extra inputs are not permitted"
    ):
        GetGamePrimitivesPayload.model_validate(
            {
                "type": "world_state_manager",
                "action": "get_game_primitives",
                "initialize": True,
            }
        )


def test_request_adapter_rejects_nested_model_coercion():
    """Strict adapter validation rejects coercion inside nested primitive values."""
    with pytest.raises(pydantic.ValidationError, match="valid integer"):
        GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(
            {
                "type": "world_state_manager",
                "action": "upsert_game_primitive",
                "request_id": "nested-coercion",
                "draft_id": "edit",
                "expected_revision": "revision",
                "ref": "scene:main/meters/focus",
                "primitive": {
                    "kind": "meters",
                    "value": {"id": "focus", "min": 0, "max": "5", "value": 3},
                },
            },
            strict=True,
        )


@pytest.mark.asyncio
async def test_websocket_success_envelope_is_exact_and_json_serializable():
    scene = _populated_scene()
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "get_game_primitives",
            "request_id": "snapshot-1",
        }
    )

    assert len(queued) == 1
    assert set(queued[0]) == {"type", "action", "request_id", "data"}
    assert queued[0]["type"] == "world_state_manager"
    assert queued[0]["action"] == "game_primitives"
    assert queued[0]["request_id"] == "snapshot-1"
    assert queued[0]["data"] == build_game_primitives_snapshot(scene).model_dump(
        mode="json"
    )


@pytest.mark.asyncio
async def test_editor_metadata_websocket_is_scene_independent_and_matches_snapshots():
    """Metadata requests project the same registries without reading scene state."""
    queued = []
    handler = MagicMock(scene=None)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "get_game_primitive_editor_metadata",
            "request_id": "metadata-1",
        }
    )

    expected = get_game_primitive_editor_metadata().model_dump(mode="json")
    assert queued == [
        {
            "type": "world_state_manager",
            "action": "game_primitive_editor_metadata",
            "request_id": "metadata-1",
            "data": expected,
        }
    ]
    assert (
        build_game_primitives_snapshot(Scene()).editor_metadata.model_dump(mode="json")
        == expected
    )


@pytest.mark.asyncio
async def test_websocket_rejects_unknown_request_fields_with_exact_error_envelope():
    queued = []
    handler = MagicMock(scene=Scene())
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "get_game_primitives",
            "request_id": "bad-request",
            "initialize": True,
        }
    )

    assert len(queued) == 1
    assert queued[0]["type"] == "world_state_manager"
    assert queued[0]["action"] == "game_primitives_failed"
    assert set(queued[0]) == {
        "type",
        "action",
        "request_id",
        "request_action",
        "error",
    }
    assert queued[0]["request_id"] == "bad-request"
    assert set(queued[0]["error"]) == {"message"}
    assert queued[0]["error"]["message"].startswith(
        "1 validation error for tagged-union["
    )


@pytest.mark.asyncio
async def test_websocket_malformed_state_uses_explicit_error_envelope():
    scene = Scene()
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = []
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "get_game_primitives",
            "request_id": "malformed-state",
        }
    )

    assert len(queued) == 1
    assert queued[0]["type"] == "world_state_manager"
    assert queued[0]["action"] == "game_primitives_failed"
    assert set(queued[0]) == {
        "type",
        "action",
        "request_id",
        "request_action",
        "error",
    }
    assert set(queued[0]["error"]) == {"message"}
    assert queued[0]["error"]["message"].startswith("Invalid Game Primitives root:")
    assert scene.game_state.variables[GAME_PRIMITIVES_KEY] == []


@pytest.mark.asyncio
async def test_websocket_draft_upsert_and_atomic_commit_return_canonical_data():
    scene = Scene()
    scene.config.game.general.auto_save = False
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)
    initial_revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "create_game_primitive_draft",
            "request_id": "create-draft",
            "draft_id": "ui-edit",
            "expected_revision": initial_revision,
        }
    )

    assert queued[0]["action"] == "game_primitive_draft"
    assert queued[0]["data"]["created_by"] == "ui"
    assert queued[1] == {
        "type": "world_state_manager",
        "action": "operation_done",
        "request_id": "create-draft",
        "data": {},
    }
    assert [message["action"] for message in queued] == [
        "game_primitive_draft",
        "operation_done",
    ]
    assert scene.saved is False
    create_revision = queued[0]["revision"]

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "upsert_game_primitive",
            "request_id": "upsert-meter",
            "draft_id": "ui-edit",
            "expected_revision": create_revision,
            "ref": "scene:main/meters/focus",
            "primitive": {
                "kind": "meters",
                "value": {"id": "focus", "min": 0, "max": 5, "value": 3},
            },
        }
    )
    commit_revision = queued[0]["revision"]
    assert (
        queued[0]["data"]["anchors"]["scene:main"]["primitives"]["meters"]["focus"][
            "value"
        ]
        == 3
    )
    assert [message["action"] for message in queued] == [
        "game_primitive_draft",
        "operation_done",
    ]
    assert queued[1] == {
        "type": "world_state_manager",
        "action": "operation_done",
        "request_id": "upsert-meter",
        "data": {},
    }

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "commit_game_primitive_draft",
            "request_id": "commit-draft",
            "draft_id": "ui-edit",
            "expected_revision": commit_revision,
        }
    )

    assert queued[0]["action"] == "game_primitives"
    assert queued[0]["data"] == build_game_primitives_snapshot(scene).model_dump(
        mode="json"
    )
    assert [message["action"] for message in queued] == [
        "game_primitives",
        "operation_done",
    ]
    assert queued[1] == {
        "type": "world_state_manager",
        "action": "operation_done",
        "request_id": "commit-draft",
        "data": {},
    }
    assert (
        PrimitiveStore.for_scene(scene).get_primitive("scene:main/meters/focus")[
            "value"
        ]
        == 3
    )


@pytest.mark.asyncio
async def test_websocket_definition_anchor_primitive_and_validation_contracts():
    """Every draft edit returns the canonical draft, revision, and completion pair."""
    scene = Scene()
    scene.config.game.general.auto_save = False
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "meters", "focus", {"id": "focus", "min": 0, "max": 5, "value": 1}
    )
    store.set_anchor_tags("scene:main", ["old"])
    store.ensure_anchor("scene:main")["meta"] = {"chapter": 1}
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 1},
    )
    store.set_primitive("scene:main/lists/notes", {"value": ["keep"]})
    editing = WorldStateManagerPlugin(MagicMock(scene=scene))._primitive_authoring()
    editing.create_draft(
        scene,
        "contracts",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    async def mutate(action: str, **fields) -> dict:
        queued.clear()
        request_id = f"request-{action}"
        await plugin.handle(
            {
                "type": "world_state_manager",
                "action": action,
                "request_id": request_id,
                "draft_id": "contracts",
                "expected_revision": PrimitiveStore.read_snapshot_for_scene(
                    scene
                ).revision_token(),
                **fields,
            }
        )
        persisted = editing.get_draft(scene, "contracts")
        revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
        assert queued == [
            {
                "type": "world_state_manager",
                "action": "game_primitive_draft",
                "request_id": request_id,
                "data": persisted.model_dump(mode="json"),
                "revision": revision,
            },
            {
                "type": "world_state_manager",
                "action": "operation_done",
                "request_id": request_id,
                "data": {},
            },
        ]
        return queued[0]["data"]

    draft = await mutate(
        "upsert_game_primitive_definition",
        definition={
            "kind": "meters",
            "id": "focus",
            "value": {"id": "focus", "min": 0, "max": 10, "value": 4},
        },
    )
    assert draft["replacements"]["definitions"] == [{"kind": "meters", "id": "focus"}]

    draft = await mutate(
        "upsert_game_primitive_anchor",
        anchor="scene:main",
        value={"tags": ["new"], "meta": {"chapter": 2}},
    )
    assert draft["anchors"]["scene:main"]["tags"] == ["new"]
    assert draft["anchors"]["scene:main"]["meta"] == {"chapter": 2}

    draft = await mutate("delete_game_primitive", ref="scene:main/meters/focus")
    assert draft["deletions"]["primitives"] == ["scene:main/meters/focus"]

    draft = await mutate("validate_game_primitive_draft")
    assert draft["status"] == "validated"
    assert draft["validation"] == {"ok": True, "errors": [], "warnings": []}

    draft = await mutate("delete_game_primitive_definition", kind="meters", id="focus")
    assert draft["deletions"]["definitions"] == [{"kind": "meters", "id": "focus"}]

    draft = await mutate("delete_game_primitive_anchor", anchor="scene:main")
    assert draft["deletions"]["anchors"] == ["scene:main"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "fields", "message"),
    [
        (
            "delete_game_primitive_definition",
            {"kind": "meters", "id": "missing"},
            "Primitive definition not found: meters/missing",
        ),
        (
            "delete_game_primitive_anchor",
            {"anchor": "object:Missing"},
            "Primitive anchor not found: object:Missing",
        ),
    ],
)
async def test_websocket_missing_definition_and_anchor_fail_explicitly(
    action: str, fields: dict, message: str
):
    scene = Scene()
    scene.config.game.general.auto_save = False
    editing = WorldStateManagerPlugin(MagicMock(scene=scene))._primitive_authoring()
    editing.create_draft(
        scene,
        "missing",
        expected_revision=PrimitiveStore.read_snapshot_for_scene(
            scene
        ).revision_token(),
    )
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)
    request_id = f"missing-{action}"

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": request_id,
            "draft_id": "missing",
            "expected_revision": PrimitiveStore.read_snapshot_for_scene(
                scene
            ).revision_token(),
            **fields,
        }
    )

    assert queued == [
        {
            "type": "world_state_manager",
            "action": "game_primitives_failed",
            "request_id": request_id,
            "request_action": action,
            "error": {"message": message},
        }
    ]
    assert PrimitiveStore.for_scene(scene).root == before


@pytest.mark.asyncio
async def test_websocket_draft_list_get_delete_and_missing_errors_are_explicit():
    scene = Scene()
    scene.config.game.general.auto_save = False
    service_store = PrimitiveStore.for_scene(scene)
    service_store.root["drafts"]["b"] = PrimitiveDraft(id="b").model_dump(mode="json")
    service_store.root["drafts"]["a"] = PrimitiveDraft(id="a").model_dump(mode="json")
    service_store.ensure_shape()
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "list_game_primitive_drafts",
            "request_id": "list-drafts",
        }
    )
    assert queued[0]["action"] == "game_primitive_drafts"
    assert [draft["id"] for draft in queued[0]["data"]] == ["a", "b"]

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "get_game_primitive_draft",
            "request_id": "get-draft",
            "draft_id": "a",
        }
    )
    assert queued[0]["data"]["id"] == "a"
    delete_revision = queued[0]["revision"]

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "delete_game_primitive_draft",
            "request_id": "delete-draft",
            "draft_id": "a",
            "expected_revision": delete_revision,
        }
    )
    assert [draft["id"] for draft in queued[0]["data"]] == ["b"]
    assert queued[1]["action"] == "operation_done"

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "get_game_primitive_draft",
            "request_id": "missing-draft",
            "draft_id": "missing",
        }
    )
    assert queued == [
        {
            "type": "world_state_manager",
            "action": "game_primitives_failed",
            "request_id": "missing-draft",
            "request_action": "get_game_primitive_draft",
            "error": {"message": "Primitive draft not found: missing"},
        }
    ]


@pytest.mark.asyncio
async def test_websocket_stale_commit_and_invalid_typed_upsert_preserve_state():
    scene = Scene()
    scene.config.game.general.auto_save = False
    store = PrimitiveStore.for_scene(scene)
    store.root["drafts"]["edit"] = PrimitiveDraft(id="edit").model_dump(mode="json")
    store.ensure_shape()
    stale_revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
    store.set_anchor_tags("scene:main", ["newer"])
    before = copy.deepcopy(store.root)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "commit_game_primitive_draft",
            "request_id": "stale-commit",
            "draft_id": "edit",
            "expected_revision": stale_revision,
        }
    )
    assert "Stale Game Primitives revision" in queued[0]["error"]["message"]
    assert store.root == before

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "upsert_game_primitive",
            "request_id": "invalid-upsert",
            "draft_id": "edit",
            "expected_revision": PrimitiveStore.read_snapshot_for_scene(
                scene
            ).revision_token(),
            "ref": "scene:main/meters/focus",
            "primitive": {
                "kind": "clocks",
                "value": {"id": "focus", "max": 4},
            },
            "unexpected": True,
        }
    )
    assert queued[0]["action"] == "game_primitives_failed"
    assert "validation error" in queued[0]["error"]["message"]
    assert store.root == before


@pytest.mark.asyncio
async def test_relationship_adjustment_uses_effect_and_preserves_reverse_edge():
    scene = Scene()
    scene.config.game.general.auto_save = False
    _add_character(scene, "Alice")
    _add_character(scene, "Bob")
    graph = RelationshipGraph()
    graph.set(scene, "Alice", "Bob", "trust", 1)
    graph.set(scene, "Bob", "Alice", "trust", -1)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "adjust_game_primitive",
            "request_id": "adjust-relationship",
            "expected_revision": PrimitiveStore.read_snapshot_for_scene(
                scene
            ).revision_token(),
            "ref": "relationship:Alice->Bob/meters/trust",
            "delta": 2,
        }
    )

    assert [message["action"] for message in queued] == [
        "game_primitives",
        "operation_done",
    ]
    assert graph.get(scene, "Alice", "Bob", "trust") == 3
    assert graph.get(scene, "Bob", "Alice", "trust") == -1
    assert PrimitiveStore.for_scene(scene).recent_ledger(1)[0]["op"] == "effect.inc"


@pytest.mark.asyncio
async def test_websocket_meter_clock_adjustments_are_effect_driven_and_atomic():
    scene = Scene()
    scene.config.game.general.auto_save = False
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 2},
    )
    store.set_primitive(
        "scene:main/clocks/alarm", {"id": "alarm", "max": 4, "value": 1}
    )
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "adjust_game_primitive",
            "request_id": "adjust-meter",
            "expected_revision": plugin._primitive_revision(),
            "ref": "scene:main/meters/focus",
            "delta": 2,
        }
    )

    assert store.get_primitive("scene:main/meters/focus")["value"] == 4
    assert store.root["ledger"][-1]["op"] == "effect.inc"
    assert queued[0]["action"] == "game_primitives"
    assert queued[0]["request_id"] == "adjust-meter"
    assert queued[1]["request_id"] == "adjust-meter"

    before = copy.deepcopy(store.root)
    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "adjust_game_primitive",
            "request_id": "overflow-clock",
            "expected_revision": plugin._primitive_revision(),
            "ref": "scene:main/clocks/alarm",
            "delta": 4,
        }
    )
    assert queued[0]["action"] == "game_primitives_failed"
    assert store.root == before


@pytest.mark.asyncio
async def test_websocket_adjustment_rejects_stale_and_non_runtime_targets():
    scene = Scene()
    scene.config.game.general.auto_save = False
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 2},
    )
    before = copy.deepcopy(store.root)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "adjust_game_primitive",
            "request_id": "stale-adjust",
            "expected_revision": "stale",
            "ref": "scene:main/meters/focus",
            "delta": -1,
        }
    )
    assert "Stale Game Primitives revision" in queued[0]["error"]["message"]
    assert store.root == before

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "adjust_game_primitive",
            "request_id": "bad-kind",
            "expected_revision": plugin._primitive_revision(),
            "ref": "scene:main/decks/omens",
            "delta": 1,
        }
    )
    assert "requires a meter or clock ref" in queued[0]["error"]["message"]
    assert store.root == before


def test_typed_upsert_contracts_enforce_outer_and_value_identity():
    """Transport upserts reject mismatched definition and primitive ids."""
    common = {
        "type": "world_state_manager",
        "request_id": "identity",
        "draft_id": "edit",
        "expected_revision": "revision",
    }
    with pytest.raises(pydantic.ValidationError, match="must match value id"):
        UpsertGamePrimitiveDefinitionPayload.model_validate(
            {
                **common,
                "action": "upsert_game_primitive_definition",
                "definition": {
                    "kind": "meters",
                    "id": "focus",
                    "value": {
                        "id": "attention",
                        "min": 0,
                        "max": 5,
                        "value": 2,
                    },
                },
            }
        )

    with pytest.raises(pydantic.ValidationError, match="does not match value id"):
        UpsertGamePrimitivePayload.model_validate(
            {
                **common,
                "action": "upsert_game_primitive",
                "ref": "scene:main/attributes/focus",
                "primitive": {
                    "kind": "attributes",
                    "value": {
                        "id": "attention",
                        "source": "literal",
                        "value": 1,
                    },
                },
            }
        )


@pytest.mark.asyncio
async def test_unknown_game_primitive_action_returns_correlated_failure():
    queued = []
    handler = MagicMock(scene=Scene())
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "unknown_game_primitive_action",
            "request_id": "unknown-action",
        }
    )

    assert queued[0]["action"] == "game_primitives_failed"
    assert queued[0]["request_id"] == "unknown-action"
    assert queued[0]["request_action"] == "unknown_game_primitive_action"


@pytest.mark.asyncio
async def test_malformed_game_primitive_request_never_reaches_generic_dispatch():
    """A recognized action missing correlation receives one modeled failure."""
    queued = []
    handler = MagicMock(scene=Scene())
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {"type": "world_state_manager", "action": "get_game_primitives"}
    )

    assert len(queued) == 1
    assert queued[0]["action"] == "game_primitives_failed"
    assert queued[0]["request_id"] == "unmatched-request"
    assert queued[0]["request_action"] == "get_game_primitives"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "request_id", "request_fields"),
    [
        ("create_game_primitive_draft", "create-failed", {"draft_id": "edit"}),
        (
            "upsert_game_primitive",
            "upsert-failed",
            {
                "draft_id": "edit",
                "ref": "scene:main/meters/focus",
                "primitive": {
                    "kind": "meters",
                    "value": {"id": "focus", "min": 0, "max": 5, "value": 3},
                },
            },
        ),
        ("commit_game_primitive_draft", "commit-failed", {"draft_id": "edit"}),
    ],
)
async def test_mutation_autosave_failure_has_no_phantom_success(
    action: str, request_id: str, request_fields: dict
):
    scene = Scene()
    scene.config.game.general.auto_save = True
    if action != "create_game_primitive_draft":
        store = PrimitiveStore.for_scene(scene)
        store.root["drafts"]["edit"] = PrimitiveDraft(id="edit").model_dump(mode="json")
        store.ensure_shape()
    root_existed = GAME_PRIMITIVES_KEY in scene.game_state.variables
    before_root = copy.deepcopy(scene.game_state.variables.get(GAME_PRIMITIVES_KEY))
    expected_revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
    scene.save = AsyncMock(side_effect=RuntimeError("autosave failed"))
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": request_id,
            "expected_revision": expected_revision,
            **request_fields,
        }
    )

    assert queued == [
        {
            "type": "world_state_manager",
            "action": "game_primitives_failed",
            "request_id": request_id,
            "request_action": action,
            "error": {"message": "autosave failed"},
        }
    ]
    scene.save.assert_awaited_once_with(auto=True)
    assert (GAME_PRIMITIVES_KEY in scene.game_state.variables) is root_existed
    assert scene.game_state.variables.get(GAME_PRIMITIVES_KEY) == before_root
    assert PrimitiveStore.read_snapshot_for_scene(scene).revision_token() == (
        expected_revision
    )


@pytest.mark.asyncio
async def test_mutation_surfaces_finalization_and_rollback_failures():
    """A rollback error is included in the sole correlated failure response."""
    scene = Scene()
    scene.config.game.general.auto_save = True
    scene.save = AsyncMock(side_effect=RuntimeError("autosave failed"))
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)
    plugin._restore_primitive_root = MagicMock(
        side_effect=RuntimeError("restore failed")
    )

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": "create_game_primitive_draft",
            "request_id": "rollback-failed",
            "draft_id": "edit",
            "expected_revision": PrimitiveStore.read_snapshot_for_scene(
                scene
            ).revision_token(),
        }
    )

    assert queued == [
        {
            "type": "world_state_manager",
            "action": "game_primitives_failed",
            "request_id": "rollback-failed",
            "request_action": "create_game_primitive_draft",
            "error": {
                "message": "autosave failed; primitive root rollback failed: restore failed"
            },
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "target_field", "target", "deleted_collection"),
    [
        (
            "preview_delete_game_primitive_anchor",
            "anchor",
            "scene:main",
            "anchors",
        ),
        (
            "preview_delete_game_primitive",
            "ref",
            "scene:main/meters/focus",
            "primitives",
        ),
    ],
)
async def test_deletion_previews_validate_detached_candidates_without_mutation(
    action: str,
    target_field: str,
    target: str,
    deleted_collection: str,
    monkeypatch,
):
    """Anchor and primitive previews return tombstones but persist nothing."""
    scene = Scene()
    monkeypatch.setattr(scene.config.game.general, "auto_save", False)
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/focus",
        {"id": "focus", "min": 0, "max": 5, "value": 2},
    )
    before = copy.deepcopy(store.root)
    revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": f"preview-{deleted_collection}",
            "expected_revision": revision,
            target_field: target,
        }
    )

    assert len(queued) == 1
    response = queued[0]
    assert response["action"] == "game_primitive_deletion_preview"
    assert response["revision"] == revision
    assert response["validation"] == {"ok": True, "errors": [], "warnings": []}
    assert response["draft"]["deletions"][deleted_collection] == [target]
    assert response["candidate"]["before"]["anchors"] == 1
    assert response["candidate"]["before"]["primitives"] == 1
    expected_after = 0 if deleted_collection == "anchors" else 1
    assert response["candidate"]["after"]["anchors"] == expected_after
    assert response["candidate"]["after"]["primitives"] == 0
    assert store.root == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "fields", "message"),
    [
        (
            "preview_delete_game_primitive_anchor",
            {"anchor": "scene:missing"},
            "Primitive anchor not found: scene:missing",
        ),
        (
            "preview_delete_game_primitive",
            {"ref": "scene:main/meters/missing"},
            "Primitive not found: scene:main/meters/missing",
        ),
    ],
)
async def test_deletion_previews_fail_explicitly_for_missing_and_stale_targets(
    action: str, fields: dict, message: str
):
    scene = Scene()
    before = copy.deepcopy(scene.game_state.variables)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)
    revision = plugin._primitive_revision()

    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": "missing-preview",
            "expected_revision": revision,
            **fields,
        }
    )
    assert queued[0]["action"] == "game_primitives_failed"
    assert queued[0]["error"]["message"] == message
    assert scene.game_state.variables == before

    queued.clear()
    await plugin.handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": "stale-preview",
            "expected_revision": "stale",
            **fields,
        }
    )
    assert "Stale Game Primitives revision" in queued[0]["error"]["message"]
    assert scene.game_state.variables == before


def _relationship_request(
    plugin: WorldStateManagerPlugin, request_id: str, change: dict
) -> dict:
    return {
        "type": "world_state_manager",
        "action": "author_game_primitive_relationship",
        "request_id": request_id,
        "expected_revision": plugin._primitive_revision(),
        "source": "Alice",
        "target": "Bob",
        "change": change,
    }


@pytest.mark.asyncio
async def test_relationship_authoring_create_edit_and_deletes_are_atomic_and_directional(
    monkeypatch,
):
    """One action owns the complete relationship lifecycle and preserves siblings."""
    scene = Scene()
    monkeypatch.setattr(scene.config.game.general, "auto_save", False)
    _add_character(scene, "Alice")
    _add_character(scene, "Bob")
    graph = RelationshipGraph()
    graph.set(scene, "Bob", "Alice", "trust", -2)
    graph.set(scene, "Alice", "Bob", "respect", 1)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    async def author(request_id: str, change: dict) -> dict:
        drafts_before = set(PrimitiveStore.for_scene(scene).root["drafts"])
        queued.clear()
        await plugin.handle(_relationship_request(plugin, request_id, change))
        assert [item["action"] for item in queued] == [
            "game_primitives",
            "operation_done",
        ]
        assert queued[0]["request_id"] == request_id
        assert queued[0]["data"] == build_game_primitives_snapshot(scene).model_dump(
            mode="json"
        )
        drafts = PrimitiveStore.for_scene(scene).root["drafts"]
        new_draft_ids = set(drafts) - drafts_before
        assert len(new_draft_ids) == 1
        committed = PrimitiveDraft.model_validate(drafts[new_draft_ids.pop()])
        assert committed.status == "committed"
        assert committed.created_by == "ui"
        assert committed.validation.ok
        assert committed.validation.errors == []
        assert not any(committed.definitions.values())
        assert committed.anchors == {}
        assert committed.replacements.model_dump(mode="json") == {
            "definitions": [],
            "anchors": [],
            "primitives": [],
        }
        assert committed.deletions.model_dump(mode="json") == {
            "definitions": [],
            "anchors": [],
            "primitives": [],
        }
        return queued[0]["data"]

    await author(
        "create-dimension",
        {
            "operation": "upsert_dimension",
            "dimension": {
                "id": "trust",
                "label": "Trust",
                "min": -5,
                "max": 5,
                "value": 2,
                "render_policy": "summary",
            },
        },
    )
    assert graph.get(scene, "Alice", "Bob", "trust") == 2
    assert graph.get(scene, "Alice", "Bob", "respect") == 1
    assert graph.get(scene, "Bob", "Alice", "trust") == -2

    await author(
        "edit-dimension",
        {
            "operation": "upsert_dimension",
            "dimension": {
                "id": "trust",
                "label": "Confidence",
                "min": -10,
                "max": 10,
                "value": 7,
                "render_policy": "hidden",
            },
        },
    )
    assert graph.get(scene, "Alice", "Bob", "trust") == 7
    assert graph.get(scene, "Alice", "Bob", "respect") == 1

    await author(
        "delete-dimension",
        {"operation": "delete_dimension", "dimension_id": "trust"},
    )
    with pytest.raises(PrimitiveError, match="dimension not found"):
        graph.get(scene, "Alice", "Bob", "trust")
    assert graph.get(scene, "Alice", "Bob", "respect") == 1
    assert graph.get(scene, "Bob", "Alice", "trust") == -2

    await author("delete-edge", {"operation": "delete_edge"})
    assert graph.edge(scene, "Alice", "Bob") is None
    assert graph.get(scene, "Bob", "Alice", "trust") == -2


@pytest.mark.asyncio
async def test_relationship_authoring_invalid_stale_and_finalization_failures_rollback(
    monkeypatch,
):
    """Every pre-commit or finalization failure preserves the exact prior root."""
    scene = Scene()
    monkeypatch.setattr(scene.config.game.general, "auto_save", False)
    _add_character(scene, "Alice")
    _add_character(scene, "Bob")
    graph = RelationshipGraph()
    graph.set(scene, "Alice", "Bob", "trust", 1)
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    plugin = WorldStateManagerPlugin(handler)

    invalid = _relationship_request(
        plugin,
        "invalid-relationship",
        {
            "operation": "upsert_dimension",
            "dimension": {"id": "trust", "min": -5, "max": 5, "value": 8},
        },
    )
    await plugin.handle(invalid)
    assert queued[0]["action"] == "game_primitives_failed"
    assert PrimitiveStore.for_scene(scene).root == before

    queued.clear()
    stale = _relationship_request(
        plugin,
        "stale-relationship",
        {"operation": "delete_dimension", "dimension_id": "trust"},
    )
    stale["expected_revision"] = "stale"
    await plugin.handle(stale)
    assert "Stale Game Primitives revision" in queued[0]["error"]["message"]
    assert PrimitiveStore.for_scene(scene).root == before

    queued.clear()
    scene.config.game.general.auto_save = True
    scene.save = AsyncMock(side_effect=RuntimeError("autosave failed"))
    await plugin.handle(
        _relationship_request(
            plugin,
            "relationship-autosave",
            {
                "operation": "upsert_dimension",
                "dimension": {"id": "trust", "min": -5, "max": 5, "value": 4},
            },
        )
    )
    assert queued[0]["action"] == "game_primitives_failed"
    assert queued[0]["error"] == {"message": "autosave failed"}
    assert PrimitiveStore.for_scene(scene).root == before


def test_relationship_authoring_contract_is_strict_and_routed():
    """The action union accepts only operation-specific canonical payloads."""
    payload = {
        "type": "world_state_manager",
        "action": "author_game_primitive_relationship",
        "request_id": "contract",
        "expected_revision": "revision",
        "source": "Alice",
        "target": "Bob",
        "change": {"operation": "delete_edge"},
    }
    assert isinstance(
        GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(payload, strict=True),
        AuthorGamePrimitiveRelationshipPayload,
    )
    with pytest.raises(
        pydantic.ValidationError, match="Extra inputs are not permitted"
    ):
        GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(
            {**payload, "change": {"operation": "delete_edge", "dimension_id": "x"}},
            strict=True,
        )


@pytest.mark.asyncio
async def test_post_commit_emission_failure_attempts_modeled_indeterminate_response(
    monkeypatch,
):
    """A committed mutation never becomes an ordinary failure when emission fails."""
    scene = Scene()
    monkeypatch.setattr(scene.config.game.general, "auto_save", False)
    emitted = []
    attempts = 0

    def emit(message: dict) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("snapshot transport failed")
        emitted.append(message)

    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = emit
    plugin = WorldStateManagerPlugin(handler)
    request = {
        "type": "world_state_manager",
        "action": "create_game_primitive_draft",
        "request_id": "indeterminate-commit",
        "draft_id": "committed-draft",
        "expected_revision": plugin._primitive_revision(),
    }

    await plugin.handle(request)

    assert "committed-draft" in PrimitiveStore.for_scene(scene).root["drafts"]
    assert len(emitted) == 1
    response = GamePrimitivesIndeterminateResponse.model_validate(emitted[0])
    assert response.request_id == "indeterminate-commit"
    assert response.request_action == "create_game_primitive_draft"
    assert response.outcome == "committed_but_unconfirmed"
    assert response.error.message == "snapshot transport failed"
    assert all(item["action"] != "game_primitives_failed" for item in emitted)
