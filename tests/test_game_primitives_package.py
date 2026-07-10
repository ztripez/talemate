"""Tests for the installable Game Primitives prompt bridge package."""

from __future__ import annotations

import os

import pytest
from _game_primitives_test_helpers import seed_prompt_attribute

import talemate.emit.async_signals as async_signals
import talemate.game.engine.nodes.load_definitions  # noqa: F401 - imports template modules
import talemate.game.engine.nodes.packaging as packaging_module
from talemate.agents.base import DynamicInstruction
from talemate.agents.conversation import ConversationAgentEmission
from talemate.agents.creator.assistant import ContextualGenerateEmission
from talemate.agents.narrator import NarratorAgentEmission
from talemate.character import Character
from talemate.context import ActiveScene
from talemate.game.engine.nodes.core import GraphContext
from talemate.game.engine.nodes.event import connect_listeners
from talemate.game.engine.nodes.packaging import (
    PackageData,
    PackageInitializationError,
    get_package_by_registry,
    get_scene_package_info,
    initialize_package,
    install_package,
    uninstall_package,
)
from talemate.game.engine.nodes.registry import (
    get_node,
    import_initial_node_definitions,
)
from talemate.game.engine.nodes.scene import SceneLoop
from talemate.game.primitives.attributes import AttributeResolver
from talemate.game.primitives.schema import GAME_PRIMITIVES_KEY
from talemate.tale_mate import Scene

PACKAGE_REGISTRY = "package/talemate/GamePrimitives"
LISTENER_REGISTRIES = {
    "game/primitives/initialize",
    "game/primitives/injectConversationContext",
    "game/primitives/injectNarratorContext",
    "game/primitives/injectCreatorContext",
}

import_initial_node_definitions()


@pytest.fixture
def scene(tmp_path, monkeypatch):
    """Return a scene with isolated package persistence."""
    monkeypatch.setattr(
        Scene, "scenes_dir", classmethod(lambda cls: str(tmp_path)), raising=True
    )
    value = Scene()
    value.project_name = "game-primitives-package-test"
    os.makedirs(value.save_dir, exist_ok=True)
    return value


def _seed_weather(scene: Scene) -> None:
    """Store one prompt-visible scene attribute for listener tests."""
    seed_prompt_attribute(scene, "scene:main/attributes/weather")


@pytest.mark.asyncio
async def test_game_primitives_package_and_listeners_are_discoverable():
    """Template discovery registers the package and all listener modules."""
    package = await get_package_by_registry(PACKAGE_REGISTRY)

    assert package is not None
    assert package.name == "Game Primitives"
    assert package.restart_scene_loop is True
    assert set(package.install_nodes) == LISTENER_REGISTRIES
    for registry in LISTENER_REGISTRIES:
        assert get_node(registry) is not None


@pytest.mark.asyncio
async def test_package_initialization_tracks_installed_listener_ids(scene):
    """Initializing the package persists every attached listener node id."""
    package = await get_package_by_registry(PACKAGE_REGISTRY)
    await install_package(scene, package)
    scene_loop = SceneLoop()

    installed = await initialize_package(scene, scene_loop, package)
    persisted = await get_scene_package_info(scene)
    persisted_package = persisted.get_package(PACKAGE_REGISTRY)

    assert len(installed.installed_nodes) == len(LISTENER_REGISTRIES)
    assert installed.installed_nodes == persisted_package.installed_nodes
    assert set(installed.installed_nodes).issubset(scene_loop.nodes)
    assert {
        scene_loop.nodes[node_id].registry for node_id in installed.installed_nodes
    } == LISTENER_REGISTRIES


@pytest.mark.asyncio
async def test_package_uninstall_removes_attached_listener_nodes(scene):
    """Uninstalling the package removes its listeners from the active scene loop."""
    package = await get_package_by_registry(PACKAGE_REGISTRY)
    await install_package(scene, package)
    scene_loop = SceneLoop()
    scene.creative_node_graph = scene_loop
    installed = await initialize_package(scene, scene_loop, package)
    installed_ids = set(installed.installed_nodes)

    await uninstall_package(scene, PACKAGE_REGISTRY)
    persisted = await get_scene_package_info(scene)

    assert installed_ids
    assert installed_ids.isdisjoint(scene_loop.nodes)
    assert not persisted.has_package(PACKAGE_REGISTRY)


@pytest.mark.asyncio
async def test_conversation_listener_module_appends_dynamic_instruction(scene):
    """Installed conversation listener graph mutates the real emission payload."""
    _seed_weather(scene)
    event = ConversationAgentEmission(
        agent=object(),
        actor=None,
        character=Character(name="Model"),
        response="",
    )
    listener = get_node("game/primitives/injectConversationContext")()

    with ActiveScene(scene), GraphContext():
        await listener.execute_from_event(event)

    assert len(event.dynamic_instructions) == 1
    assert event.dynamic_instructions[0].title == "Game Primitives - Relevant State"
    assert "Weather: Rainy" in event.dynamic_instructions[0].content


@pytest.mark.asyncio
async def test_narrator_listener_module_appends_dynamic_instruction(scene):
    """Narrator listener graph appends scene-wide prompt-safe context."""
    _seed_weather(scene)
    event = NarratorAgentEmission(agent=object())
    listener = get_node("game/primitives/injectNarratorContext")()

    with ActiveScene(scene), GraphContext():
        await listener.execute_from_event(event)

    assert len(event.dynamic_instructions) == 1
    assert isinstance(event.dynamic_instructions[0], DynamicInstruction)
    assert "Weather: Rainy" in event.dynamic_instructions[0].content


@pytest.mark.asyncio
async def test_creator_listener_module_injects_only_character_context(scene):
    """Creator listener excludes scene runtime and injects focused character data."""
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "scene:main/attributes/danger",
        {"source": "literal", "render_policy": "prompt", "value": "Immediate"},
    )
    resolver.set(
        scene,
        "character:Model/attributes/pose",
        {"source": "literal", "render_policy": "prompt", "value": "Relaxed"},
    )
    event = ContextualGenerateEmission(
        agent=object(), character=Character(name="Model")
    )
    listener = get_node("game/primitives/injectCreatorContext")()

    with ActiveScene(scene), GraphContext():
        await listener.execute_from_event(event)

    assert len(event.dynamic_instructions) == 1
    assert isinstance(event.dynamic_instructions[0], DynamicInstruction)
    assert "Pose: Relaxed" in event.dynamic_instructions[0].content
    assert "Immediate" not in event.dynamic_instructions[0].content


@pytest.mark.asyncio
async def test_initialize_listener_creates_primitive_store(scene):
    """Initialization listener creates the primitive store on scene-loop startup."""
    listener = get_node("game/primitives/initialize")()

    with ActiveScene(scene), GraphContext():
        await listener.execute_from_event(object())

    assert GAME_PRIMITIVES_KEY in scene.game_state.variables


@pytest.mark.asyncio
async def test_uninstall_disconnects_live_conversation_listener(scene):
    """Uninstall removes the package listener from the async signal receiver list."""
    _seed_weather(scene)
    package = await get_package_by_registry(PACKAGE_REGISTRY)
    await install_package(scene, package)
    scene_loop = SceneLoop()
    scene.creative_node_graph = scene_loop
    await initialize_package(scene, scene_loop, package)
    signal = async_signals.get("agent.conversation.inject_instructions")
    event = ConversationAgentEmission(
        agent=object(),
        actor=None,
        character=Character(name="Model"),
        response="",
    )

    with ActiveScene(scene), GraphContext() as state:
        connect_listeners(scene_loop, state)
        await signal.send(event)
    assert len(event.dynamic_instructions) == 1
    event.dynamic_instructions.clear()

    await uninstall_package(scene, PACKAGE_REGISTRY)
    with ActiveScene(scene), GraphContext():
        await signal.send(event)

    assert event.dynamic_instructions == []


@pytest.mark.asyncio
async def test_initialize_package_requires_persisted_installation(scene):
    """Package initialization fails loudly when the package is not installed."""
    package = PackageData(
        name="Missing",
        author="Tester",
        description="Not installed",
        installable=True,
        registry="test/package/missing",
    )

    with pytest.raises(PackageInitializationError, match="not installed"):
        await initialize_package(scene, SceneLoop(), package)


@pytest.mark.asyncio
async def test_initialize_package_rolls_back_failed_replacement(scene):
    """Failed package initialization leaves no partially attached replacement nodes."""
    package = PackageData(
        name="Broken",
        author="Tester",
        description="Missing node registry",
        installable=True,
        registry="test/package/broken",
        install_nodes=["test/package/does-not-exist"],
    )
    await install_package(scene, package)
    scene_loop = SceneLoop()
    before = set(scene_loop.nodes)

    with pytest.raises(PackageInitializationError, match="Failed to initialize"):
        await initialize_package(scene, scene_loop, package)

    persisted = await get_scene_package_info(scene)
    assert set(scene_loop.nodes) == before
    assert persisted.get_package(package.registry).installed_nodes == []


@pytest.mark.asyncio
async def test_reinitialize_package_replaces_fixed_id_listener_instances(scene):
    """Reinitializing fixed-ID JSON modules keeps one fresh listener per registry."""
    package = await get_package_by_registry(PACKAGE_REGISTRY)
    await install_package(scene, package)
    scene_loop = SceneLoop()
    first = await initialize_package(scene, scene_loop, package)
    first_nodes = {
        node_id: scene_loop.nodes[node_id] for node_id in first.installed_nodes
    }

    second = await initialize_package(scene, scene_loop, first)

    assert second.installed_nodes == first.installed_nodes
    assert set(second.installed_nodes).issubset(scene_loop.nodes)
    assert all(
        scene_loop.nodes[node_id] is not first_nodes[node_id]
        for node_id in second.installed_nodes
    )


@pytest.mark.asyncio
async def test_reinitialize_package_restores_prior_nodes_on_persistence_failure(
    scene, monkeypatch
):
    """Persistence failure removes replacements and restores prior listener objects."""
    package = await get_package_by_registry(PACKAGE_REGISTRY)
    await install_package(scene, package)
    scene_loop = SceneLoop()
    installed = await initialize_package(scene, scene_loop, package)
    prior_nodes = {
        node_id: scene_loop.nodes[node_id] for node_id in installed.installed_nodes
    }

    async def fail_save(scene, scene_package_info):
        raise OSError("simulated persistence failure")

    monkeypatch.setattr(packaging_module, "save_scene_package_info", fail_save)
    with pytest.raises(PackageInitializationError, match="persistence failure"):
        await initialize_package(scene, scene_loop, installed)

    assert all(
        scene_loop.nodes[node_id] is prior_nodes[node_id] for node_id in prior_nodes
    )


@pytest.mark.asyncio
async def test_package_initialization_rejects_foreign_fixed_id_collision(scene):
    """A second package cannot overwrite fixed-ID nodes owned by another package."""
    first_package = await get_package_by_registry(PACKAGE_REGISTRY)
    await install_package(scene, first_package)
    scene_loop = SceneLoop()
    first = await initialize_package(scene, scene_loop, first_package)
    owned_nodes = {
        node_id: scene_loop.nodes[node_id] for node_id in first.installed_nodes
    }
    second_package = PackageData(
        name="Collision",
        author="Tester",
        description="Attempts to reuse a listener module",
        installable=True,
        registry="test/package/collision",
        install_nodes=["game/primitives/injectConversationContext"],
    )
    await install_package(scene, second_package)

    with pytest.raises(PackageInitializationError, match="does not own"):
        await initialize_package(scene, scene_loop, second_package)

    assert all(
        scene_loop.nodes[node_id] is owned_nodes[node_id] for node_id in owned_nodes
    )
