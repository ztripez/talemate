"""Graph node wrappers for Game Primitives deck operations.

These nodes expose deck drawing, inspection, shuffling, and reset operations to
Talemate graph execution. Each node reads the active scene from
``talemate.context.active_scene`` and delegates behavior to ``DeckEngine``.
"""

from talemate.context import active_scene
from talemate.game.engine.nodes.core import UNRESOLVED, GraphState, Node
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.decks import DeckDrawRequest, DeckEngine

__all__ = ["Draw", "Peek", "Reset", "Shuffle"]


@register("primitives/decks/Draw")
class Draw(Node):
    """Graph node that draws one card from a Game Primitives deck.

    Inputs include a deck definition/id/ref plus optional anchor, instance id,
    tag filters, recent-card avoidance, trace context, and immediate effect
    application. Outputs expose the full selection result and convenience card
    fields.
    """

    def setup(self):
        """Declare deck draw inputs and selection result outputs."""
        self.add_input("deck", socket_type="str,dict")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("instance_id", socket_type="str", optional=True)
        self.add_input("include_tags", socket_type="list", optional=True)
        self.add_input("exclude_tags", socket_type="list", optional=True)
        self.add_input("avoid_recent", socket_type="int", optional=True)
        self.add_input("context", socket_type="dict", optional=True)
        self.add_input("apply_effects", socket_type="bool", optional=True)
        self.add_output("result", socket_type="dict")
        self.add_output("card_id", socket_type="str")
        self.add_output("label", socket_type="str")
        self.add_output("text", socket_type="str")
        self.add_output("variables", socket_type="dict")
        self.add_output("effects", socket_type="list")
        self.add_output("debug", socket_type="dict")

    async def run(self, state: GraphState):
        """Draw a card using the active scene and publish selection outputs.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes selection data to output sockets.

        Raises:
            PrimitiveError: If deck resolution or draw execution fails.
            pydantic.ValidationError: If node inputs are invalid.
        """
        scene = active_scene.get()
        request = DeckDrawRequest.model_validate(
            {
                "deck": self.require_input("deck"),
                "anchor": self.normalized_input_value("anchor"),
                "instance_id": self.normalized_input_value("instance_id"),
                "include_tags": _optional_input(self, "include_tags", []),
                "exclude_tags": _optional_input(self, "exclude_tags", []),
                "avoid_recent": _optional_input(self, "avoid_recent", None),
                "context": _optional_input(self, "context", {}),
                "apply_effects": _optional_input(self, "apply_effects", False),
            }
        )
        result = DeckEngine().draw(
            scene,
            request.deck,
            anchor=request.anchor,
            instance_id=request.instance_id,
            options=request.options(),
        )
        payload = result.model_dump(mode="json", exclude_none=True)
        self.set_output_values(
            {
                "result": payload,
                "card_id": result.result_id,
                "label": result.label,
                "text": result.text,
                "variables": payload.get("variables", {}),
                "effects": [
                    effect.model_dump(mode="json", exclude_none=True)
                    for effect in result.effects
                ],
                "debug": payload["debug"],
            }
        )


@register("primitives/decks/Peek")
class Peek(Node):
    """Graph node that returns deck runtime state without drawing.

    Inputs are ``deck`` plus optional ``anchor`` and ``instance_id``. Output
    ``state`` contains a JSON-compatible peek result with the primitive ref and
    runtime state.
    """

    def setup(self):
        """Declare deck reference inputs and peek output."""
        self.add_input("deck", socket_type="str,dict")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("instance_id", socket_type="str", optional=True)
        self.add_output("state", socket_type="dict")

    async def run(self, state: GraphState):
        """Peek at a deck instance using the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes the runtime state payload to ``state``.

        Raises:
            PrimitiveError: If deck resolution or peek execution fails.
            pydantic.ValidationError: If deck input payloads are invalid.
        """
        scene = active_scene.get()
        payload = DeckEngine().peek(
            scene,
            self.require_input("deck"),
            anchor=self.normalized_input_value("anchor"),
            instance_id=self.normalized_input_value("instance_id"),
        )
        self.set_output_values({"state": payload})


@register("primitives/decks/Shuffle")
class Shuffle(Node):
    """Graph node that shuffles a persisted deck instance.

    Inputs are ``deck`` plus optional ``anchor`` and ``instance_id``. Output
    ``state`` contains the updated runtime state after shuffling.
    """

    def setup(self):
        """Declare deck reference inputs and shuffled state output."""
        self.add_input("deck", socket_type="str,dict")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("instance_id", socket_type="str", optional=True)
        self.add_output("state", socket_type="dict")

    async def run(self, state: GraphState):
        """Shuffle a deck instance using the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes the updated runtime state to ``state``.

        Raises:
            PrimitiveError: If deck resolution or shuffle execution fails.
            pydantic.ValidationError: If deck input payloads are invalid.
        """
        scene = active_scene.get()
        runtime = DeckEngine().shuffle(
            scene,
            self.require_input("deck"),
            anchor=self.normalized_input_value("anchor"),
            instance_id=self.normalized_input_value("instance_id"),
        )
        self.set_output_values({"state": runtime.model_dump(mode="json")})


@register("primitives/decks/Reset")
class Reset(Node):
    """Graph node that resets a persisted deck instance.

    Inputs are ``deck`` plus optional ``anchor`` and ``instance_id``. Output
    ``state`` contains the fresh runtime state after reset.
    """

    def setup(self):
        """Declare deck reference inputs and reset state output."""
        self.add_input("deck", socket_type="str,dict")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("instance_id", socket_type="str", optional=True)
        self.add_output("state", socket_type="dict")

    async def run(self, state: GraphState):
        """Reset a deck instance using the active scene.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes the reset runtime state to ``state``.

        Raises:
            PrimitiveError: If deck resolution or reset execution fails.
            pydantic.ValidationError: If deck input payloads are invalid.
        """
        scene = active_scene.get()
        runtime = DeckEngine().reset(
            scene,
            self.require_input("deck"),
            anchor=self.normalized_input_value("anchor"),
            instance_id=self.normalized_input_value("instance_id"),
        )
        self.set_output_values({"state": runtime.model_dump(mode="json")})


def _optional_input(node: Node, name: str, default):
    """Return an optional node input while preserving explicit ``None``."""
    value = node.get_input_value(name)
    return default if value is UNRESOLVED else value
