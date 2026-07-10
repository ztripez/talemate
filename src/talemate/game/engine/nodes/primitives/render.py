"""Graph node wrappers for prompt-safe Game Primitives context rendering."""

from __future__ import annotations

from typing import ClassVar

import pydantic

from talemate.agents.base import DynamicInstruction
from talemate.character import Character
from talemate.context import active_scene
from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.primitives.helpers import optional_input
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.context import (
    ContextAudience,
    PrimitiveContextDebug,
    PrimitiveContextRenderer,
    PrimitiveRenderedContext,
)
from talemate.game.primitives.store import PrimitiveStore

__all__ = [
    "InjectConversationContext",
    "InjectCreatorContext",
    "InjectNarratorContext",
    "InitializeStore",
    "RenderRelevantContext",
]


class RenderRelevantContextOutput(pydantic.BaseModel):
    """Validated graph output for rendered primitive context.

    Attributes:
        title: Stable dynamic-instruction title.
        content: Prompt-safe rendered context content.
        instruction: Dynamic instruction wrapping non-empty content, or ``None``.
        anchors: Canonical anchors that contributed rendered content.
        refs: Canonical attribute refs that contributed rendered content.
        debug: Optional safe relevance diagnostics.
    """

    model_config = pydantic.ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    title: str
    content: str
    instruction: DynamicInstruction | None = None
    anchors: list[str] = pydantic.Field(default_factory=list)
    refs: list[str] = pydantic.Field(default_factory=list)
    debug: PrimitiveContextDebug | None = None


class InjectionOutput(pydantic.BaseModel):
    """Validated output for a dynamic-instruction injection node.

    Attributes:
        injected: Whether a non-empty instruction was appended to the event.
        instruction: Appended dynamic instruction, or ``None`` when context was empty.
    """

    model_config = pydantic.ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    injected: bool
    instruction: DynamicInstruction | None = None


class InitializeStoreOutput(pydantic.BaseModel):
    """Validated primitive-store initialization output.

    Attributes:
        initialized: Whether primitive-store initialization completed successfully.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    initialized: bool


class ConversationInjectionPayload(pydantic.BaseModel):
    """Validate conversation emission fields used for primitive context injection.

    Attributes:
        character: Speaking character used to select relevant primitive anchors.
        dynamic_instructions: Mutable instruction list receiving rendered context.
    """

    model_config = pydantic.ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    character: Character
    dynamic_instructions: list[DynamicInstruction]


class NarratorInjectionPayload(pydantic.BaseModel):
    """Validate narrator emission fields used for primitive context injection.

    Attributes:
        dynamic_instructions: Mutable instruction list receiving scene-wide rendered
            primitive context.
    """

    model_config = pydantic.ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    dynamic_instructions: list[DynamicInstruction]


class CreatorInjectionPayload(pydantic.BaseModel):
    """Validate creator emission fields used for primitive context injection.

    Attributes:
        character: Focused character, or ``None`` when no primitive context should
            be injected.
        dynamic_instructions: Mutable instruction list receiving rendered context.
    """

    model_config = pydantic.ConfigDict(
        from_attributes=True, arbitrary_types_allowed=True
    )

    character: Character | None = None
    dynamic_instructions: list[DynamicInstruction]


@register("primitives/render/InitializeStore")
class InitializeStore(Node):
    """Initialize and validate the active scene's Game Primitives store."""

    def setup(self):
        """Declare the store initialization result output.

        Returns:
            None. The method registers an optional event trigger input and an
            ``initialized`` Boolean output.
        """
        self.add_input("event", socket_type="event", optional=True)
        self.add_output("initialized", socket_type="bool")

    async def run(self, state: GraphState):
        """Initialize the active scene's primitive store.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``initialized=True`` after validation succeeds.

        Raises:
            PrimitiveStoreError: If existing primitive state is invalid.
        """
        PrimitiveStore.for_scene(active_scene.get())
        self.set_output_values(InitializeStoreOutput(initialized=True))


@register("primitives/render/RenderRelevantContext")
class RenderRelevantContext(Node):
    """Render prompt-safe primitive context for a requested agent audience.

    Inputs are ``audience``, optional ``character``, optional ``target_character``,
    and optional ``include_debug``. Outputs contain rendered context metadata and a
    dynamic instruction when content is non-empty.
    """

    def setup(self):
        """Declare relevant-context render inputs and outputs.

        Returns:
            None. The method registers render request inputs and context outputs.
        """
        self.add_input("audience", socket_type="str")
        self.add_input("character", socket_type="str", optional=True)
        self.add_input("target_character", socket_type="str", optional=True)
        self.add_input("include_debug", socket_type="bool", optional=True)
        self.add_output("title", socket_type="str")
        self.add_output("content", socket_type="str")
        self.add_output("instruction", socket_type="dynamic_instruction")
        self.add_output("anchors", socket_type="list")
        self.add_output("refs", socket_type="list")
        self.add_output("debug", socket_type="any")

    async def run(self, state: GraphState):
        """Render relevant primitive context from the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes rendered context fields to output sockets.

        Raises:
            pydantic.ValidationError: If node inputs or persisted payloads are invalid.
            PrimitiveError: If relevant primitive state cannot be resolved safely.
            ValueError: If a visible primitive value cannot be rendered safely.
        """
        result = PrimitiveContextRenderer().render_relevant_context(
            active_scene.get(),
            audience=self.require_input("audience"),
            character=optional_input(self, "character", None),
            target_character=optional_input(self, "target_character", None),
            include_debug=optional_input(self, "include_debug", False),
        )
        self.set_output_values(_context_output(result))


class _InjectContext(Node):
    """Base node for appending rendered primitive context to an agent emission."""

    payload_type: ClassVar[type[pydantic.BaseModel]]
    audience: ClassVar[ContextAudience]

    def setup(self):
        """Declare event input and injection result outputs."""
        self.add_input("event", socket_type="event")
        self.add_output("injected", socket_type="bool")
        self.add_output("instruction", socket_type="dynamic_instruction")

    def _render(self, payload: pydantic.BaseModel) -> PrimitiveRenderedContext:
        """Render context for a validated event payload."""
        return PrimitiveContextRenderer().render_relevant_context(
            active_scene.get(), audience=self.audience
        )

    async def run(self, state: GraphState):
        """Append a non-empty primitive instruction to an agent emission.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node mutates ``event.dynamic_instructions`` and writes result
            fields to output sockets.

        Raises:
            pydantic.ValidationError: If the emission boundary or persisted
                primitive context is invalid.
            PrimitiveError: If relevant primitive state cannot be resolved safely.
            ValueError: If a visible primitive value cannot be rendered safely.
        """
        event = self.require_input("event")
        payload = self.payload_type.model_validate(event)
        output = _inject_result(event, self._render(payload))
        self.set_output_values(output)


@register("primitives/render/InjectConversationContext")
class InjectConversationContext(_InjectContext):
    """Append prompt-safe primitive context relevant to a speaking character.

    The node validates a conversation injection event and appends one dynamic
    instruction when relevant content exists. Outputs report whether injection
    occurred and expose the appended instruction, or ``None`` for empty context.
    """

    payload_type: ClassVar[type[pydantic.BaseModel]] = ConversationInjectionPayload
    audience: ClassVar[ContextAudience] = "conversation"

    def _render(
        self, payload: ConversationInjectionPayload
    ) -> PrimitiveRenderedContext:
        """Render conversation context focused on the speaking character."""
        return PrimitiveContextRenderer().render_relevant_context(
            active_scene.get(), audience=self.audience, character=payload.character.name
        )


@register("primitives/render/InjectNarratorContext")
class InjectNarratorContext(_InjectContext):
    """Append prompt-safe scene-wide primitive context to a narrator emission.

    The node validates a narrator injection event and appends one dynamic instruction
    when relevant content exists. Outputs report whether injection occurred and expose
    the appended instruction, or ``None`` for empty context.
    """

    payload_type: ClassVar[type[pydantic.BaseModel]] = NarratorInjectionPayload
    audience: ClassVar[ContextAudience] = "narrator"


@register("primitives/render/InjectCreatorContext")
class InjectCreatorContext(_InjectContext):
    """Append prompt-safe primitive context for a creator-focused character.

    The node validates a creator injection event. A dynamic instruction is appended
    only when the event identifies a character and relevant content exists. Outputs
    report whether injection occurred and expose the appended instruction, or
    ``None`` when no instruction was added.
    """

    payload_type: ClassVar[type[pydantic.BaseModel]] = CreatorInjectionPayload
    audience: ClassVar[ContextAudience] = "creator"

    def _render(self, payload: CreatorInjectionPayload) -> PrimitiveRenderedContext:
        """Render creator context only when the emission names a character."""
        if payload.character is None:
            return PrimitiveRenderedContext(content="")
        return PrimitiveContextRenderer().render_relevant_context(
            active_scene.get(), audience=self.audience, character=payload.character.name
        )


def _context_output(result: PrimitiveRenderedContext) -> RenderRelevantContextOutput:
    """Build graph output from rendered primitive context."""
    instruction = (
        DynamicInstruction(title=result.title, content=result.content)
        if result.content.strip()
        else None
    )
    return RenderRelevantContextOutput(
        title=result.title,
        content=result.content,
        instruction=instruction,
        anchors=result.anchors,
        refs=result.refs,
        debug=result.debug,
    )


def _inject_result(event, result: PrimitiveRenderedContext) -> InjectionOutput:
    """Append rendered context to an event and return validated injection output."""
    output = _context_output(result)
    if output.instruction is None:
        return InjectionOutput(injected=False)
    event.dynamic_instructions.append(output.instruction)
    return InjectionOutput(injected=True, instruction=output.instruction)
