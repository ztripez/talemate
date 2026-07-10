"""Node wrappers for Game Primitives conditions."""

from talemate.context import active_scene
from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.conditions import evaluate_condition_input

__all__ = ["EvaluateCondition"]


@register("primitives/conditions/EvaluateCondition")
class EvaluateCondition(Node):
    """Evaluate primitive-aware condition payloads against the active scene.

    A primitive-aware condition is a Boolean predicate over Talemate scene game
    state or Game Primitives state. The node reads a ``condition`` dictionary or
    list input and emits a Boolean ``matches`` value plus JSON-compatible
    evaluation debug records.
    """

    def setup(self):
        """Declare input and output sockets for primitive condition evaluation.

        Returns:
            None. The method registers a required ``condition`` input accepting a
            dictionary or list payload, a ``matches`` Boolean output, and a
            ``debug`` list output.
        """
        self.add_input("condition", socket_type="dict,list")
        self.add_output("matches", socket_type="bool")
        self.add_output("debug", socket_type="list")

    async def run(self, state: GraphState):
        """Evaluate the required condition payload and write match/debug outputs.

        Args:
            state: Graph execution state supplied by the node runner.

        Returns:
            None. The node writes ``matches`` and ``debug`` values to output sockets.

        Raises:
            ValueError: If the condition payload shape is unsupported or required
                condition fields are missing.
            pydantic.ValidationError: If a condition or group payload fails validation.
            PrimitiveStoreError: If primitive state read during evaluation is invalid.
        """
        scene = active_scene.get()
        matches, debug = evaluate_condition_input(
            scene, self.require_input("condition")
        )
        self.set_output_values({"matches": matches, "debug": debug})
