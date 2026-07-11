"""Tests for canonical primitive authoring draft storage."""

import copy

import pytest

from talemate.game.primitives.authoring import PrimitiveDraftStore
from talemate.game.primitives.definitions import (
    DEFINITION_KINDS,
    ClockPayload,
    MeterPayload,
    PrimitiveDefinitions,
)
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.schema import (
    PrimitiveDraft,
    PrimitiveRootPayload,
)
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_existing_root_gains_empty_drafts_container():
    """Old valid roots migrate by adding the new typed drafts collection."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)

    assert store.root["drafts"] == {}


def test_meter_and_clock_enforce_canonical_bounds():
    """Canonical authored meters and clocks reject out-of-range values."""
    meter = MeterPayload(id="focus", min=0, max=5, value=3)
    clock = ClockPayload(id="escape", max=4, value=2)

    assert meter.render_policy == "hidden"
    assert clock.render_policy == "summary"
    with pytest.raises(ValueError, match="within"):
        MeterPayload(id="focus", min=0, max=5, value=6)
    with pytest.raises(ValueError, match="exceed"):
        ClockPayload(id="escape", max=4, value=5)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("decks", {"id": "bad", "name": "Bad", "cards": []}),
        (
            "roll_tables",
            {"id": "bad", "name": "Bad", "mode": "weighted", "rows": []},
        ),
        ("modifiers", {"id": "bad", "applies_to": "table", "add": "one"}),
        ("meters", {"id": "bad", "min": 0, "max": 1, "value": 2}),
        ("clocks", {"id": "bad", "max": 1, "value": 2}),
    ],
)
def test_typed_definitions_fail_at_root_and_draft_ingestion(kind, payload):
    """Root and draft boundaries reject every malformed typed definition kind."""
    definitions = {kind: {"bad": payload}}

    with pytest.raises(ValueError):
        PrimitiveRootPayload.model_validate({"definitions": definitions})
    with pytest.raises(ValueError):
        PrimitiveDraft.model_validate({"id": "draft", "definitions": definitions})


def test_primitive_definitions_roundtrip_as_direct_definitions_object():
    """Typed and generic definitions normalize and roundtrip without a root wrapper."""
    definitions = {
        "decks": {
            "deck": {
                "id": "deck",
                "name": "Deck",
                "cards": [{"id": "card", "label": "Card"}],
            }
        },
        "roll_tables": {
            "table": {
                "id": "table",
                "name": "Table",
                "mode": "weighted",
                "rows": [{"id": "row", "label": "Row", "weight": 1}],
            }
        },
        "modifiers": {"bonus": {"id": "bonus", "applies_to": "table", "add": 1}},
        "meters": {"focus": {"id": "focus", "min": 0, "max": 5, "value": 2}},
        "clocks": {"escape": {"id": "escape", "max": 4, "value": 1}},
        "relationship_models": {"default": {"dimensions": ["trust"]}},
        "attribute_sources": {"mood": {"source": "literal", "value": "calm"}},
        "adventures": {
            "intro": {
                "id": "intro",
                "title": "Introduction",
                "start_scene": "arrival",
                "scenes": {"arrival": {"id": "arrival", "title": "Arrival"}},
            }
        },
    }

    model = PrimitiveDefinitions.model_validate(definitions)
    dumped = model.model_dump(mode="json")
    root_dump = PrimitiveRootPayload(
        version=1,
        definitions=model,
        anchors={},
        runtime={},
        ledger=[],
        drafts={},
    ).model_dump(mode="json")
    draft_dump = PrimitiveDraft(id="draft", definitions=model).model_dump(mode="json")

    assert set(dumped) == set(DEFINITION_KINDS)
    assert dumped["relationship_models"] == definitions["relationship_models"]
    assert root_dump["definitions"] == dumped
    assert draft_dump["definitions"] == dumped
    assert PrimitiveDefinitions.model_validate(dumped).model_dump(mode="json") == dumped


def test_primitive_definition_key_must_match_typed_model_id():
    """Typed definition maps cannot address a model under a different id."""
    with pytest.raises(ValueError, match="must match id"):
        PrimitiveDefinitions.model_validate(
            {"meters": {"focus": {"id": "attention", "min": 0, "max": 5, "value": 2}}}
        )


def test_create_draft_does_not_change_committed_definitions_or_anchors():
    """Creating a draft mutates only the isolated drafts collection."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    committed = copy.deepcopy(
        {"definitions": store.root["definitions"], "anchors": store.root["anchors"]}
    )

    draft = PrimitiveDraftStore().create(scene, "session")

    assert draft.id == "session"
    assert draft.status == "draft"
    assert store.root["definitions"] == committed["definitions"]
    assert store.root["anchors"] == committed["anchors"]


def test_duplicate_and_missing_drafts_fail_loudly():
    """Draft lookup and creation reject ambiguous state."""
    scene = Scene()
    drafts = PrimitiveDraftStore()
    drafts.create(scene, "session")

    with pytest.raises(PrimitiveStoreError, match="already exists"):
        drafts.create(scene, "session")
    with pytest.raises(PrimitiveStoreError, match="not found"):
        drafts.get(scene, "missing")


def test_draft_id_is_generated_only_when_none():
    """Empty supplied IDs fail Pydantic validation instead of becoming generated IDs."""
    scene = Scene()
    drafts = PrimitiveDraftStore()

    generated = drafts.create(scene)

    assert generated.id.startswith("draft-")
    with pytest.raises(ValueError, match="at least 1 character"):
        drafts.create(scene, "")
    with pytest.raises(ValueError, match="at least 1 character"):
        drafts.create(scene, "   ")


def test_replace_validated_root_is_atomic_on_validation_failure():
    """Invalid replacement candidates leave the committed root byte-for-byte intact."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    before = copy.deepcopy(store.root)

    with pytest.raises(PrimitiveStoreError):
        store.replace_validated_root({"version": "invalid"})

    assert store.root == before


def test_replace_validated_root_preserves_root_identity():
    """Valid replacement swaps contents once while retaining scene dictionary identity."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    root = store.root
    candidate = copy.deepcopy(root)
    candidate["runtime"]["phase"] = "drafting"

    store.replace_validated_root(candidate)

    assert store.root is root
    assert store.root["runtime"]["phase"] == "drafting"
