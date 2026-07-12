"""Shared rollback-safe transport mechanics for Game Primitives handlers."""

import copy
from collections.abc import Callable
from typing import TypeVar

import structlog

from talemate.game.primitives.authoring.editing import PrimitiveDraftEditingService
from talemate.game.primitives.constants import GAME_PRIMITIVES_KEY
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.store import PrimitiveStore

from .game_primitives_common_responses import (
    GamePrimitivesError,
    GamePrimitivesIndeterminateResponse,
    GamePrimitivesResponse,
)
from .game_primitives_draft_responses import (
    GamePrimitiveDraftResponse,
    GamePrimitiveDraftsResponse,
)
from .game_primitives_snapshot import build_game_primitives_snapshot

MutationResult = TypeVar("MutationResult")
log = structlog.get_logger("talemate.server.world_state_manager.game_primitives")


class CommittedResponseTransportError(RuntimeError):
    """A committed mutation could not emit either confirmation response."""


class GamePrimitivesHandlerBase:
    """Provide shared services, response emitters, and transaction semantics."""

    def _primitive_authoring(self) -> PrimitiveDraftEditingService:
        """Return a stateless draft editing service."""
        return PrimitiveDraftEditingService()

    def _primitive_revision(self) -> str:
        """Return the authoritative revision token for the current scene."""
        return PrimitiveStore.read_snapshot_for_scene(self.scene).revision_token()

    def _queue_draft(self, draft: PrimitiveDraft, request_id: str) -> None:
        """Queue one correlated draft response at the current revision."""
        response = GamePrimitiveDraftResponse(
            request_id=request_id, data=draft, revision=self._primitive_revision()
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    def _queue_drafts(self, drafts: list[PrimitiveDraft], request_id: str) -> None:
        """Queue correlated draft-list response data at the current revision."""
        response = GamePrimitiveDraftsResponse(
            request_id=request_id, data=drafts, revision=self._primitive_revision()
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    def _queue_snapshot(self, _result: object, request_id: str) -> None:
        """Queue a correlated authoritative snapshot response."""
        response = GamePrimitivesResponse(
            request_id=request_id, data=build_game_primitives_snapshot(self.scene)
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    def _capture_primitive_root(self) -> tuple[bool, object]:
        """Return root existence and a detached value suitable for rollback."""
        variables = self.scene.game_state.variables
        existed = GAME_PRIMITIVES_KEY in variables
        if existed:
            PrimitiveStore.read_snapshot_for_scene(self.scene)
        return existed, copy.deepcopy(variables.get(GAME_PRIMITIVES_KEY))

    def _restore_primitive_root(self, existed: bool, root: object) -> None:
        """Restore the exact captured primitive-root existence and value."""
        variables = self.scene.game_state.variables
        if existed:
            variables[GAME_PRIMITIVES_KEY] = root
        else:
            variables.pop(GAME_PRIMITIVES_KEY, None)

    async def _run_primitive_mutation(
        self,
        request_id: str,
        request_action: str,
        mutate: Callable[[], MutationResult],
        queue_success: Callable[[MutationResult, str], None],
        is_success: Callable[[MutationResult], bool] | None = None,
    ) -> None:
        """Finalize successes or restore the root before reporting rejection.

        Args:
            request_id: Correlation identifier for emitted responses.
            request_action: Action reported by an indeterminate response.
            mutate: Synchronous mutation returning typed response input.
            queue_success: Callback that queues the typed result response.
            is_success: Optional classifier for modeled domain results. False
                results are reported after rollback without being finalized.

        Raises:
            CommittedResponseTransportError: Neither post-commit response can be queued.

        Notes:
            Mutation, persistence, rollback, and pre-commit response failures
            propagate. A successful result is persisted; an exception or modeled
            rejection restores the exact captured primitive root. Post-commit
            transport failure does not roll back persisted state and emits an
            indeterminate response when possible.

        """
        existed, root = self._capture_primitive_root()
        try:
            result = mutate()
            committed = is_success is None or is_success(result)
            if committed:
                await self.finalize_operation_state()
            else:
                self._restore_primitive_root(existed, root)
        except Exception as exc:
            try:
                self._restore_primitive_root(existed, root)
            except Exception as rollback_exc:
                raise RuntimeError(
                    f"{exc}; primitive root rollback failed: {rollback_exc}"
                ) from rollback_exc
            raise
        try:
            queue_success(result, request_id)
            await self.signal_operation_done(signal_only=True, request_id=request_id)
        except Exception as exc:
            log.error(
                "game primitives response emission failed",
                request_id=request_id,
                exc_info=True,
            )
            if not committed:
                raise
            try:
                self._queue_primitive_indeterminate(request_id, request_action, exc)
            except Exception as indeterminate_exc:
                log.error(
                    "game primitives indeterminate response emission failed",
                    request_id=request_id,
                    exc_info=True,
                )
                raise CommittedResponseTransportError(
                    "committed Game Primitives mutation could not be confirmed"
                ) from indeterminate_exc

    def _queue_primitive_indeterminate(
        self, request_id: str, request_action: str, exc: Exception
    ) -> None:
        """Queue a correlated committed-but-unconfirmed response."""
        response = GamePrimitivesIndeterminateResponse(
            request_id=request_id,
            request_action=request_action,
            revision=self._primitive_revision(),
            error=GamePrimitivesError(message=str(exc)),
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))
