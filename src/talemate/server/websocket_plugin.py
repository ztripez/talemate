"""Provide shared websocket plugin routing and operation lifecycle contracts."""

import structlog
from typing import TYPE_CHECKING, Callable, Literal
from talemate.emit import emit
from talemate.exceptions import GenerationCancelled
import traceback
import pydantic
import asyncio

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

__all__ = [
    "Plugin",
    "EmitStatusMessage",
    "OperationDoneEnvelope",
]

log = structlog.get_logger("talemate.server.visual")


class EmitStatusMessage(pydantic.BaseModel):
    """Describe a status event optionally mirrored into scene messages.

    Attributes:
        message: Human-readable status text.
        status: Status category passed to the event emitter.
        as_scene_message: Whether consumers should mirror the status into the scene.

    """

    message: str
    status: str = "success"
    as_scene_message: bool = False


class OperationDoneEnvelope(pydantic.BaseModel):
    """Validate a successful websocket operation completion envelope.

    Attributes:
        type: Router that completed the operation.
        action: Completion action, always ``"operation_done"``.
        data: Reserved JSON-compatible success payload, absent for failures.
        error: Structured failure detail, absent for successes.
        request_id: Optional request correlation identifier.

    """

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    type: str = pydantic.Field(min_length=1)
    action: Literal["operation_done"] = "operation_done"
    data: dict[str, pydantic.JsonValue] | None = None
    error: "OperationError | None" = None
    request_id: str | None = pydantic.Field(default=None, min_length=1)

    @pydantic.model_validator(mode="after")
    def validate_outcome(self) -> "OperationDoneEnvelope":
        """Require exactly one success payload or failure detail.

        Returns:
            The validated completion envelope.

        Raises:
            ValueError: If both or neither outcome fields are supplied.
        """
        if (self.data is None) == (self.error is None):
            raise ValueError("operation_done requires exactly one outcome")
        return self


class OperationError(pydantic.BaseModel):
    """Describe one failed websocket operation.

    Attributes:
        message: Non-empty human-readable failure detail.
    """

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)

    message: str = pydantic.Field(min_length=1)


class Plugin:
    """Provide common websocket routing, signaling, and finalization behavior."""

    router: str = "router"

    @property
    def scene(self) -> "Scene | None":
        """Return the scene currently owned by the websocket handler, if any."""
        return self.websocket_handler.scene

    def __init__(self, websocket_handler):
        """Attach a websocket handler and connect plugin event subscriptions."""
        self.websocket_handler = websocket_handler
        self.connect()

    def connect(self):
        """Connect plugin-specific subscriptions; base plugins perform no work."""
        pass

    def disconnect(self):
        """Disconnect plugin-specific subscriptions; base plugins perform no work."""
        pass

    @classmethod
    def register_sub_handler(cls, action: str, fn: Callable):
        """Register a class-level fallback handler for one exact action name."""
        if not hasattr(cls, "sub_handlers"):
            cls.sub_handlers = {}
        cls.sub_handlers[action] = fn

    @classmethod
    def clear_sub_handlers(cls):
        """Remove every class-level fallback action handler when initialized."""
        if hasattr(cls, "sub_handlers"):
            cls.sub_handlers = {}

    async def signal_operation_failed(self, message: str, emit_status: bool = True):
        """Queue an uncorrelated failed completion and optionally emit error status."""
        response = OperationDoneEnvelope(
            type=self.router, error=OperationError(message=message)
        )
        self.websocket_handler.queue_put(
            response.model_dump(mode="json", exclude_none=True)
        )
        if emit_status:
            emit("status", message=message, status="error")

    async def signal_operation_done(
        self,
        signal_only: bool = False,
        allow_auto_save: bool = True,
        emit_status_message: EmitStatusMessage | str | dict = None,
        request_id: str | None = None,
    ):
        """Finalize scene state, then queue completion and optional status.

        Args:
            signal_only: Skip autosave or dirty-state finalization when true.
            allow_auto_save: Permit automatic save during finalization when true.
            emit_status_message: Optional status model, text, or model input mapping.
            request_id: Optional correlation identifier. When supplied, the exact id
                is copied only into the queued ``operation_done`` envelope; omission
                preserves the legacy uncorrelated envelope shape.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If status mapping data is invalid.
            Exception: Any autosave exception from finalization.

        Side Effects:
            Unless ``signal_only`` is true, autosaves or marks the scene dirty before
            queuing ``operation_done`` and emitting optional success status.

        """
        if not signal_only:
            await self.finalize_operation_state(allow_auto_save=allow_auto_save)

        response = OperationDoneEnvelope(
            type=self.router, data={}, request_id=request_id
        )
        self.websocket_handler.queue_put(
            response.model_dump(mode="json", exclude_none=True)
        )

        if emit_status_message:
            if isinstance(emit_status_message, str):
                emit_status_message = EmitStatusMessage(message=emit_status_message)
            elif isinstance(emit_status_message, dict):
                emit_status_message = EmitStatusMessage(**emit_status_message)
            emit(
                "status",
                message=emit_status_message.message,
                status=emit_status_message.status,
                data={"as_scene_message": emit_status_message.as_scene_message},
            )


    async def finalize_operation_state(self, allow_auto_save: bool = True) -> None:
        """Autosave a successful mutation or mark its scene dirty without signaling.

        Args:
            allow_auto_save: Whether an auto-save-enabled scene may be saved. A false
                value forces dirty-state handling even when scene auto-save is on.

        Returns:
            None.

        Raises:
            Exception: Any exception raised by ``scene.save(auto=True)``. The
                exception propagates and no dirty-state fallback or success response
                is produced by this method.

        Side Effects:
            When scene auto-save and ``allow_auto_save`` are both true, awaits one
            automatic save. Otherwise sets ``scene.saved`` to false and emits scene
            status. The method itself never queues ``operation_done`` or any other
            websocket envelope.

        """
        if self.scene.auto_save and allow_auto_save:
            await self.scene.save(auto=True)
        else:
            self.scene.saved = False
            self.scene.emit_status()

    def create_task_done_callback(
        self,
        success_action: str,
        failure_action: str,
        error_log_message: str,
        failure_message_key: str = "message",
    ):
        """Create a callback function for async task completion.

        Args:
            success_action: Action name to send on successful completion
            failure_action: Action name to send on failure
            error_log_message: Log message to use when logging errors
            failure_message_key: Key name for the error message in the failure payload

        """

        def on_done(task: asyncio.Task):
            try:
                task.result()
                self.websocket_handler.queue_put(
                    {"type": self.router, "action": success_action}
                )
            except GenerationCancelled:
                log.warning(error_log_message, cancelled=True)
                self.websocket_handler.queue_put(
                    {
                        "type": self.router,
                        "action": failure_action,
                        failure_message_key: "Generation cancelled",
                    }
                )
            except Exception as e:
                log.error(error_log_message, error=traceback.format_exc())
                self.websocket_handler.queue_put(
                    {
                        "type": self.router,
                        "action": failure_action,
                        failure_message_key: str(e),
                    }
                )

        return on_done

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        """Complete error and cancellation paths for background-task handlers.

        Posts an operation_done envelope on the router for the cancel and error paths
        so the frontend's per-component busy state clears even when the
        handler bailed before reaching its trailing signal_operation_done().

        - Success: the handler's own signal_operation_done() already ran,
          nothing to do here.
        - Cancel (GenerationCancelled): post a bare operation_done envelope.
        - Error: post operation_done with an error envelope. set_loading
          already emitted the "Failed" status snackbar (set_error=True), so
          we skip the duplicate emit here.

        Implemented as direct queue_put rather than scheduling another task
        so we don't orphan a follow-up coroutine inside a done-callback.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            # Success — handler called signal_operation_done() itself.
            return
        if isinstance(exc, GenerationCancelled):
            response = OperationDoneEnvelope(type=self.router, data={})
            self.websocket_handler.queue_put(
                response.model_dump(mode="json", exclude_none=True)
            )
            return
        # Real exception — error envelope.
        response = OperationDoneEnvelope(
            type=self.router, error=OperationError(message=str(exc))
        )
        self.websocket_handler.queue_put(
            response.model_dump(mode="json", exclude_none=True)
        )

    async def handle(self, data: dict):
        """Route an action mapping to a handler and report synchronous failures."""
        action: str = data.get("action")
        log.info(f"{self.router} action", action=action)
        fn = getattr(self, f"handle_{action}", None)

        if self.scene and self.scene.cancel_requested:
            # Terrible way to reset the cancel_requested flag, but it's the only way to avoid double generation cancellation with the current implementation
            # TODO: Fix this
            self.scene.cancel_requested = False

        if fn is None:
            sub_handlers = getattr(self, "sub_handlers", {})
            sub_handler_fn = sub_handlers.get(action)
            if sub_handler_fn:
                log.info(f"{self.router} sub-handler", action=action)
                await sub_handler_fn(self, data)
                return

            return

        try:
            result = await fn(data)
        except Exception as e:
            action_name = data.get("action")
            log.error(
                "Error handling action",
                action=action_name,
                error=e,
                traceback=traceback.format_exc(),
            )
            await self.signal_operation_failed(f"Error during {action_name}: {e}")
            return

        # Handlers decorated with @background_task return a Task. Attach a
        # done-callback so cancellations and synchronous failures inside the
        # task body (e.g. pydantic validation, missing-character lookups)
        # still post an operation_done envelope on the router and the
        # frontend can clear any local busy state it set when sending the
        # request.
        if isinstance(result, asyncio.Task):
            result.add_done_callback(self._on_background_task_done)
