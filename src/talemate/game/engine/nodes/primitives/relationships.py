"""Graph node wrappers for Game Primitives relationship graph operations."""

from talemate.context import active_scene
from talemate.game.engine.nodes.core import UNRESOLVED, GraphState, Node
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.anchors import relationship_anchor
from talemate.game.primitives.relationships import (
    RelationshipAdjustNodeOutput,
    RelationshipGetNodeOutput,
    RelationshipGraph,
    RelationshipRelevantNodeOutput,
    RelationshipSetNodeOutput,
    RelationshipSummaryNodeOutput,
)

__all__ = ["Adjust", "Get", "RenderRelevant", "Set", "Summary"]


@register("primitives/relationships/Get")
class Get(Node):
    """Graph node that reads one directional relationship dimension.

    Inputs are ``source``, ``target``, ``dimension``, and optional ``default``.
    Output ``value`` contains the stored dimension value or explicit default.
    """

    def setup(self):
        """Declare relationship get inputs and value output."""
        self.add_input("source", socket_type="str")
        self.add_input("target", socket_type="str")
        self.add_input("dimension", socket_type="str")
        self.add_input("default", socket_type="float,int", optional=True)
        self.add_output("value", socket_type="float,int")

    async def run(self, state: GraphState):
        """Read a relationship dimension from the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``value`` to output sockets.

        Raises:
            PrimitiveError: If the dimension is absent and no default is set.
            pydantic.ValidationError: If persisted payload validation fails.
        """
        default_value = self.get_input_value("default")
        graph = RelationshipGraph()
        args = [
            active_scene.get(),
            self.require_input("source"),
            self.require_input("target"),
            self.require_input("dimension"),
        ]
        value = (
            graph.get(*args)
            if default_value is UNRESOLVED
            else graph.get(*args, default=default_value)
        )
        self.set_output_values(
            RelationshipGetNodeOutput(value=value).model_dump(mode="json")
        )


@register("primitives/relationships/Set")
class Set(Node):
    """Graph node that stores one bounded relationship dimension.

    Inputs are ``source``, ``target``, ``dimension``, ``value``, optional ``min``,
    and optional ``max``. Outputs expose stored value, anchor, and summary.
    """

    def setup(self):
        """Declare relationship set inputs and outputs."""
        self.add_input("source", socket_type="str")
        self.add_input("target", socket_type="str")
        self.add_input("dimension", socket_type="str")
        self.add_input("value", socket_type="float,int")
        self.add_input("min", socket_type="float,int", optional=True)
        self.add_input("max", socket_type="float,int", optional=True)
        self.add_output("value", socket_type="float,int")
        self.add_output("anchor", socket_type="str")
        self.add_output("summary", socket_type="str")

    async def run(self, state: GraphState):
        """Store a relationship dimension in the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``value``, ``anchor``, and ``summary``.

        Raises:
            ValueError: If required inputs, bounds, or values are invalid.
            pydantic.ValidationError: If request or output validation fails.
        """
        graph = RelationshipGraph()
        source = self.require_input("source")
        target = self.require_input("target")
        model = graph.set(
            active_scene.get(),
            source,
            target,
            self.require_input("dimension"),
            self.require_input("value"),
            min=_default_number(self.normalized_input_value("min"), -5),
            max=_default_number(self.normalized_input_value("max"), 5),
        )
        output = RelationshipSetNodeOutput(
            value=model.value,
            anchor=relationship_anchor(source, target).key(),
            summary=graph.summary(active_scene.get(), source, target),
        )
        self.set_output_values(output.model_dump(mode="json"))


@register("primitives/relationships/Adjust")
class Adjust(Node):
    """Graph node that applies a delta to one relationship dimension.

    Inputs are ``source``, ``target``, ``dimension``, ``by``, optional ``min``,
    and optional ``max``. Outputs expose current value, previous value, anchor,
    and summary after mutation.
    """

    def setup(self):
        """Declare relationship adjust inputs and outputs."""
        self.add_input("source", socket_type="str")
        self.add_input("target", socket_type="str")
        self.add_input("dimension", socket_type="str")
        self.add_input("by", socket_type="float,int")
        self.add_input("min", socket_type="float,int", optional=True)
        self.add_input("max", socket_type="float,int", optional=True)
        self.add_output("value", socket_type="float,int")
        self.add_output("previous", socket_type="float,int")
        self.add_output("anchor", socket_type="str")
        self.add_output("summary", socket_type="str")

    async def run(self, state: GraphState):
        """Adjust a relationship dimension in the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``value``, ``previous``, ``anchor``, and
            ``summary``.

        Raises:
            ValueError: If required inputs, bounds, or delta are invalid.
            pydantic.ValidationError: If request or output validation fails.
        """
        graph = RelationshipGraph()
        scene = active_scene.get()
        source = self.require_input("source")
        target = self.require_input("target")
        model, previous = graph.adjust(
            scene,
            source,
            target,
            self.require_input("dimension"),
            self.require_input("by"),
            min=_default_number(self.normalized_input_value("min"), -5),
            max=_default_number(self.normalized_input_value("max"), 5),
        )
        output = RelationshipAdjustNodeOutput(
            value=model.value,
            previous=previous,
            anchor=relationship_anchor(source, target).key(),
            summary=graph.summary(scene, source, target),
        )
        self.set_output_values(output.model_dump(mode="json"))


@register("primitives/relationships/Summary")
class Summary(Node):
    """Graph node that renders prompt-safe prose for one relationship edge.

    Inputs are ``source``, ``target``, and optional ``audience``. Output
    ``summary`` contains prose or an empty string.
    """

    def setup(self):
        """Declare summary inputs and output."""
        self.add_input("source", socket_type="str")
        self.add_input("target", socket_type="str")
        self.add_input("audience", socket_type="str", optional=True)
        self.add_output("summary", socket_type="str")

    async def run(self, state: GraphState):
        """Render relationship summary text from the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``summary`` to output sockets.

        Raises:
            pydantic.ValidationError: If persisted dimension payloads are invalid.
        """
        summary = RelationshipGraph().summary(
            active_scene.get(),
            self.require_input("source"),
            self.require_input("target"),
            audience=self.normalized_input_value("audience") or "prompt",
        )
        self.set_output_values(
            RelationshipSummaryNodeOutput(summary=summary).model_dump(mode="json")
        )


@register("primitives/relationships/RenderRelevant")
class RenderRelevant(Node):
    """Graph node that renders summaries for outgoing relationship edges.

    Inputs are ``character`` and optional ``other``. Output ``summaries`` contains
    prompt-safe summaries for matching outbound edges.
    """

    def setup(self):
        """Declare relevant relationship inputs and output."""
        self.add_input("character", socket_type="str")
        self.add_input("other", socket_type="str", optional=True)
        self.add_output("summaries", socket_type="list")

    async def run(self, state: GraphState):
        """Render relevant relationship summaries from the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``summaries`` to output sockets.

        Raises:
            pydantic.ValidationError: If persisted dimension payloads are invalid.
        """
        summaries = RelationshipGraph().relevant_for(
            active_scene.get(),
            self.require_input("character"),
            other=self.normalized_input_value("other"),
        )
        self.set_output_values(
            RelationshipRelevantNodeOutput(summaries=summaries).model_dump(mode="json")
        )


def _default_number(value, default):
    """Return default only for an absent optional numeric node input."""
    return default if value is None else value
