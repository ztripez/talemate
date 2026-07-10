"""Tests for FOCAL primitive authoring callbacks."""

import json

import pytest

from talemate.game.primitives.authoring.focal import PrimitiveAuthoringFocal
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene

EXPECTED_CALLBACKS = {
    "create_anchor",
    "create_meter",
    "create_clock",
    "create_deck",
    "create_roll_table",
    "create_relationship_model",
    "create_modifier",
    "create_attribute_source",
    "validate_draft",
    "commit_draft",
}


@pytest.mark.asyncio
async def test_callbacks_bind_draft_and_return_json_serializable_dictionaries():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "focal-draft")
    callbacks = {
        callback.name: callback
        for callback in PrimitiveAuthoringFocal(service).callbacks(scene, "focal-draft")
    }

    assert set(callbacks) == EXPECTED_CALLBACKS
    assert all(
        "draft_id" not in {argument.name for argument in callback.arguments}
        for callback in callbacks.values()
    )
    attribute_argument_types = {
        argument.name: argument.type
        for argument in callbacks["create_attribute_source"].arguments
    }
    assert attribute_argument_types["value"] == "any"
    assert {"anchor", "instance_id"} <= {
        argument.name for argument in callbacks["create_deck"].arguments
    }
    assert {"anchor", "instance_id"} <= {
        argument.name for argument in callbacks["create_roll_table"].arguments
    }
    assert "explanation" in {
        argument.name for argument in callbacks["create_modifier"].arguments
    }

    results = [
        await callbacks["create_anchor"].fn(
            kind="character", id="Alice", tags=[], meta={}
        ),
        await callbacks["create_meter"].fn(
            anchor="character:Alice",
            id="focus",
            label="Focus",
            min=0,
            max=5,
            value=3,
            render_policy="hidden",
        ),
        await callbacks["create_clock"].fn(
            anchor="character:Alice",
            id="danger",
            label="Danger",
            max=4,
            value=1,
            render_policy="summary",
        ),
        await callbacks["create_deck"].fn(
            id="moods",
            name="Moods",
            mode="bag",
            cards=[{"id": "calm", "label": "Calm"}],
            anchor="character:Alice",
        ),
        await callbacks["create_roll_table"].fn(
            id="weather",
            name="Weather",
            mode="weighted",
            rows=[{"id": "sun", "label": "Sunny", "weight": 1}],
            anchor="character:Alice",
            instance_id="local-weather",
        ),
        await callbacks["create_relationship_model"].fn(
            source="Alice",
            target="Bob",
            dimensions=[{"id": "trust", "value": 2}],
            tags=[],
        ),
        await callbacks["create_modifier"].fn(
            id="focused",
            label="Focused",
            applies_to="character:Alice/meters/focus",
            when=[],
            operation={"add": 1},
            explanation="Alice is focused.",
        ),
        await callbacks["create_attribute_source"].fn(
            anchor="character:Alice",
            id="mood",
            source="deck",
            render_policy="hidden",
            ref="moods",
            options={},
        ),
    ]

    assert all(isinstance(result, dict) for result in results)
    assert all(result["id"] == "focal-draft" for result in results)
    for result in results:
        json.dumps(result)


@pytest.mark.asyncio
async def test_validate_and_commit_callbacks_use_bound_draft():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "bound")
    callbacks = {
        callback.name: callback
        for callback in PrimitiveAuthoringFocal(service).callbacks(scene, "bound")
    }
    await callbacks["create_anchor"].fn(kind="scene", id="main")

    validated = await callbacks["validate_draft"].fn()
    committed = await callbacks["commit_draft"].fn()

    assert validated["id"] == "bound"
    assert validated["status"] == "validated"
    assert committed["id"] == "bound"
    assert committed["status"] == "committed"
    assert PrimitiveStore.for_scene(scene).get_anchor("scene:main") is not None
    json.dumps(validated)
    json.dumps(committed)


@pytest.mark.asyncio
async def test_callback_arguments_are_validated_by_request_models():
    scene = Scene()
    service = PrimitiveAuthoringService()
    service.create_draft(scene, "invalid")
    callbacks = {
        callback.name: callback
        for callback in PrimitiveAuthoringFocal(service).callbacks(scene, "invalid")
    }

    with pytest.raises(ValueError):
        await callbacks["create_clock"].fn(anchor="scene:main", id="clock", max="four")
    with pytest.raises(ValueError, match="instance_id requires anchor"):
        await callbacks["create_deck"].fn(
            id="deck",
            name="Deck",
            mode="bag",
            cards=[{"id": "card", "label": "Card"}],
            instance_id="custom",
        )

    assert service.drafts.get(scene, "invalid").anchors == {}
