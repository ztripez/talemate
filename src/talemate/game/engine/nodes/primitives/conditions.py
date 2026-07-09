"""Node wrappers for Game Primitives conditions."""

from talemate.context import active_scene
from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.conditions import evaluate_condition_input

__all__ = ["EvaluateCondition"]


@register("primitives/conditions/EvaluateCondition")
class EvaluateCondition(Node):
    """Evaluate primitive-aware conditions against the active scene."""

    def setup(self):
        """Declare condition input and debug result output sockets."""
        self.add_input("condition", socket_type="dict,list")
        self.add_output("matches", socket_type="bool")
        self.add_output("debug", socket_type="list")

    async def run(self, state: GraphState):
        """Evaluate the provided primitive-aware condition input."""
        scene = active_scene.get()
        matches, debug = evaluate_condition_input(
            scene, self.require_input("condition")
        )
        self.set_output_values({"matches": matches, "debug": debug})
