"""Thin routing shell composed from focused Game Primitives handler mixins."""

from typing import Any

import pydantic

from .game_primitives_adventure_handlers import GamePrimitivesAdventureHandlers
from .game_primitives_bundle_handlers import GamePrimitivesBundleHandlers
from .game_primitives_anchor_instance_handlers import (
    GamePrimitivesAnchorInstanceHandlers,
)
from .game_primitives_common_responses import (
    GamePrimitivesError,
    GamePrimitivesFailedResponse,
)
from .game_primitives_draft_definition_handlers import (
    GamePrimitivesDraftDefinitionHandlers,
)
from .game_primitives_handler_base import (
    CommittedResponseTransportError,
    GamePrimitivesHandlerBase,
)
from .game_primitives_relationship_handlers import GamePrimitivesRelationshipHandlers
from .game_primitives_request_contracts import GAME_PRIMITIVES_REQUEST_ADAPTER
from .game_primitives_transport import (
    GamePrimitivesRequestModel,
    GamePrimitivesRoutingEnvelope,
    GamePrimitivesRoutingProbe,
)


class GamePrimitivesMixin(
    GamePrimitivesBundleHandlers,
    GamePrimitivesAdventureHandlers,
    GamePrimitivesDraftDefinitionHandlers,
    GamePrimitivesAnchorInstanceHandlers,
    GamePrimitivesRelationshipHandlers,
    GamePrimitivesHandlerBase,
):
    """Strictly validate, route, and correlate Game Primitives requests.

    ``handle`` claims only actions containing ``game_primitive``. Other websocket
    messages are delegated to the next mixin. Claimed messages are validated by
    the canonical discriminated request union and dispatched to
    ``handle_<action>``; failures are correlated when an envelope is available.
    """

    def _queue_primitive_failure(
        self, request_id: str, request_action: str, exc: Exception
    ) -> None:
        response = GamePrimitivesFailedResponse(
            request_id=request_id,
            request_action=request_action,
            error=GamePrimitivesError(message=str(exc)),
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    async def handle(self, data: dict[str, Any]) -> None:
        """Route a websocket mapping or delegate an unrelated message.

        Args:
            data: Untrusted websocket payload mapping.

        Returns:
            None.

        Side Effects:
            Invokes a routed handler, queues a correlated failure, or delegates
            the payload to the next ``handle`` implementation.

        Raises:
            CommittedResponseTransportError: A committed mutation cannot emit
                either its success or indeterminate response.

        """
        try:
            probe = GamePrimitivesRoutingProbe.model_validate(data)
        except pydantic.ValidationError:
            await super().handle(data)
            return
        if "game_primitive" not in probe.action:
            await super().handle(data)
            return
        envelope = None
        try:
            envelope = GamePrimitivesRoutingEnvelope.model_validate(data)
            payload = GAME_PRIMITIVES_REQUEST_ADAPTER.validate_python(data, strict=True)
            await self._dispatch_game_primitives_request(payload)
        except CommittedResponseTransportError:
            raise
        except Exception as exc:
            self._queue_primitive_failure(
                envelope.request_id if envelope else "unmatched-request",
                envelope.action if envelope else probe.action,
                exc,
            )

    async def _dispatch_game_primitives_request(
        self, payload: GamePrimitivesRequestModel
    ) -> None:
        """Invoke the handler named by a validated request action.

        Args:
            payload: Strictly validated Game Primitives request.

        Returns:
            None.

        Side Effects:
            Executes the selected handler and its documented persistence and
            websocket effects.

        Raises:
            AttributeError: No handler exists for the validated action.
            Exception: The selected handler fails.

        """
        handler = getattr(self, f"handle_{payload.action}")
        await handler(payload)


__all__ = ["CommittedResponseTransportError", "GamePrimitivesMixin"]
