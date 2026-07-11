"""Unit tests for Game Primitives refs, store initialization, and ledger."""

from __future__ import annotations

import copy
import json
import math

import pytest

from talemate.game.primitives import (
    AnchorRef,
    InvalidAnchorRef,
    InvalidPrimitiveRef,
    LedgerEntry,
    PrimitiveRef,
    PrimitiveStore,
    PrimitiveStoreError,
    character_anchor,
    object_anchor,
    relationship_anchor,
    scene_anchor,
)
from talemate.game.primitives.schema import (
    CURRENT_VERSION,
    GAME_PRIMITIVES_KEY,
    default_root,
)
from talemate.tale_mate import Scene


@pytest.mark.parametrize(
    "raw",
    [
        "scene:main",
        "character:Model",
        "object:HasselbladCamera",
        "relationship:Model->Photographer",
        "location:studio",
        "story_scene:warmup",
        "project:studio-session",
    ],
)
def test_anchor_ref_parse_roundtrips(raw):
    """Supported anchor strings parse and return stable keys."""
    ref = AnchorRef.parse(raw)

    assert ref.key() == raw
    assert str(ref) == raw


def test_anchor_helpers_return_canonical_refs():
    """Helper constructors produce the documented anchor reference forms."""
    assert scene_anchor().key() == "scene:main"
    assert character_anchor("Model").key() == "character:Model"
    assert object_anchor("Camera").key() == "object:Camera"
    assert relationship_anchor("Model", "Photographer").key() == (
        "relationship:Model->Photographer"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "character",
        "character:",
        "unknown:Model",
        "character:Model/poses",
        "character:Model:extra",
        "relationship:Model",
        "relationship:Model->",
        "relationship:->Photographer",
        "relationship:Model->Photographer->Assistant",
    ],
)
def test_anchor_ref_parse_rejects_invalid_values(raw):
    """Invalid anchor strings raise the canonical anchor exception."""
    with pytest.raises(InvalidAnchorRef):
        AnchorRef.parse(raw)


def test_anchor_ref_model_rejects_id_containing_separator():
    """Anchor ids cannot contain the ':' separator used by persisted keys."""
    with pytest.raises(ValueError):
        character_anchor("A:B")

    store = PrimitiveStore.for_scene(Scene())
    bad_anchor = AnchorRef.model_construct(kind="character", id="A:B")
    with pytest.raises(ValueError):
        store.ensure_anchor(bad_anchor)

    assert "character:A:B" not in store.root["anchors"]


@pytest.mark.parametrize(
    "raw",
    [
        "character:Model/meters/confidence",
        "relationship:Model->Photographer/meters/trust",
        "object:HasselbladCamera/meters/film_remaining",
        "scene:main/clocks/studio_time",
        "project:studio-session/roll_tables/model_reaction",
    ],
)
def test_primitive_ref_parse_roundtrips(raw):
    """Primitive refs parse into anchor, kind, and id segments."""
    ref = PrimitiveRef.parse(raw)

    assert ref.key() == raw
    assert str(ref) == raw


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "character:Model/meters",
        "character:Model/meters/confidence/extra",
        "character:Model//confidence",
        "character:Model/meters/",
        "character/meters/confidence",
        "character:Model/ /confidence",
    ],
)
def test_primitive_ref_parse_rejects_invalid_values(raw):
    """Invalid primitive strings raise the canonical primitive exception."""
    with pytest.raises(InvalidPrimitiveRef):
        PrimitiveRef.parse(raw)


def test_store_for_scene_initializes_missing_root_shape():
    """A scene without primitive state gets the MVP root shape on demand."""
    scene = Scene()
    assert GAME_PRIMITIVES_KEY not in scene.game_state.variables

    store = PrimitiveStore.for_scene(scene)

    assert scene.game_state.variables[GAME_PRIMITIVES_KEY] is store.root
    assert store.root["version"] == CURRENT_VERSION
    assert store.root["definitions"]["roll_tables"] == {}
    assert store.root["definitions"]["adventures"] == {}
    assert store.root["anchors"] == {}
    assert store.root["runtime"] == {}
    assert store.root["ledger"] == []


def test_read_snapshot_is_validated_and_detached_from_mutable_state():
    """Snapshot reads cannot mutate or observe later changes to scene state."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/danger",
        {"id": "danger", "value": 2, "min": 0, "max": 5},
    )
    snapshot = PrimitiveStore.read_snapshot_for_scene(scene)

    returned = snapshot.get_primitive("scene:main/meters/danger")
    returned["value"] = 4
    store.set_runtime_primitive(
        "scene:main/meters/danger",
        {"id": "danger", "value": 5, "min": 0, "max": 5},
    )

    assert snapshot.get_primitive("scene:main/meters/danger")["value"] == 2
    assert store.get_primitive("scene:main/meters/danger")["value"] == 5


def test_store_for_scene_rejects_partial_existing_root_shape():
    """An existing root must explicitly contain every current-version field."""
    scene = Scene()
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = {
        "definitions": {"relationship_models": {"poses": {"cards": []}}}
    }

    with pytest.raises(PrimitiveStoreError, match="Field required"):
        PrimitiveStore.for_scene(scene)


def test_store_for_scene_rejects_invalid_existing_root():
    """Corrupt primitive roots fail loudly instead of being overwritten."""
    scene = Scene()
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = "not-a-dict"

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore.for_scene(scene)


@pytest.mark.parametrize(
    "root",
    [
        None,
        {"version": None},
        {"version": "1"},
        {"version": True},
        {"version": CURRENT_VERSION + 1},
        {"version": CURRENT_VERSION - 1},
        {"definitions": []},
        {"definitions": {"meters": {}, " meters ": {}}},
        {"definitions": {"meters": {"x": 1, " x ": 2}}},
        {"anchors": []},
        {"runtime": []},
        {"ledger": {}},
        {"definitions": {"decks": []}},
        {"anchors": {"scene:main": []}},
        {"anchors": {"scene:main": {"tags": {}}}},
        {"anchors": {"scene:main": {"primitives": []}}},
        {"anchors": {"scene:main": {"meta": []}}},
        {"anchors": {"scene:main": {"primitives": {"meters": []}}}},
        {"anchors": {"not-an-anchor": {}}},
        {"anchors": {"scene:main": {"primitives": {"meters": {"bad/id": {}}}}}},
        {"anchors": {"character:Alice": {}, "character: Alice": {}}},
        {
            "anchors": {
                "scene:main": {
                    "primitives": {"meters": {"tension": {}, " tension ": {}}}
                }
            }
        },
        {"anchors": {"scene:main": {"primitives": {"meters": {}, " meters ": {}}}}},
    ],
)
def test_store_for_scene_rejects_corrupt_persisted_shapes(root):
    """Persisted primitive roots with incompatible shapes fail loudly."""
    scene = Scene()
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = root

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore.for_scene(scene)


def test_store_for_scene_does_not_mutate_corrupt_root_on_failure():
    """A failed root validation does not inject defaults into corrupt state."""
    scene = Scene()
    root = {"definitions": []}
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = root

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore.for_scene(scene)

    assert root == {"definitions": []}


@pytest.mark.parametrize("limit", [0, True, "1", None, 1.0])
def test_store_for_scene_rejects_invalid_ledger_limit_before_mutation(limit):
    """Invalid ledger retention limits fail before creating primitive state."""
    scene = Scene()

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore.for_scene(scene, max_ledger_length=limit)

    assert GAME_PRIMITIVES_KEY not in scene.game_state.variables

    root = {}
    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore(root, max_ledger_length=limit)
    assert root == {}


def test_direct_store_constructor_validates_and_shapes_root():
    """Direct store construction validates and initializes the root immediately."""
    root = default_root()
    store = PrimitiveStore(root, max_ledger_length=2)

    assert store.root is root
    assert root["ledger"] == []
    assert root["definitions"]["meters"] == {}

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore([], max_ledger_length=2)


def test_store_anchor_and_primitive_crud():
    """Primitive payloads are stored under anchor/kind/id paths."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)

    assert store.get_anchor("character:Model") is None
    anchor_payload = store.ensure_anchor("character:Model")
    assert anchor_payload["tags"] == []
    assert anchor_payload["primitives"]["meters"] == {}
    assert anchor_payload["meta"] == {}
    anchor_payload["tags"].append("mutated-copy")
    assert store.get_anchor("character:Model")["tags"] == []
    anchor_copy = store.get_anchor("character:Model")
    anchor_copy["tags"].append("mutated-get-copy")
    assert store.get_anchor("character:Model")["tags"] == []

    value = {"id": "confidence", "value": 2, "min": 0, "max": 5}
    store.set_primitive("character:Model/meters/confidence", value)
    value["value"] = 99

    assert store.get_primitive("character:Model/meters/confidence") == {
        "value": 2,
        "id": "confidence",
        "label": None,
        "min": 0,
        "max": 5,
        "render_policy": "hidden",
    }
    returned = store.get_primitive("character:Model/meters/confidence")
    returned["value"] = 99
    assert store.get_primitive("character:Model/meters/confidence")["value"] == 2
    assert store.get_primitive(
        "character:Model/meters/missing", default="fallback"
    ) == ("fallback")

    assert store.delete_primitive("character:Model/meters/confidence") is True
    assert store.delete_primitive("character:Model/meters/confidence") is False
    assert store.get_primitive("character:Model/meters/confidence") is None

    set_entry, delete_entry = store.recent_ledger(2)
    assert set_entry["op"] == "primitive.set"
    assert set_entry["ref"] == "character:Model/meters/confidence"
    canonical = store.root["ledger"][0]["input"]["value"]
    assert set_entry["input"] == {"value": canonical}
    assert set_entry["output"] == {
        "previous": None,
        "current": canonical,
    }
    assert delete_entry["op"] == "primitive.delete"
    assert delete_entry["ref"] == "character:Model/meters/confidence"
    assert delete_entry["output"] == {"previous": canonical}


def test_store_copy_on_read_deep_copies_nested_payloads():
    """Primitive and ledger reads deep-copy nested JSON payloads."""
    store = PrimitiveStore.for_scene(Scene())
    ref = "scene:main/values/tension"
    original = {"value": {"history": [{"n": 1}]}}

    store.set_primitive(ref, original)
    original["value"]["history"][0]["n"] = 99
    assert store.get_primitive(ref)["value"]["history"][0]["n"] == 1

    returned = store.get_primitive(ref)
    returned["value"]["history"][0]["n"] = 42
    assert store.get_primitive(ref)["value"]["history"][0]["n"] == 1

    store.append_ledger({"op": "nested", "output": {"items": [{"n": 1}]}})
    recent = store.recent_ledger(1)
    recent[0]["output"]["items"][0]["n"] = 99
    assert store.recent_ledger(1)[0]["output"]["items"][0]["n"] == 1


def test_store_revalidates_mutated_ref_objects_before_use():
    """Mutable ref model inputs are normalized again before storage use."""
    store = PrimitiveStore.for_scene(Scene())
    ref = PrimitiveRef.parse("scene:main/meters/tension")
    ref.kind = " meters "
    ref.id = " tension "

    store.set_primitive(ref, {"id": "tension", "value": 1, "min": 0, "max": 5})

    assert store.get_primitive("scene:main/meters/tension")["value"] == 1
    assert (
        list(store.root["anchors"]["scene:main"]["primitives"].keys()).count("meters")
        == 1
    )


def test_store_rejects_anchor_collision_before_primitive_write():
    """Equivalent persisted anchor keys are rejected before primitive mutation."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.ensure_anchor("scene:main")
    store.root["anchors"]["scene: main"] = {}
    before = scene.game_state.model_dump(mode="json")

    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", {"value": 1})

    assert scene.game_state.model_dump(mode="json") == before


def test_store_rejects_non_dict_primitive_payload():
    """Primitive writes require dictionary payloads for JSON object storage."""
    store = PrimitiveStore.for_scene(Scene())

    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", 3)


def test_store_definition_key_must_match_typed_model_id():
    """Typed definition writes enforce the canonical key and model id invariant."""
    store = PrimitiveStore.for_scene(Scene())

    with pytest.raises(PrimitiveStoreError, match="must match id"):
        store.set_definition(
            "meters",
            "focus",
            {"id": "attention", "min": 0, "max": 5, "value": 2},
        )

    assert store.get_definition("meters", "focus") is None


def test_store_rejects_non_json_primitive_payload_without_partial_write():
    """Invalid nested payload values fail before mutating primitive state."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    before = scene.game_state.model_dump(mode="json")

    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", {"value": object()})

    assert scene.game_state.model_dump(mode="json") == before
    assert store.get_primitive("scene:main/meters/tension") is None


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_store_rejects_non_finite_primitive_payload(value):
    """Primitive payloads reject non-finite floats before persistence."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    before = scene.game_state.model_dump(mode="json")

    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", {"value": value})

    assert scene.game_state.model_dump(mode="json") == before


def test_store_rejects_runtime_corrupt_primitive_kind_payload():
    """Runtime corruption under an anchor primitive kind fails loudly on access."""
    store = PrimitiveStore.for_scene(Scene())
    store.ensure_anchor("scene:main")
    store.root["anchors"]["scene:main"]["primitives"]["meters"] = []

    with pytest.raises(PrimitiveStoreError):
        store.get_primitive("scene:main/meters/tension")


def test_store_rejects_bad_ledger_state_without_partial_primitive_write():
    """A corrupt ledger prevents primitive writes before state is mutated."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.root["ledger"] = {}
    before = scene.game_state.model_dump(mode="json")

    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", {"value": 1})

    assert scene.game_state.model_dump(mode="json") == before
    assert "scene:main" not in store.root["anchors"]


def test_store_rejects_bad_ledger_limit_without_partial_primitive_write():
    """An invalid ledger retention limit prevents primitive mutation."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.max_ledger_length = True
    before = scene.game_state.model_dump(mode="json")

    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", {"value": 1})

    assert scene.game_state.model_dump(mode="json") == before


def test_delete_primitive_ledger_failure_does_not_remove_primitive():
    """Delete validates ledger state before removing primitive data."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/tension",
        {"id": "tension", "value": 1, "min": 0, "max": 5},
    )
    before = scene.game_state.model_dump(mode="json")
    store.root["ledger"] = {}

    with pytest.raises(PrimitiveStoreError):
        store.delete_primitive("scene:main/meters/tension")

    assert (
        scene.game_state.variables[GAME_PRIMITIVES_KEY]["anchors"]
        == before["variables"][GAME_PRIMITIVES_KEY]["anchors"]
    )


def test_delete_primitive_ledger_limit_failure_does_not_remove_primitive():
    """Delete validates ledger retention limits before removing primitive data."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/tension",
        {"id": "tension", "value": 1, "min": 0, "max": 5},
    )
    before = scene.game_state.model_dump(mode="json")
    store.max_ledger_length = False

    with pytest.raises(PrimitiveStoreError):
        store.delete_primitive("scene:main/meters/tension")

    assert scene.game_state.model_dump(mode="json") == before
    assert store.get_primitive("scene:main/meters/tension")["value"] == 1

    store.max_ledger_length = 0
    with pytest.raises(PrimitiveStoreError):
        store.set_primitive("scene:main/meters/tension", {"value": 1})

    assert scene.game_state.model_dump(mode="json") == before


def test_ledger_append_and_trimming():
    """Ledger entries validate, append, trim oldest entries, and copy reads."""
    store = PrimitiveStore.for_scene(Scene(), max_ledger_length=2)

    store.append_ledger(LedgerEntry(op="test.zero", output={"n": 0}))
    store.append_ledger({"op": "test.one", "output": {"n": 1}})
    store.append_ledger({"op": "test.two", "output": {"n": 2}})

    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]
    assert [entry["op"] for entry in store.recent_ledger(1)] == ["test.two"]
    for invalid_limit in [0, True, "1", None, 1.0]:
        with pytest.raises(PrimitiveStoreError):
            store.recent_ledger(invalid_limit)

    recent = store.recent_ledger(1)
    recent[0]["op"] = "mutated"
    assert store.recent_ledger(1)[0]["op"] == "test.two"

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": ""})
    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": "bad.ref", "ref": "not-a-primitive-ref"})
    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": "bad.anchor", "anchor": "not-an-anchor"})
    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": "bad.nan", "input": {"value": math.nan}})
    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": "bad.inf", "output": {"value": math.inf}})
    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]

    store.max_ledger_length = None
    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": "bad.limit"})
    assert [entry["op"] for entry in store.recent_ledger()] == [
        "test.one",
        "test.two",
    ]


def test_append_ledger_invalid_limit_does_not_normalize_partial_root():
    """Append validates ledger limit before normalizing persisted root shape."""
    root = default_root()
    store = PrimitiveStore(root, max_ledger_length=1)
    root.pop("definitions")
    before = copy.deepcopy(root)
    store.max_ledger_length = None

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": "bad.limit"})

    assert root == before


def test_append_ledger_invalid_entry_does_not_normalize_partial_root():
    """Append validates new entries before normalizing persisted root shape."""
    root = default_root()
    store = PrimitiveStore(root, max_ledger_length=1)
    root.pop("definitions")
    before = copy.deepcopy(root)

    with pytest.raises(PrimitiveStoreError):
        store.append_ledger({"op": ""})

    assert root == before


def test_store_rejects_non_finite_values_in_persisted_root():
    """Persisted root JSON payloads reject non-finite floats on load."""
    scene = Scene()
    scene.game_state.variables[GAME_PRIMITIVES_KEY] = {"runtime": {"bad": math.inf}}

    with pytest.raises(PrimitiveStoreError):
        PrimitiveStore.for_scene(scene)


def test_recent_ledger_rejects_corrupt_persisted_ledger():
    """Ledger reads validate persisted entries instead of returning corrupt data."""
    store = PrimitiveStore.for_scene(Scene())
    store.root["ledger"] = [{"op": ""}]

    with pytest.raises(PrimitiveStoreError):
        store.recent_ledger()

    store.root["ledger"] = {}
    with pytest.raises(PrimitiveStoreError):
        store.recent_ledger()


def test_store_root_is_json_serializable_and_reloadable():
    """Primitive state survives a game-state-level JSON round trip."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "scene:main/meters/tension",
        {"id": "tension", "value": 4, "min": 0, "max": 10},
    )
    store.append_ledger({"op": "test.render", "input": {"anchor": "scene:main"}})

    dumped = json.dumps(scene.game_state.model_dump(mode="json"))
    loaded = json.loads(dumped)

    reloaded_scene = Scene()
    reloaded_scene.game_state.variables = loaded["variables"]
    reloaded_store = PrimitiveStore.for_scene(reloaded_scene)

    assert reloaded_store.get_primitive("scene:main/meters/tension")["value"] == 4
    assert reloaded_store.recent_ledger(1)[0]["op"] == "test.render"
