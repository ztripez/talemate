"""Graph node wrappers for Game Primitives attribute operations."""

import pydantic

from talemate.context import active_scene
from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.primitives.helpers import optional_input
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.attributes import (
    AttributeResolution,
    AttributeResolver,
    AttributeSource,
)
from talemate.game.primitives.render import Audience

__all__ = ["Get", "Render", "Resolve", "Set"]


class AttributeGetNodeOutput(pydantic.BaseModel):
    """Validated output emitted by the primitive attribute get node.

    Attributes:
        source: Stored attribute source model.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    source: AttributeSource


class AttributeSetNodeOutput(pydantic.BaseModel):
    """Validated output emitted by the primitive attribute set node.

    Attributes:
        ref: Canonical primitive attribute reference written to the store.
        source: Stored attribute source model.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    ref: str
    source: AttributeSource


class AttributeResolveNodeOutput(pydantic.BaseModel):
    """Validated output emitted by the primitive attribute resolve node.

    Attributes:
        value: JSON-compatible resolved attribute value.
        rendered: Optional prompt-safe text produced during resolution.
        result: Full resolution model.
        debug: JSON-compatible trace metadata.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    value: pydantic.JsonValue | None = None
    rendered: str | None = None
    result: AttributeResolution
    debug: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class AttributeRenderNodeOutput(pydantic.BaseModel):
    """Validated output emitted by the primitive attribute render node.

    Attributes:
        rendered: Prompt-safe rendered text for the requested audience.
        result: Full resolution model used to render the text.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    rendered: str
    result: AttributeResolution


@register("primitives/attributes/Get")
class Get(Node):
    """Graph node that reads one stored primitive attribute source.

    Input ``ref`` is an ``attributes`` primitive reference. Output ``source`` is
    the stored source payload.
    """

    def setup(self):
        """Declare the graph node contract for reading a primitive attribute source.

        Returns:
            None. The method registers a required ``ref`` string input and a
            ``source`` dictionary output on the node.
        """
        self.add_input("ref", socket_type="str")
        self.add_output("source", socket_type="dict")

    async def run(self, state: GraphState):
        """Read an attribute source from the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``source`` to output sockets.

        Raises:
            ValueError: If ``ref`` does not target primitive attributes.
            PrimitiveError: If the attribute source is missing.
            pydantic.ValidationError: If the stored source payload is invalid.
        """
        source = AttributeResolver().get(active_scene.get(), self.require_input("ref"))
        output = AttributeGetNodeOutput(source=source)
        self.set_output_values(output.model_dump(mode="json", exclude_none=True))


@register("primitives/attributes/Set")
class Set(Node):
    """Graph node that stores one primitive attribute source.

    Inputs are ``ref`` and ``source``. The source ``id`` may be omitted; when
    omitted the attribute id from ``ref`` is used.
    """

    def setup(self):
        """Declare the graph node contract for storing a primitive attribute source.

        Returns:
            None. The method registers required ``ref`` and ``source`` inputs plus
            ``ref`` and ``source`` outputs on the node.
        """
        self.add_input("ref", socket_type="str")
        self.add_input("source", socket_type="dict")
        self.add_output("ref", socket_type="str")
        self.add_output("source", socket_type="dict")

    async def run(self, state: GraphState):
        """Store an attribute source in the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``ref`` and ``source`` to output sockets.

        Raises:
            ValueError: If ``ref`` does not target primitive attributes.
            pydantic.ValidationError: If the source payload is invalid.
            PrimitiveStoreError: If the primitive store rejects the source payload.
        """
        ref = self.require_input("ref")
        source = AttributeResolver().set(
            active_scene.get(), ref, self.require_input("source")
        )
        output = AttributeSetNodeOutput(ref=ref, source=source)
        self.set_output_values(output.model_dump(mode="json", exclude_none=True))


@register("primitives/attributes/Resolve")
class Resolve(Node):
    """Graph node that resolves one primitive attribute source.

    Inputs are ``ref`` and optional ``context``. Outputs include convenience value
    fields and the full resolution payload.
    """

    def setup(self):
        """Declare the graph node contract for resolving a primitive attribute source.

        Returns:
            None. The method registers a required ``ref`` input, an optional
            ``context`` dictionary input, and ``value``, ``rendered``, ``result``,
            and ``debug`` outputs on the node.
        """
        self.add_input("ref", socket_type="str")
        self.add_input("context", socket_type="dict", optional=True)
        self.add_output("value", socket_type="any")
        self.add_output("rendered", socket_type="str")
        self.add_output("result", socket_type="dict")
        self.add_output("debug", socket_type="dict")

    async def run(self, state: GraphState):
        """Resolve an attribute source against the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes resolution fields to output sockets.

        Raises:
            ValueError: If ``ref`` does not target primitive attributes.
            PrimitiveError: If the attribute source or referenced primitive fails.
            pydantic.ValidationError: If input or stored payloads are invalid.
        """
        resolution = AttributeResolver().resolve(
            active_scene.get(),
            self.require_input("ref"),
            context=optional_input(self, "context", {}),
        )
        output = AttributeResolveNodeOutput(
            value=resolution.value,
            rendered=resolution.rendered,
            result=resolution,
            debug=resolution.debug,
        )
        self.set_output_values(output.model_dump(mode="json", exclude_none=True))


@register("primitives/attributes/Render")
class Render(Node):
    """Graph node that renders one primitive attribute for a requested audience.

    Inputs are ``ref``, optional ``audience`` with supported values ``prompt`` and
    ``memory``, and optional ``context``. Output ``rendered`` contains
    audience-visible text or an empty string when the render policy hides the
    attribute.
    """

    def setup(self):
        """Declare the graph node contract for rendering a primitive attribute source.

        Returns:
            None. The method registers a required ``ref`` input, optional
            ``audience`` and ``context`` inputs, and ``rendered`` and ``result``
            outputs on the node.
        """
        self.add_input("ref", socket_type="str")
        self.add_input("audience", socket_type="str", optional=True)
        self.add_input("context", socket_type="dict", optional=True)
        self.add_output("rendered", socket_type="str")
        self.add_output("result", socket_type="dict")

    async def run(self, state: GraphState):
        """Render an attribute source against the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``rendered`` and ``result`` to output sockets.

        Raises:
            ValueError: If ``ref`` does not target primitive attributes or the
                audience/render policy is unsupported.
            PrimitiveError: If the attribute source or referenced primitive fails.
            pydantic.ValidationError: If input or stored payloads are invalid.
        """
        resolver = AttributeResolver()
        scene = active_scene.get()
        ref = self.require_input("ref")
        context = optional_input(self, "context", {})
        audience = pydantic.TypeAdapter(Audience).validate_python(
            optional_input(self, "audience", "prompt")
        )
        source = resolver.get(scene, ref)
        resolution = resolver.resolve(scene, ref, context=context)
        rendered = resolver.render_resolution(source, resolution, audience=audience)
        output = AttributeRenderNodeOutput(rendered=rendered, result=resolution)
        self.set_output_values(output.model_dump(mode="json", exclude_none=True))
