"""Expose development-only prompt, scene-state, and diagnostic websocket actions."""

import json

import pydantic
import structlog
from talemate.instance import get_client
from talemate.client.base import ClientBase
from talemate.path import LOGS_DIR
from talemate.scene.state_editor import SceneStateEditor
from talemate.scene.schema import SceneState
from talemate.server.websocket_plugin import Plugin
from talemate.emit import emit
from typing import Any

log = structlog.get_logger("talemate.server.devtools")


class TestPromptPayload(pydantic.BaseModel):
    """Validate a direct prompt test and its generation configuration."""

    prompt: str
    generation_parameters: dict
    client_name: str
    kind: str


class SetSceneStatePayload(pydantic.BaseModel):
    """Validate a complete replacement scene-state model."""

    state: SceneState


class GameStateVariablesPayload(pydantic.BaseModel):
    """Validate replacement JSON-compatible game-state variables."""

    variables: dict[str, Any] = {}


class GameStateWatchPathsPayload(pydantic.BaseModel):
    """Validate game-state paths selected for frontend observation."""

    paths: list[str] = []


class DumpPromptLogPayload(pydantic.BaseModel):
    """Validate prompt records requested for diagnostic persistence."""

    prompts: list[dict[str, Any]] = []


def ensure_number(v):
    """Convert a numeric string to ``int`` or ``float`` and preserve other values."""
    if isinstance(v, str):
        if v.isdigit():
            return int(v)
        try:
            return float(v)
        except ValueError:
            return v
    return v


class DevToolsPlugin(Plugin):
    """Serve development diagnostics through the ``devtools`` websocket router."""

    router = "devtools"

    async def handle_test_prompt(self, data):
        """Validate a prompt test, invoke its client, and queue the full response."""
        payload = TestPromptPayload(**data)
        client: ClientBase = get_client(payload.client_name)

        log.info(
            "Testing prompt",
            payload={
                k: ensure_number(v)
                for k, v in payload.generation_parameters.items()
                if k != "prompt"
            },
        )

        response = await client.generate(
            payload.prompt,
            payload.generation_parameters,
            payload.kind,
        )

        self.websocket_handler.queue_put(
            {
                "type": "devtools",
                "action": "test_prompt_response",
                "data": {
                    "prompt": payload.prompt,
                    "generation_parameters": payload.generation_parameters,
                    "client_name": payload.client_name,
                    "kind": payload.kind,
                    "response": response,
                    "reasoning": client.reasoning_response,
                },
            }
        )

    async def handle_get_scene_state(self, data):
        """Queue the active scene's editable state representation."""
        scene = self.scene
        editor = SceneStateEditor(scene)
        state = editor.dump()

        self.websocket_handler.queue_put(
            {"type": "devtools", "action": "scene_state", "data": state}
        )

    async def handle_update_scene_state(self, data):
        """Validate and replace editable scene state, reporting explicit failure."""
        scene = self.scene
        editor = SceneStateEditor(scene)

        try:
            payload = SetSceneStatePayload(**data)
            editor.load(payload.model_dump().get("state"))
        except Exception as exc:
            self.websocket_handler.queue_put(
                {
                    "type": "devtools",
                    "action": "scene_state_update_failed",
                    "error": {"message": str(exc)},
                }
            )
            await self.signal_operation_failed(str(exc))
            return

        emit("status", message="Scene state updated", status="success")

        self.websocket_handler.queue_put(
            {"type": "devtools", "action": "scene_state_updated", "data": editor.dump()}
        )

        await self.signal_operation_done()

    async def handle_get_game_state(self, data):
        """Queue active-scene game-state variables or report a missing scene."""
        scene = self.scene
        if not scene:
            await self.signal_operation_failed("No active scene")
            return

        game_state = scene.game_state.model_dump()
        variables = game_state.get("variables", {})

        self.websocket_handler.queue_put(
            {
                "type": "devtools",
                "action": "game_state",
                "data": {"variables": variables},
            }
        )

    async def handle_update_game_state(self, data):
        """Validate and replace game-state variables, then reload dependent pins."""
        scene = self.scene
        if not scene:
            await self.signal_operation_failed("No active scene")
            return

        try:
            payload = GameStateVariablesPayload(**data)
        except Exception as exc:
            await self.signal_operation_failed(str(exc))
            return

        # Replace variables with provided structure (must be JSON-serializable)
        scene.game_state.variables = payload.variables or {}

        # Re-evaluate gamestate-controlled pins
        await scene.load_active_pins()

        emit("status", message="Game state updated", status="success")

        self.websocket_handler.queue_put(
            {
                "type": "devtools",
                "action": "game_state_updated",
                "data": {"variables": scene.game_state.variables},
            }
        )

        await self.signal_operation_done()

    async def handle_get_game_state_watch_paths(self, data):
        """Queue paths currently selected for game-state observation."""
        scene = self.scene
        if not scene:
            await self.signal_operation_failed("No active scene")
            return

        self.websocket_handler.queue_put(
            {
                "type": "devtools",
                "action": "game_state_watch_paths",
                "data": {"paths": scene.game_state_watch_paths},
            }
        )

    async def handle_set_game_state_watch_paths(self, data):
        """Validate, normalize, and persist game-state observation paths."""
        scene = self.scene
        if not scene:
            await self.signal_operation_failed("No active scene")
            return

        try:
            payload = GameStateWatchPathsPayload(**data)
        except Exception as exc:
            await self.signal_operation_failed(str(exc))
            return

        # Sanitize: remove duplicates and empty strings, keep unique sorted list
        sanitized_paths = sorted(list(set(filter(None, payload.paths))))

        scene.game_state_watch_paths = sanitized_paths

        # Emit scene status so TalemateApp.vue gets the updated watch paths
        scene.emit_status()

        emit("status", message="Game state watch paths updated", status="success")

        self.websocket_handler.queue_put(
            {
                "type": "devtools",
                "action": "game_state_watch_paths_updated",
                "data": {"paths": scene.game_state_watch_paths},
            }
        )

        await self.signal_operation_done()

    async def handle_dump_prompt_log(self, data):
        """Validate and write prompt diagnostics to the configured logs directory."""
        try:
            payload = DumpPromptLogPayload(**data)
        except Exception as exc:
            await self.signal_operation_failed(str(exc))
            return

        if not payload.prompts:
            emit("status", message="No prompts to dump", status="warning")
            return

        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = LOGS_DIR / "prompt_log.json"

        try:
            output_path.write_text(json.dumps(payload.prompts, indent=2, default=str))
        except Exception as exc:
            await self.signal_operation_failed(f"Failed to write prompt log: {exc}")
            return

        log.info("Prompt log dumped", path=str(output_path), count=len(payload.prompts))
        emit(
            "status",
            message=f"Prompt log dumped ({len(payload.prompts)} entries) to {output_path.name}",
            status="success",
        )
