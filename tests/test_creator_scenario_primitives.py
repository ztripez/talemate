"""Tests for creator-driven scenario primitive authoring."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pydantic
import pytest

from talemate.agents.creator.primitives import ScenarioPrimitiveCreatorMixin
from talemate.character import Character
from talemate.game.primitives.authoring.planner import PrimitiveScenarioPlan
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


class _Creator(ScenarioPrimitiveCreatorMixin):
    def __init__(self, scene):
        self.scene = scene
        self.client = SimpleNamespace()


def _attach_character(scene, character):
    actor = scene.Actor(character, None)
    scene.actors.append(actor)
    scene.character_data[character.name] = character
    scene.active_characters.append(character.name)
    actor.scene = scene


class _Focal:
    action = None
    instances = []

    def __init__(self, _client, callbacks, max_calls, **context):
        self.callbacks = {callback.name: callback for callback in callbacks}
        self.max_calls = max_calls
        self.context = context
        self.state = SimpleNamespace(calls=[])
        self.instances.append(self)

    async def request(self, template):
        assert template == "creator.primitive-authoring"
        if type(self).action:
            await type(self).action(self)


@pytest.fixture(autouse=True)
def mock_generation(monkeypatch):
    _Focal.action = None
    _Focal.instances = []
    request = AsyncMock(
        return_value=(
            "",
            {
                "response": {
                    "needed": True,
                    "rationale": "Tension should persist.",
                    "anchors": [{"kind": "scene", "id": "main"}],
                    "systems": [
                        {
                            "kind": "meter",
                            "id": "tension_meter",
                            "anchor": {"kind": "scene", "id": "main"},
                            "purpose": "Track tension.",
                            "visibility": "hidden",
                            "depends_on": [],
                        }
                    ],
                    "prompt_visible": [],
                    "hidden": [],
                    "warnings": [],
                }
            },
        )
    )
    monkeypatch.setattr("talemate.agents.creator.primitives.Prompt.request", request)
    monkeypatch.setattr("talemate.agents.creator.primitives.focal.Focal", _Focal)
    return request


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("anchors", [{"kind": "character", "id": "Alice"}] * 2),
        (
            "systems",
            [
                {
                    "kind": "meter",
                    "id": "stress",
                    "anchor": None,
                    "purpose": "Track stress.",
                    "visibility": "hidden",
                    "depends_on": [],
                }
            ]
            * 2,
        ),
        ("prompt_visible", ["mood", "mood"]),
        ("hidden", [""]),
        ("warnings", ["risk", "risk"]),
    ],
)
def test_plan_rejects_duplicate_and_blank_content(field, value):
    payload = {
        "needed": True,
        "rationale": "Persistent mechanics are useful.",
        "anchors": [{"kind": "character", "id": "Alice"}],
        "systems": [],
        "prompt_visible": [],
        "hidden": [],
        "warnings": [],
    }
    payload[field] = value

    with pytest.raises(ValueError):
        PrimitiveScenarioPlan.model_validate(payload, strict=True)


def test_plan_requires_content_when_needed():
    with pytest.raises(ValueError, match="needed=True"):
        PrimitiveScenarioPlan.model_validate(
            {
                "needed": True,
                "rationale": "Persistent mechanics might be useful.",
                "anchors": [],
                "systems": [],
                "prompt_visible": [],
                "hidden": [],
                "warnings": [],
            },
            strict=True,
        )


@pytest.mark.parametrize(
    "omitted_field",
    (
        "needed",
        "rationale",
        "anchors",
        "systems",
        "prompt_visible",
        "hidden",
        "warnings",
    ),
)
def test_plan_requires_every_prompt_field(omitted_field):
    payload = {
        "needed": False,
        "rationale": "No persistent mechanics are useful.",
        "anchors": [],
        "systems": [],
        "prompt_visible": [],
        "hidden": [],
        "warnings": [],
    }
    del payload[omitted_field]

    with pytest.raises(pydantic.ValidationError) as exc_info:
        PrimitiveScenarioPlan.model_validate(payload, strict=True)

    assert exc_info.value.errors()[0]["loc"] == (omitted_field,)
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_plan_preserves_explicit_no_op_with_all_required_empty_lists():
    payload = {
        "needed": False,
        "rationale": "No persistent mechanics are useful.",
        "anchors": [],
        "systems": [],
        "prompt_visible": [],
        "hidden": [],
        "warnings": [],
    }

    plan = PrimitiveScenarioPlan.model_validate(payload, strict=True)

    assert plan.model_dump() == payload
    assert plan.is_empty


@pytest.mark.parametrize(
    "payload",
    [
        {
            "needed": True,
            "anchors": [{"kind": "not-an-anchor", "id": "main"}],
            "systems": [{"id": "stress", "kind": "meter"}],
        },
        {
            "needed": True,
            "anchors": ["character:Alice", "character:Alice"],
            "systems": [{"id": "stress", "kind": "meter"}],
        },
        {
            "needed": True,
            "anchors": ["character:Alice"],
            "systems": ["stress", "stress"],
        },
        {"needed": True, "anchors": [], "systems": []},
    ],
    ids=["malformed", "duplicate-anchor", "duplicate-system", "empty"],
)
def test_needed_plan_rejects_malformed_duplicate_or_empty_payload(payload):
    with pytest.raises(pydantic.ValidationError):
        PrimitiveScenarioPlan.model_validate(payload, strict=True)


@pytest.mark.asyncio
async def test_plan_reads_prompt_extractor_payload(mock_generation):
    mock_generation.return_value = (
        "",
        {
            "response": {
                "needed": False,
                "rationale": "No persistent mechanics are useful.",
                "anchors": [],
                "systems": [],
                "prompt_visible": [],
                "hidden": [],
                "warnings": [],
            }
        },
    )

    plan = await _Creator(Scene()).plan_primitives_for_scenario(
        description="A quiet room"
    )

    assert plan.is_empty
    assert not plan.needed
    assert mock_generation.call_args.kwargs["vars"]["scenario"] == "A quiet room"


@pytest.mark.asyncio
async def test_no_op_plan_does_not_create_draft(mock_generation):
    mock_generation.return_value = (
        "",
        {
            "response": {
                "needed": False,
                "rationale": "No persistent mechanics are useful.",
                "anchors": [],
                "systems": [],
                "prompt_visible": [],
                "hidden": [],
                "warnings": [],
            }
        },
    )
    scene = Scene()

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="A quiet room"
    )

    assert result.ok
    assert result.draft_id is None
    assert not _Focal.instances
    assert PrimitiveStore.for_scene(scene).root["drafts"] == {}


async def _create_meter(handler):
    await handler.callbacks["create_anchor"].fn(kind="scene", id="main")
    await handler.callbacks["create_meter"].fn(
        anchor="scene:main",
        id="tension",
        label="Tension",
        min=0,
        max=5,
        value=1,
        render_policy="hidden",
    )


async def _author_photoshoot_primitives(handler):
    callbacks = handler.callbacks
    await callbacks["create_anchor"].fn(kind="character", id="Alice")
    await callbacks["create_anchor"].fn(kind="character", id="Bob")
    await callbacks["create_meter"].fn(
        anchor="character:Alice",
        id="confidence",
        label="Confidence",
        min=0,
        max=5,
        value=3,
        render_policy="summary",
    )
    await callbacks["create_meter"].fn(
        anchor="character:Bob",
        id="stress",
        label="Stress",
        min=0,
        max=5,
        value=1,
        render_policy="hidden",
    )
    await callbacks["create_deck"].fn(
        id="poses",
        name="Pose Deck",
        mode="bag",
        cards=[
            {"id": "power", "label": "Power pose"},
            {"id": "candid", "label": "Candid pose"},
        ],
        anchor="character:Alice",
        instance_id="pose-deck",
    )
    await callbacks["create_relationship_model"].fn(
        source="Alice",
        target="Bob",
        dimensions=[
            {
                "id": "trust",
                "label": "Trust",
                "min": -5,
                "max": 5,
                "value": 2,
                "render_policy": "summary",
            }
        ],
        tags=["photoshoot"],
    )
    await callbacks["create_roll_table"].fn(
        id="shoot_outcome",
        name="Shoot Outcome",
        mode="weighted",
        rows=[
            {"id": "strong", "label": "Strong shot", "weight": 2},
            {"id": "awkward", "label": "Awkward shot", "weight": 1},
        ],
        anchor="character:Alice",
        instance_id="shoot-outcome",
    )
    await callbacks["create_modifier"].fn(
        id="confidence_bonus",
        label="Confidence bonus",
        applies_to="shoot_outcome",
        when=[],
        operation={"add": 1},
        explanation="Confidence improves the result.",
    )
    await callbacks["create_attribute_source"].fn(
        anchor="character:Alice",
        id="current_pose",
        source="deck",
        render_policy="prompt",
        ref="poses",
        options={},
    )


@pytest.mark.asyncio
async def test_valid_draft_auto_commits_and_reports_counts():
    _Focal.action = _create_meter
    scene = Scene()

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="A tense room"
    )

    assert result.ok and result.committed
    assert result.created.anchors == 1
    assert result.created.meters == 1
    assert "1 anchors" in result.summary
    assert "1 meters" in result.summary
    assert PrimitiveStore.for_scene(scene).get_anchor("scene:main") is not None
    assert _Focal.instances[0].max_calls >= 32
    assert set(_Focal.instances[0].callbacks) == {
        "create_anchor",
        "create_meter",
        "create_clock",
        "create_deck",
        "create_roll_table",
        "create_relationship_model",
        "create_modifier",
        "create_attribute_source",
    }


@pytest.mark.asyncio
async def test_photoshoot_authoring_reports_exact_counts_and_summary():
    _Focal.action = _author_photoshoot_primitives
    scene = Scene()
    for name in ("Alice", "Bob"):
        _attach_character(scene, Character(name=name))

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="Alice and Bob collaborate on a high-pressure photoshoot.",
        characters=["Alice", "Bob"],
    )

    assert result.model_dump() == {
        "ok": True,
        "draft_id": result.draft_id,
        "committed": True,
        "summary": (
            "Committed 3 anchors, 3 meters, 1 decks, 1 roll tables, "
            "1 relationships, 1 modifiers, 1 attribute sources."
        ),
        "created": {
            "anchors": 3,
            "meters": 3,
            "clocks": 0,
            "decks": 1,
            "roll_tables": 1,
            "relationships": 1,
            "modifiers": 1,
            "attribute_sources": 1,
        },
        "warnings": [
            "character:Alice/attributes/current_pose uses a mutating prompt source",
            "character:Alice/attributes/current_pose lacks guaranteed renderable text",
        ],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_valid_draft_is_left_uncommitted_when_requested():
    _Focal.action = _create_meter
    scene = Scene()

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="A tense room", auto_commit=False
    )

    assert result.ok and not result.committed
    assert PrimitiveStore.for_scene(scene).get_anchor("scene:main") is None
    assert PrimitiveStore.for_scene(scene).root["drafts"][result.draft_id]["anchors"]


@pytest.mark.asyncio
async def test_callback_error_makes_result_fail_without_commit():
    async def fail_call(handler):
        await _create_meter(handler)
        handler.state.calls.append(
            SimpleNamespace(name="create_deck", error="bad cards")
        )

    _Focal.action = fail_call
    scene = Scene()

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="A tense room"
    )

    assert not result.ok and not result.committed
    assert result.errors == ["create_deck: bad cards"]
    assert PrimitiveStore.for_scene(scene).get_anchor("scene:main") is None


@pytest.mark.asyncio
async def test_invalid_draft_returns_validation_errors():
    async def create_invalid_attribute(handler):
        await handler.callbacks["create_anchor"].fn(kind="scene", id="main")
        await handler.callbacks["create_attribute_source"].fn(
            anchor="scene:main",
            id="draw",
            source="deck",
            render_policy="hidden",
            ref="missing",
            options={},
        )

    _Focal.action = create_invalid_attribute
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    committed_before = copy.deepcopy(
        {"definitions": store.root["definitions"], "anchors": store.root["anchors"]}
    )

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="A card draw"
    )

    assert not result.ok and not result.committed
    assert result.draft_id
    assert any("Missing deck definition" in error for error in result.errors)
    persisted = store.root["drafts"][result.draft_id]
    assert persisted["id"] == result.draft_id
    assert persisted["status"] == "draft"
    assert persisted["validation"]["ok"] is False
    assert persisted["validation"]["errors"] == result.errors
    assert store.root["definitions"] == committed_before["definitions"]
    assert store.root["anchors"] == committed_before["anchors"]


@pytest.mark.asyncio
async def test_unexpected_programming_error_propagates(mock_generation):
    mock_generation.side_effect = RuntimeError("planner unavailable")

    with pytest.raises(RuntimeError, match="planner unavailable"):
        await _Creator(Scene()).generate_primitive_bundle_for_scenario(
            description="Anything"
        )


@pytest.mark.asyncio
async def test_generation_does_not_modify_character_base_attributes():
    _Focal.action = _author_photoshoot_primitives
    scene = Scene()
    characters = [
        Character(
            name="Alice",
            base_attributes={"strength": 3, "profession": "photographer"},
        ),
        Character(
            name="Bob",
            base_attributes={"stress": "nervous", "wardrobe": "formal"},
        ),
    ]
    for character in characters:
        _attach_character(scene, character)
    original = {
        character.name: copy.deepcopy(character.base_attributes)
        for character in scene.characters
    }

    result = await _Creator(scene).generate_primitive_bundle_for_scenario(
        description="Alice photographs Bob.",
        characters=[character.name for character in characters],
    )

    assert result.ok
    assert {
        character.name: character.base_attributes for character in scene.characters
    } == original
