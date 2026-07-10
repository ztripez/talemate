"""Integration tests for opted-in primitive generation during scene loading."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from pydantic import ValidationError

from talemate import Scene
from talemate.game.primitives.authoring.planner import PrimitiveScenarioBundleResult
from talemate.load import SceneInitialization, load_scene_from_data


def _scene_data(**overrides):
    data = {
        "description": "Scene description",
        "intro": "Scene intro",
        "name": "New scene",
        "environment": "scene",
        "history": [],
        "archived_history": [],
        "character_data": {},
        "active_characters": [],
    }
    data.update(overrides)
    return data


@pytest.fixture
def load_dependencies(monkeypatch):
    memory = SimpleNamespace(set_db=AsyncMock())
    creator = SimpleNamespace(generate_primitive_bundle_for_scenario=AsyncMock())

    def get_agent(name):
        return creator if name == "creator" else memory

    monkeypatch.setattr("talemate.load.instance.get_agent", get_agent)
    monkeypatch.setattr("talemate.load.initialization.instance.get_agent", get_agent)
    monkeypatch.setattr(
        "talemate.load.import_scene_node_definitions", lambda _scene: None
    )
    monkeypatch.setattr(
        "talemate.load.handle_no_player_character", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "talemate.load.voice_library.load_scene_voice_library",
        AsyncMock(return_value=SimpleNamespace()),
    )
    monkeypatch.setattr(
        "talemate.world_state.manager.WorldStateManager.remove_all_empty_pins",
        AsyncMock(return_value=None),
    )
    return creator


@pytest.mark.asyncio
async def test_no_opt_in_does_not_resolve_creator(load_dependencies):
    creator = load_dependencies

    scene = await load_scene_from_data(Scene(), _scene_data(), reset=True, empty=True)

    creator.generate_primitive_bundle_for_scenario.assert_not_awaited()
    assert scene.primitive_scenario_bundle_initialization_result is None
    assert SceneInitialization().generate_primitive_bundle is False


@pytest.mark.asyncio
async def test_opt_in_production_hook_runs_after_intro(load_dependencies):
    creator = load_dependencies
    creator.generate_primitive_bundle_for_scenario.return_value = (
        PrimitiveScenarioBundleResult(ok=True, committed=True)
    )
    scene_data = _scene_data(
        description="",
        intro="Generated intro",
        generate_primitive_bundle=True,
        primitive_bundle_description=None,
    )

    scene = await load_scene_from_data(Scene(), scene_data, reset=True, empty=True)

    assert creator.generate_primitive_bundle_for_scenario.await_args == call(
        scene=scene,
        description="Generated intro",
        characters=[],
        auto_commit=True,
    )
    assert scene.primitive_scenario_bundle_initialization_result["ok"] is True


@pytest.mark.asyncio
async def test_expected_failure_returns_usable_scene_and_exposes_result(
    load_dependencies, monkeypatch
):
    creator = load_dependencies
    result = PrimitiveScenarioBundleResult(ok=False, errors=["invalid meter"])
    creator.generate_primitive_bundle_for_scenario.return_value = result
    emit = MagicMock()
    monkeypatch.setattr("talemate.load.initialization.emit", emit)

    scene = await load_scene_from_data(
        Scene(),
        _scene_data(generate_primitive_bundle=True),
        reset=True,
        empty=True,
    )

    assert scene.name == "New scene"
    assert scene.primitive_scenario_bundle_initialization_result == result.model_dump(
        mode="json"
    )
    emit.assert_called_once_with(
        "status",
        message="Primitive scenario initialization failed",
        status="error",
        scene=scene,
        data={"primitive_scenario_bundle_result": result.model_dump(mode="json")},
    )


@pytest.mark.asyncio
async def test_programming_error_propagates(load_dependencies):
    creator = load_dependencies
    creator.generate_primitive_bundle_for_scenario.side_effect = RuntimeError("bug")

    with pytest.raises(RuntimeError, match="bug"):
        await load_scene_from_data(
            Scene(),
            _scene_data(generate_primitive_bundle=True),
            reset=True,
            empty=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generate_primitive_bundle", "true"),
        ("primitive_bundle_description", 123),
        ("intro_instructions", 123),
    ],
)
async def test_primitive_initialization_rejects_malformed_fields(
    load_dependencies, field, value
):
    with pytest.raises(ValidationError):
        await load_scene_from_data(
            Scene(),
            _scene_data(**{field: value}),
            reset=True,
            empty=True,
        )
