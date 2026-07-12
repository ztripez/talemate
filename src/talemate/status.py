"""Emit lifecycle status for foreground and background asynchronous operations."""

import asyncio
import structlog
from functools import wraps

from talemate.emit import emit
from talemate.exceptions import GenerationCancelled
from talemate.context import handle_generation_cancelled

__all__ = [
    "set_loading",
    "background_task",
    "LoadingStatus",
]

log = structlog.get_logger("talemate.status")


class set_loading:
    """Decorate a coroutine with busy, success, cancellation, and failure statuses."""

    def __init__(
        self,
        message,
        set_busy: bool = True,
        set_success: bool = False,
        set_error: bool = False,
        cancellable: bool = False,
        as_async: bool = False,
    ):
        """Configure status text, terminal states, cancellation, and task wrapping."""
        self.message = message
        self.set_busy = set_busy
        self.set_success = set_success
        self.set_error = set_error
        self.cancellable = cancellable
        self.as_async = as_async

    def __call__(self, fn):
        """Wrap an asynchronous callable with the configured status lifecycle."""
        async def wrapper(*args, **kwargs):
            if self.set_busy:
                status_data = {}
                if self.cancellable:
                    status_data["cancellable"] = True
                emit("status", message=self.message, status="busy", data=status_data)
            try:
                result = await fn(*args, **kwargs)
                if self.set_success:
                    emit("status", message=self.message, status="success")
                else:
                    emit("status", message="", status="idle")
                return result
            except GenerationCancelled as e:
                log.warning("Generation cancelled", args=args, kwargs=kwargs)
                if self.set_error:
                    emit("status", message=f"{self.message}: Cancelled", status="idle")
                else:
                    # Always clear the busy status on cancel. Without this the
                    # frontend's notificatioonBusy lock (driven by status=='busy')
                    # never resolves and the scene input stays disabled.
                    emit("status", message="", status="idle")
                handle_generation_cancelled(e)
                # Re-raise so callers (notably the @background_task decorator's
                # done-callback in Plugin.handle) can post a router-level
                # operation_done envelope and clear per-component busy state.
                raise
            except Exception as e:
                log.error("Error in set_loading wrapper", error=e)
                if self.set_error:
                    emit("status", message=f"{self.message}: Failed", status="error")
                else:
                    emit("status", message="", status="idle")
                raise e

        # if as_async we want to wrap the function in a coroutine
        # that adds a task to the event loop and returns the task

        if self.as_async:

            async def async_wrapper(*args, **kwargs):
                task = asyncio.create_task(wrapper(*args, **kwargs))
                # Mark exceptions as retrieved so cancellations / errors that
                # propagate out of the wrapper don't surface as
                # "Task exception was never retrieved" warnings.
                task.add_done_callback(_consume_task_exception)
                return task

            return async_wrapper

        return wrapper


def _consume_task_exception(task: asyncio.Task) -> None:
    """Mark a background task exception as retrieved.

    Suppresses the "Task exception was never retrieved" warning at GC time. The
    exception itself is already logged by the set_loading wrapper.
    """
    if task.cancelled():
        return
    # Calling exception() is enough to mark it retrieved; the return value
    # is intentionally discarded.
    task.exception()


def background_task(
    message: str,
    *,
    cancellable: bool = True,
    set_success: bool = False,
    set_error: bool = True,
):
    """Schedule a coroutine as a background task with status emissions.

    The wrapped function returns immediately with the task object — calling
    code can ignore it. This is what frees the websocket receive loop so
    follow-up messages (e.g. the cancel/retry/ignore dialog response from
    the LLM client) can be dispatched while the work is still running.

    The frontend still observes a busy snackbar (with a cancel button when
    cancellable=True) for the duration of the task; "background" here refers
    to the backend handler returning before the work completes, not to the
    UX being free to continue.
    """

    def decorator(fn):
        wrapped = set_loading(
            message,
            cancellable=cancellable,
            set_success=set_success,
            set_error=set_error,
        )(fn)

        @wraps(fn)
        async def outer(*args, **kwargs):
            task = asyncio.create_task(wrapped(*args, **kwargs))
            task.add_done_callback(_consume_task_exception)
            return task

        return outer

    return decorator


class LoadingStatus:
    """Emit progress statuses with an optional bounded step counter."""

    def __init__(self, max_steps: int | None = None, cancellable: bool = False):
        """Configure the optional total step count and cancellation indicator."""
        self.max_steps = max_steps
        self.current_step = 0
        self.cancellable = cancellable

    def __call__(self, message: str):
        """Advance one step and emit a busy status with the supplied message."""
        self.current_step += 1

        if self.max_steps is None:
            counter = ""
        else:
            counter = f" [{self.current_step}/{self.max_steps}]"

        emit(
            "status",
            message=f"{message}{counter}",
            status="busy",
            data={
                "cancellable": self.cancellable,
            },
        )

    def done(self, message: str = "", status: str = "idle"):
        """Emit a terminal status after at least one progress step."""
        if self.current_step == 0:
            return

        emit(
            "status",
            message=message,
            status=status,
        )
