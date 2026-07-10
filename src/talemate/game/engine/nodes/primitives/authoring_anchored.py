"""Primitive authoring nodes for anchors and anchor-scoped state."""

from talemate.game.engine.nodes.core import UNRESOLVED, GraphState
from talemate.game.engine.nodes.primitives.authoring_base import (
    DraftOutputNode,
    authoring_service,
)
from talemate.game.engine.nodes.primitives.helpers import optional_input
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.authoring.schema import (
    CreateAnchorRequest,
    CreateAttributeSourceRequest,
    CreateClockRequest,
    CreateMeterRequest,
    CreateRelationshipRequest,
)


@register("primitives/authoring/CreateAnchor")
class CreateAnchor(DraftOutputNode):
    """Stage anchor tags and metadata in a primitive draft."""

    def setup(self):
        """Register anchor request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("kind", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("tags", socket_type="list", optional=True)
        self.add_input("meta", socket_type="dict", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated anchor in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateAnchorRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "kind": self.require_input("kind"),
                "id": self.require_input("id"),
                "tags": optional_input(self, "tags", []),
                "meta": optional_input(self, "meta", {}),
            }
        )
        self.publish_result(authoring_service().create_anchor, request)


@register("primitives/authoring/CreateMeter")
class CreateMeter(DraftOutputNode):
    """Stage a bounded meter under a primitive draft anchor."""

    def setup(self):
        """Register meter request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("anchor", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("label", socket_type="str", optional=True)
        self.add_input("min", socket_type="float,int")
        self.add_input("max", socket_type="float,int")
        self.add_input("value", socket_type="float,int")
        self.add_input("render_policy", socket_type="str", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated meter in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateMeterRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "anchor": self.require_input("anchor"),
                "id": self.require_input("id"),
                "label": optional_input(self, "label", None),
                "min": self.require_input("min"),
                "max": self.require_input("max"),
                "value": self.require_input("value"),
                "render_policy": optional_input(self, "render_policy", "hidden"),
            }
        )
        self.publish_result(authoring_service().create_meter, request)


@register("primitives/authoring/CreateClock")
class CreateClock(DraftOutputNode):
    """Stage a progress clock under a primitive draft anchor."""

    def setup(self):
        """Register clock request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("anchor", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("label", socket_type="str", optional=True)
        self.add_input("max", socket_type="int")
        self.add_input("value", socket_type="int", optional=True)
        self.add_input("render_policy", socket_type="str", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated clock in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateClockRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "anchor": self.require_input("anchor"),
                "id": self.require_input("id"),
                "label": optional_input(self, "label", None),
                "max": self.require_input("max"),
                "value": optional_input(self, "value", 0),
                "render_policy": optional_input(self, "render_policy", "summary"),
            }
        )
        self.publish_result(authoring_service().create_clock, request)


@register("primitives/authoring/CreateRelationshipModel")
class CreateRelationshipModel(DraftOutputNode):
    """Stage a directional relationship model in a draft."""

    def setup(self):
        """Register relationship request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("source", socket_type="str")
        self.add_input("target", socket_type="str")
        self.add_input("dimensions", socket_type="list")
        self.add_input("tags", socket_type="list", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated relationship model in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        request = CreateRelationshipRequest.model_validate(
            {
                "draft_id": self.require_input("draft_id"),
                "source": self.require_input("source"),
                "target": self.require_input("target"),
                "dimensions": self.require_input("dimensions"),
                "tags": optional_input(self, "tags", []),
            }
        )
        self.publish_result(authoring_service().create_relationship, request)


@register("primitives/authoring/CreateAttributeSource")
class CreateAttributeSource(DraftOutputNode):
    """Stage an attribute source under a primitive draft anchor."""

    def setup(self):
        """Register attribute-source request sockets."""
        self.add_input("draft_id", socket_type="str")
        self.add_input("anchor", socket_type="str")
        self.add_input("id", socket_type="str")
        self.add_input("source", socket_type="str")
        self.add_input("render_policy", socket_type="str")
        self.add_input("ref", socket_type="str", optional=True)
        self.add_input("value", socket_type="any", optional=True)
        self.add_input("options", socket_type="dict", optional=True)
        self.add_draft_output()

    async def run(self, state: GraphState):
        """Stage a validated attribute source in the active scene's draft.

        Args:
            state: Current graph execution state.

        """
        payload = {
            "draft_id": self.require_input("draft_id"),
            "anchor": self.require_input("anchor"),
            "id": self.require_input("id"),
            "source": self.require_input("source"),
            "render_policy": self.require_input("render_policy"),
            "ref": optional_input(self, "ref", None),
            "options": optional_input(self, "options", {}),
        }
        value = self.get_input_value("value")
        if value is not UNRESOLVED:
            payload["value"] = value
        request = CreateAttributeSourceRequest.model_validate(payload)
        self.publish_result(authoring_service().create_attribute_source, request)
