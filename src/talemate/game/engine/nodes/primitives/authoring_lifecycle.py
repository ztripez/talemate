"""Primitive draft lifecycle graph nodes."""

from talemate.game.engine.nodes.core import GraphState
from talemate.game.engine.nodes.primitives.authoring_base import (
    CreateDraftRequest,
    DraftOutputNode,
    authoring_service,
)
from talemate.game.engine.nodes.primitives.helpers import optional_input
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.authoring.schema import DraftRequest


@register("primitives/authoring/CreateDraft")
class CreateDraft(DraftOutputNode):
    """Create and publish an isolated primitive authoring draft."""

    def setup(self):
        """Register draft-creation request sockets."""
        self.add_input("draft_id", socket_type="str", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Create a validated draft in the active scene.

        Args:
            state: Current graph execution state.

        """
        request = CreateDraftRequest.model_validate(
            {"draft_id": optional_input(self, "draft_id", None)}
        )
        self.publish_result(authoring_service().create_draft, request.draft_id)


class DraftLifecycleNode(DraftOutputNode):
    """Target one existing draft through a validated ``draft_id`` input."""

    def setup(self):
        """Register lifecycle request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_draft_output()

    def request(self) -> DraftRequest:
        """Validate the lifecycle request.

        Returns:
            A request targeting the selected draft.

        Raises:
            pydantic.ValidationError: If the draft identifier is invalid.

        """
        return DraftRequest.model_validate({"draft_id": self.require_input("draft_id")})


@register("primitives/authoring/ValidateDraft")
class ValidateDraft(DraftLifecycleNode):
    """Validate and publish a draft without changing committed primitives."""

    async def run(self, state: GraphState):
        """Validate the selected draft.

        Args:
            state: Current graph execution state.

        """
        request = self.request()
        self.publish_result(authoring_service().validate_draft, request.draft_id)


@register("primitives/authoring/CommitDraft")
class CommitDraft(DraftLifecycleNode):
    """Atomically commit and publish a successfully validated primitive draft."""

    async def run(self, state: GraphState):
        """Commit the selected validated draft.

        Args:
            state: Current graph execution state.

        """
        request = self.request()
        self.publish_result(authoring_service().commit_draft, request.draft_id)
