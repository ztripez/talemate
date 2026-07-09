"""Smoke tests for Game Primitives Python node registration."""

from __future__ import annotations

import copy
import importlib

from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
from talemate.context import ActiveScene
from talemate.game.engine.nodes.registry import get_node
from talemate.tale_mate import Scene


async def test_debug_ping_node_is_registered_and_runs():
    """Verify the primitive debug node registers, runs, and preserves scene state."""
    scene = Scene()
    before_import = copy.deepcopy(scene.game_state.model_dump())

    with ActiveScene(scene):
        primitives_package = importlib.import_module("talemate.game.primitives")
        importlib.reload(primitives_package)
        node_cls = get_node("primitives/DebugPing")

    after_import = copy.deepcopy(scene.game_state.model_dump())
    node = node_cls()
    assert node.inputs == []
    socket_types = {socket.name: socket.socket_type for socket in node.outputs}

    before_run = copy.deepcopy(scene.game_state.model_dump())
    outputs = await run_node(node, scene=scene)
    after_run = copy.deepcopy(scene.game_state.model_dump())

    assert "PrimitiveStore" in primitives_package.__all__
    assert after_import == before_import
    assert after_run == before_run
    assert socket_types == {"ok": "bool", "message": "str"}
    assert outputs["ok"] is True
    assert outputs["message"] == "game-primitives"
    assert outputs["ok__deactivated"] is False
    assert outputs["message__deactivated"] is False
