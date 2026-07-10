"""Primitive authoring nodes for reusable definitions."""

from talemate.game.engine.nodes.core import GraphState
from talemate.game.engine.nodes.primitives.authoring_base import (
    DraftOutputNode,
    authoring_service,
)
from talemate.game.engine.nodes.primitives.helpers import optional_input
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.authoring.schema import (
    CreateDeckRequest,
    CreateModifierRequest,
    CreateRollTableRequest,
)


@register("primitives/authoring/CreateDeck")
class CreateDeck(DraftOutputNode):
    """Stage a validated deck definition in a primitive draft."""

    def setup(self):
        """Register deck request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("name", socket_type="str")
        self.add_input("mode", socket_type="str")
        self.add_input("cards", socket_type="list")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("instance_id", socket_type="str", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated deck definition in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateDeckRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "id": self.require_input("id"),
                "name": self.require_input("name"),
                "mode": self.require_input("mode"),
                "cards": self.require_input("cards"),
                "anchor": optional_input(self, "anchor", None),
                "instance_id": optional_input(self, "instance_id", None),
            }
        )
        self.publish_result(authoring_service().create_deck, request)


@register("primitives/authoring/CreateRollTable")
class CreateRollTable(DraftOutputNode):
    """Stage a validated roll-table definition in a primitive draft."""

    def setup(self):
        """Register roll-table request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("name", socket_type="str")
        self.add_input("mode", socket_type="str")
        self.add_input("rows", socket_type="list")
        self.add_input("dice", socket_type="str", optional=True)
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("instance_id", socket_type="str", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated roll-table definition in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateRollTableRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "id": self.require_input("id"),
                "name": self.require_input("name"),
                "mode": self.require_input("mode"),
                "rows": self.require_input("rows"),
                "dice": optional_input(self, "dice", None),
                "anchor": optional_input(self, "anchor", None),
                "instance_id": optional_input(self, "instance_id", None),
            }
        )
        self.publish_result(authoring_service().create_roll_table, request)


@register("primitives/authoring/CreateModifier")
class CreateModifier(DraftOutputNode):
    """Stage a validated roll modifier in a primitive draft."""

    def setup(self):
        """Register modifier request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("label", socket_type="str", optional=True)
        self.add_input("applies_to", socket_type="str")
        self.add_input("when", socket_type="list", optional=True)
        self.add_input("operation", socket_type="dict")
        self.add_input("explanation", socket_type="str", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated roll modifier in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateModifierRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "id": self.require_input("id"),
                "label": optional_input(self, "label", None),
                "applies_to": self.require_input("applies_to"),
                "when": optional_input(self, "when", []),
                "operation": self.require_input("operation"),
                "explanation": optional_input(self, "explanation", None),
            }
        )
        self.publish_result(authoring_service().create_modifier, request)
