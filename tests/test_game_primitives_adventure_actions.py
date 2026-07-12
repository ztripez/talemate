"""Strict websocket actions for AdventureEngine runtime control."""

from __future__ import annotations

import copy
from unittest.mock import MagicMock

import pydantic
import pytest

from talemate.game.primitives.store import PrimitiveStore
from talemate.server.world_state_manager import WorldStateManagerPlugin
from talemate.server.world_state_manager.game_primitives_request_contracts import (
    GAME_PRIMITIVES_REQUEST_ADAPTER,
)
from talemate.server.world_state_manager.game_primitives_handler_base import (
    CommittedResponseTransportError,
)
from talemate.tale_mate import Scene


def _scene(
    *,
    blocked: bool = False,
    failing_effect: bool = False,
    failing_activation: bool = False,
) -> Scene:
    scene = Scene()
    scene.config.game.general.auto_save = False
    conditions = (
        [{"operator": "and", "conditions": [{"kind": "never"}]}] if blocked else []
    )
    transition_effects = (
        [{"op": "inc", "target": "scene:main/meters/missing"}] if failing_effect else []
    )
    PrimitiveStore.for_scene(scene).set_definition(
        "adventures",
        "demo",
        {
            "id": "demo",
            "title": "Demo",
            "start_scene": "start",
            "scenes": {
                "start": {
                    "id": "start",
                    "title": "Start",
                    "entry_effects": (
                        [{"op": "inc", "target": "scene:main/meters/missing"}]
                        if failing_activation
                        else []
                    ),
                },
                "finish": {"id": "finish", "title": "Finish"},
            },
            "transitions": {
                "continue": {
                    "id": "continue",
                    "from_scene": "start",
                    "to_scene": "finish",
                    "label": "Continue",
                    "conditions": conditions,
                    "exit_effects": transition_effects,
                }
            },
        },
    )
    return scene


async def _request(scene: Scene, action: str, request_id: str, **fields) -> list[dict]:
    queued = []
    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = queued.append
    await WorldStateManagerPlugin(handler).handle(
        {
            "type": "world_state_manager",
            "action": action,
            "request_id": request_id,
            **fields,
        }
    )
    return queued


async def _committed_action(
    action: str,
) -> tuple[Scene, dict, dict]:
    scene = _scene()
    if action == "take_game_primitive_adventure_transition":
        await _request(
            scene, "activate_game_primitive_adventure", "prepare", adventure_id="demo"
        )
        request = {
            "type": "world_state_manager",
            "action": action,
            "request_id": "transport",
            "transition_id": "continue",
        }
    else:
        request = {
            "type": "world_state_manager",
            "action": action,
            "request_id": "transport",
            "adventure_id": "demo",
        }
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)
    return scene, request, before


def test_adventure_action_contracts_are_strict_and_action_discriminated():
    activation = GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(
        {
            "type": "world_state_manager",
            "action": "activate_game_primitive_adventure",
            "request_id": "activate",
            "adventure_id": "demo",
        },
        strict=True,
    )
    assert activation.adventure_id == "demo"

    with pytest.raises(pydantic.ValidationError, match="Extra inputs"):
        GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(
            {
                "type": "world_state_manager",
                "action": "take_game_primitive_adventure_transition",
                "request_id": "take",
                "transition_id": "continue",
                "runtime": {"current_story_scene": "finish"},
            },
            strict=True,
        )


@pytest.mark.asyncio
async def test_activation_returns_action_specific_snapshot_and_never_accepts_runtime():
    scene = _scene()
    queued = await _request(
        scene,
        "activate_game_primitive_adventure",
        "activate",
        adventure_id="demo",
    )

    response = queued[0]
    assert response["action"] == "game_primitive_adventure_activation"
    assert response["request_id"] == "activate"
    assert response["result"] == {
        "ok": True,
        "adventure_id": "demo",
        "state": {
            "adventure_id": "demo",
            "current_story_scene": "start",
            "visited": ["start"],
            "completed": [],
            "transition_log": [],
        },
        "error": None,
    }
    assert response["data"]["current_adventure"]["id"] == "demo"
    assert queued[1]["action"] == "operation_done"


@pytest.mark.asyncio
async def test_activation_rejection_is_structured_and_preserves_runtime():
    scene = _scene()
    await _request(
        scene,
        "activate_game_primitive_adventure",
        "first",
        adventure_id="demo",
    )
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)

    queued = await _request(
        scene,
        "activate_game_primitive_adventure",
        "second",
        adventure_id="demo",
    )

    assert queued[0]["result"]["ok"] is False
    assert queued[0]["result"]["error"] == "An adventure is already active"
    assert PrimitiveStore.for_scene(scene).root == before


@pytest.mark.asyncio
async def test_failed_activation_effect_is_structured_and_leaves_no_runtime():
    scene = _scene(failing_activation=True)
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)

    queued = await _request(
        scene,
        "activate_game_primitive_adventure",
        "failed-activation",
        adventure_id="demo",
    )

    assert queued[0]["result"]["ok"] is False
    assert queued[0]["result"]["error"]
    assert queued[0]["data"]["current_adventure"] is None
    assert PrimitiveStore.for_scene(scene).root == before


@pytest.mark.asyncio
async def test_unavailable_transition_returns_reasons_and_preserves_state():
    scene = _scene(blocked=True)
    await _request(
        scene, "activate_game_primitive_adventure", "activate", adventure_id="demo"
    )
    before = copy.deepcopy(PrimitiveStore.for_scene(scene).root)

    queued = await _request(
        scene,
        "take_game_primitive_adventure_transition",
        "blocked",
        transition_id="continue",
    )

    result = queued[0]["result"]
    assert result["ok"] is False
    assert result["error"] == "Transition conditions are not met"
    assert queued[0]["data"]["current_adventure"]["transitions"][0]["reasons"] == [
        "Transition conditions are not met"
    ]
    assert PrimitiveStore.for_scene(scene).root == before


@pytest.mark.asyncio
async def test_failed_transition_effect_and_successful_transition_are_atomic():
    failing_scene = _scene(failing_effect=True)
    await _request(
        failing_scene,
        "activate_game_primitive_adventure",
        "activate-failing",
        adventure_id="demo",
    )
    before = copy.deepcopy(PrimitiveStore.for_scene(failing_scene).root)
    failed = await _request(
        failing_scene,
        "take_game_primitive_adventure_transition",
        "failed-effect",
        transition_id="continue",
    )
    assert failed[0]["result"]["ok"] is False
    assert failed[0]["result"]["effects"][-1]["ok"] is False
    assert PrimitiveStore.for_scene(failing_scene).root == before

    scene = _scene()
    await _request(
        scene, "activate_game_primitive_adventure", "activate", adventure_id="demo"
    )
    succeeded = await _request(
        scene,
        "take_game_primitive_adventure_transition",
        "success",
        transition_id="continue",
    )
    response = succeeded[0]
    assert response["action"] == "game_primitive_adventure_transition"
    assert response["result"]["ok"] is True
    assert (
        response["data"]["current_adventure"]["current_story_scene"]["id"] == "finish"
    )
    assert response["data"]["current_adventure"]["state"]["transition_log"] == [
        {
            "transition_id": "continue",
            "from_scene": "start",
            "to_scene": "finish",
            "carry_anchors": [],
        }
    ]
    assert response["data"]["recent_ledger"][-1]["op"] == "adventure.transition"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "activate_game_primitive_adventure",
        "take_game_primitive_adventure_transition",
    ],
)
@pytest.mark.parametrize("failed_attempt", [1, 2])
async def test_committed_adventure_emission_failure_is_indeterminate(
    action: str, failed_attempt: int
):
    scene, request, before = await _committed_action(action)
    emitted = []
    attempts = 0
    committed = None

    def emit(message: dict) -> None:
        nonlocal attempts, committed
        attempts += 1
        if committed is None:
            committed = copy.deepcopy(PrimitiveStore.for_scene(scene).root)
        if attempts == failed_attempt:
            raise RuntimeError(f"queue attempt {failed_attempt} failed")
        emitted.append(message)

    handler = MagicMock(scene=scene)
    handler.queue_put.side_effect = emit
    await WorldStateManagerPlugin(handler).handle(request)

    assert committed != before
    assert PrimitiveStore.for_scene(scene).root == committed
    indeterminate = emitted[-1]
    assert indeterminate["action"] == "game_primitives_indeterminate"
    assert indeterminate["request_id"] == "transport"
    assert indeterminate["request_action"] == action
    assert indeterminate["outcome"] == "committed_but_unconfirmed"
    assert indeterminate["error"] == {
        "message": f"queue attempt {failed_attempt} failed"
    }
    assert all(item["action"] != "game_primitives_failed" for item in emitted)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "activate_game_primitive_adventure",
        "take_game_primitive_adventure_transition",
    ],
)
async def test_committed_adventure_indeterminate_transport_failure_is_fatal(
    action: str,
):
    scene, request, before = await _committed_action(action)
    handler = MagicMock(scene=scene)
    committed = None

    def fail_emit(_message: dict) -> None:
        nonlocal committed
        if committed is None:
            committed = copy.deepcopy(PrimitiveStore.for_scene(scene).root)
        raise RuntimeError("transport unavailable")

    handler.queue_put.side_effect = fail_emit

    with pytest.raises(CommittedResponseTransportError):
        await WorldStateManagerPlugin(handler).handle(request)

    assert handler.queue_put.call_count == 2
    assert committed != before
    assert PrimitiveStore.for_scene(scene).root == committed
