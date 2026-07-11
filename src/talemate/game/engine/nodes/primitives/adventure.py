"""Register executable graph nodes for Talemate adventure operations."""

import pydantic
from typing import Literal

from talemate.context import active_scene
from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.primitives.helpers import optional_input
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.adventure import AdventureEngine

__all__ = [
    "CanTakeTransition",
    "GetCurrentScene",
    "ListTransitions",
    "RenderCurrentSceneContext",
    "TakeTransition",
]


class TransitionIdInput(pydantic.BaseModel):
    """Validated graph input identifying one adventure transition."""

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)
    transition_id: str = pydantic.Field(min_length=1)


class TakeTransitionInput(TransitionIdInput):
    """Validated graph input for taking an adventure transition."""

    render_intro: pydantic.StrictBool = True


class RenderContextInput(pydantic.BaseModel):
    """Validated graph input selecting an adventure context audience."""

    model_config = pydantic.ConfigDict(extra="forbid")
    audience: Literal["prompt", "summary"] = "prompt"


@register("primitives/adventure/GetCurrentScene")
class GetCurrentScene(Node):
    """Return the active story-scene definition."""

    def setup(self):
        """Declare current-scene outputs."""
        self.add_output("scene", socket_type="dict")

    async def run(self, state: GraphState):
        """Read and serialize the active story scene."""
        current = AdventureEngine().get_current(active_scene.get())
        self.set_output_values(
            {"scene": current.model_dump(mode="json") if current is not None else {}}
        )


@register("primitives/adventure/ListTransitions")
class ListTransitions(Node):
    """List outgoing transition availability for the active story scene."""

    def setup(self):
        """Declare transition-list output."""
        self.add_output("transitions", socket_type="list")

    async def run(self, state: GraphState):
        """Evaluate and serialize outgoing transitions."""
        transitions = AdventureEngine().list_transitions(active_scene.get())
        self.set_output_values(
            {"transitions": [item.model_dump(mode="json") for item in transitions]}
        )


@register("primitives/adventure/CanTakeTransition")
class CanTakeTransition(Node):
    """Evaluate whether a named transition can currently be taken."""

    def setup(self):
        """Declare transition id input and availability outputs."""
        self.add_input("transition_id", socket_type="str")
        self.add_output("available", socket_type="bool")
        self.add_output("result", socket_type="dict")
        self.add_output("reasons", socket_type="list")

    async def run(self, state: GraphState):
        """Evaluate and publish transition availability."""
        request = TransitionIdInput.model_validate(
            {"transition_id": self.require_input("transition_id")}
        )
        result = AdventureEngine().can_take_transition(
            active_scene.get(), request.transition_id
        )
        self.set_output_values(
            {
                "available": result.available,
                "result": result.model_dump(mode="json"),
                "reasons": result.reasons,
            }
        )


@register("primitives/adventure/TakeTransition")
class TakeTransition(Node):
    """Attempt one deterministic adventure transition."""

    def setup(self):
        """Declare transition request inputs and result outputs."""
        self.add_input("transition_id", socket_type="str")
        self.add_input("render_intro", socket_type="bool", optional=True)
        self.add_output("ok", socket_type="bool")
        self.add_output("result", socket_type="dict")
        self.add_output("from_scene", socket_type="str")
        self.add_output("to_scene", socket_type="str")
        self.add_output("intro", socket_type="str")
        self.add_output("error", socket_type="str")

    async def run(self, state: GraphState):
        """Take a transition and publish its structured result."""
        request = TakeTransitionInput.model_validate(
            {
                "transition_id": self.require_input("transition_id"),
                "render_intro": optional_input(self, "render_intro", True),
            }
        )
        result = AdventureEngine().take_transition(
            active_scene.get(),
            request.transition_id,
            render_intro=request.render_intro,
        )
        self.set_output_values(
            {
                "ok": result.ok,
                "result": result.model_dump(mode="json", exclude_none=True),
                "from_scene": result.from_scene or "",
                "to_scene": result.to_scene or "",
                "intro": result.intro or "",
                "error": result.error or "",
            }
        )


@register("primitives/adventure/RenderCurrentSceneContext")
class RenderCurrentSceneContext(Node):
    """Render prompt-safe prose for the active story scene."""

    def setup(self):
        """Declare audience input and rendered context output."""
        self.add_input("audience", socket_type="str", optional=True)
        self.add_output("context", socket_type="str")

    async def run(self, state: GraphState):
        """Render current adventure context for prompt or summary use."""
        request = RenderContextInput.model_validate(
            {"audience": optional_input(self, "audience", "prompt")}
        )
        context = AdventureEngine().render_current_context(
            active_scene.get(), audience=request.audience
        )
        self.set_output_values({"context": context})
