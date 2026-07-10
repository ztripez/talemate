"""Shared contracts for primitive authoring graph nodes."""

from collections.abc import Callable
from typing import Any

import pydantic

from talemate.context import active_scene
from talemate.game.engine.nodes.core import Node
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.schema import PrimitiveDraft


class CreateDraftRequest(pydantic.BaseModel):
    """Request creation of an optionally named primitive draft.

    Attributes:
        draft_id: Optional non-empty draft identifier. When omitted, the authoring
            service generates an identifier.

    Invariants:
        A supplied identifier is stripped of surrounding whitespace and cannot be
        empty. Unknown request fields are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    draft_id: str | None = pydantic.Field(default=None, min_length=1)


class DraftNodeOutput(pydantic.BaseModel):
    """Validate the draft output shared by primitive authoring nodes.

    Attributes:
        draft: Canonical primitive draft returned by an authoring operation.

    Invariants:
        The nested draft satisfies ``PrimitiveDraft`` validation, non-finite
        numeric values are rejected, and no unknown output fields are accepted.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    draft: PrimitiveDraft


class DraftOutputNode(Node):
    """Publish validated primitive authoring drafts through a shared contract.

    Subclasses register operation-specific inputs and a dictionary-valued ``draft``
    output. Their run methods validate inputs, apply one operation to the active
    scene, and publish the resulting draft as JSON-compatible data. Primitive store,
    authoring, and Pydantic validation errors propagate to the node runner.
    """

    def add_draft_output(self) -> None:
        """Register the dictionary-valued ``draft`` output socket."""
        self.add_output("draft", socket_type="dict")

    def publish_result(
        self,
        operation: Callable[[Any, Any], PrimitiveDraft],
        request: Any,
    ) -> None:
        """Run an authoring operation and publish its validated draft result.

        Args:
            operation: Service operation accepting the active scene and request.
            request: Request value passed unchanged to ``operation``.

        Raises:
            ValueError: If the operation rejects the request.
            pydantic.ValidationError: If the result is not a valid draft.

        """
        draft = operation(active_scene.get(), request)
        output = DraftNodeOutput(draft=draft)
        self.set_output_values(output.model_dump(mode="json"))


def authoring_service() -> PrimitiveAuthoringService:
    """Create an isolated primitive authoring service.

    Returns:
        A new primitive authoring service.

    """
    return PrimitiveAuthoringService()
