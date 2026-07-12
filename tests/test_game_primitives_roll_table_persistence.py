"""Persistence-boundary tests for anchored roll-table instances."""

import copy

import pytest

from talemate.game.primitives.authoring import PrimitiveDraftStore
from talemate.game.primitives.constants import GAME_PRIMITIVES_KEY
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.schema import (
    AnchorPayload,
    PrimitiveRootPayload,
    default_root,
)
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


INLINE_TABLE = {
    "id": "weather",
    "name": "Weather",
    "mode": "weighted",
    "rows": [{"id": "sun", "label": "Sunny", "weight": 1}],
}

INVALID_INSTANCE_PAYLOADS = [
    INLINE_TABLE,
    {"definition": INLINE_TABLE},
    {"value": INLINE_TABLE},
    {"definition_id": "weather"},
    {"table": "weather"},
    {"definition": "weather", "extra": True},
]


def _anchor_with_roll_table(payload: dict) -> dict:
    return {"primitives": {"roll_tables": {"local-weather": copy.deepcopy(payload)}}}


@pytest.mark.parametrize("setter_name", ["set_primitive", "set_runtime_primitive"])
@pytest.mark.parametrize("payload", INVALID_INSTANCE_PAYLOADS)
def test_store_setters_reject_noncanonical_roll_table_instances(setter_name, payload):
    """Both primitive write APIs reject non-id-only payloads before mutation."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    before = copy.deepcopy(store.root)

    with pytest.raises(PrimitiveStoreError):
        getattr(store, setter_name)(
            "scene:main/roll_tables/local-weather", copy.deepcopy(payload)
        )

    assert store.root == before


def test_store_setters_persist_canonical_roll_table_instance():
    """Anchored roll-table writes normalize through the canonical payload model."""
    store = PrimitiveStore.for_scene(Scene())

    store.set_primitive(
        "scene:main/roll_tables/local-weather", {"definition": " weather "}
    )

    assert store.get_primitive("scene:main/roll_tables/local-weather") == {
        "definition": "weather"
    }


@pytest.mark.parametrize("payload", INVALID_INSTANCE_PAYLOADS)
def test_anchor_root_and_draft_schemas_reject_noncanonical_instances(payload):
    """Direct anchor, committed-root, and draft schemas share the same contract."""
    anchor = _anchor_with_roll_table(payload)
    root = default_root()
    root["anchors"] = {"scene:main": copy.deepcopy(anchor)}

    with pytest.raises(ValueError):
        AnchorPayload.model_validate(anchor)
    with pytest.raises(ValueError):
        PrimitiveRootPayload.model_validate(root)
    with pytest.raises(ValueError):
        PrimitiveDraft.model_validate(
            {"id": "draft", "anchors": {"scene:main": copy.deepcopy(anchor)}}
        )


@pytest.mark.parametrize("in_draft", [False, True])
@pytest.mark.parametrize("payload", INVALID_INSTANCE_PAYLOADS)
def test_root_and_draft_loading_reject_noncanonical_instances(in_draft, payload):
    """Persisted committed and draft payloads fail as soon as storage is loaded."""
    scene = Scene()
    root = default_root()
    anchor = _anchor_with_roll_table(payload)
    if in_draft:
        root["drafts"] = {"draft": {"id": "draft", "anchors": {"scene:main": anchor}}}
    else:
        root["anchors"] = {"scene:main": anchor}
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = root

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore.for_scene(scene)
    with pytest.raises(PrimitiveStoreError):
        PrimitiveDraftStore().get(scene, "draft")
