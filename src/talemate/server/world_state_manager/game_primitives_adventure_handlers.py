"""Snapshot read and adventure runtime action handlers."""

from .game_primitives_adventure_requests import (
    ActivateGamePrimitiveAdventurePayload,
    GetGamePrimitiveEditorMetadataPayload,
    GetGamePrimitivesPayload,
    TakeGamePrimitiveAdventureTransitionPayload,
)
from .game_primitives_adventure_responses import (
    GamePrimitiveAdventureActivationResponse,
    GamePrimitiveAdventureTransitionResponse,
)
from .game_primitives_common_responses import GamePrimitiveEditorMetadataResponse
from .game_primitives_adventure_service import GamePrimitivesAdventureService
from .game_primitives_snapshot import (
    build_game_primitives_snapshot,
    get_game_primitive_editor_metadata,
)


class GamePrimitivesAdventureHandlers:
    """Handle snapshot reads and rollback-safe adventure runtime actions."""

    def _primitive_adventure(self) -> GamePrimitivesAdventureService:
        """Return a stateless adventure runtime service."""
        return GamePrimitivesAdventureService()

    async def handle_get_game_primitives(
        self, payload: GetGamePrimitivesPayload
    ) -> None:
        """Queue the authoritative snapshot requested by ``payload``.

        ``payload`` carries the response correlation ID. Snapshot construction and
        websocket transport failures propagate without mutating scene state.
        """
        self._queue_snapshot(None, payload.request_id)

    async def handle_get_game_primitive_editor_metadata(
        self, payload: GetGamePrimitiveEditorMetadataPayload
    ) -> None:
        """Queue canonical editor metadata without reading scene state."""
        response = GamePrimitiveEditorMetadataResponse(
            request_id=payload.request_id,
            data=get_game_primitive_editor_metadata(),
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    def _queue_adventure_activation(self, result, request_id: str) -> None:
        response = GamePrimitiveAdventureActivationResponse(
            request_id=request_id,
            result=result,
            data=build_game_primitives_snapshot(self.scene),
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    def _queue_adventure_transition(self, result, request_id: str) -> None:
        response = GamePrimitiveAdventureTransitionResponse(
            request_id=request_id,
            result=result,
            data=build_game_primitives_snapshot(self.scene),
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    async def handle_activate_game_primitive_adventure(
        self, payload: ActivateGamePrimitiveAdventurePayload
    ) -> None:
        """Activate an adventure and queue its result and resulting snapshot.

        ``payload`` identifies the adventure and carries the action and correlation
        ID. Successful activation persists state and queues the activation result and
        authoritative snapshot. Rejection or pre-commit failure restores the
        primitive root; post-commit transport failure preserves state and attempts to
        report an indeterminate result.
        """
        service = self._primitive_adventure()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.activate(self.scene, payload.adventure_id),
            self._queue_adventure_activation,
            lambda result: result.ok,
        )

    async def handle_take_game_primitive_adventure_transition(
        self, payload: TakeGamePrimitiveAdventureTransitionPayload
    ) -> None:
        """Take an adventure transition and queue the resulting snapshot.

        ``payload`` identifies the transition and carries the action and correlation
        ID. A successful transition persists state and queues its result and the
        authoritative snapshot. Rejection or pre-commit failure restores the
        primitive root; post-commit transport failure preserves state and attempts to
        report an indeterminate result.
        """
        service = self._primitive_adventure()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.take_transition(self.scene, payload.transition_id),
            self._queue_adventure_transition,
            lambda result: result.ok,
        )
