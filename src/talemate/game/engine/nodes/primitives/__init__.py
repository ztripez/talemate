"""Register Game Primitives graph nodes with the Talemate node registry.

Game Primitives are deterministic game-runtime building blocks intended to
expose stable node interfaces without mutating scene state during module import.
Importing this module registers primitive nodes so graph execution can discover
them through the central node registry.
"""

from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.registry import register

__all__ = ["DebugPing"]


@register("primitives/DebugPing")
class DebugPing(Node):
    """Graph node that emits a deterministic Game Primitives health-check payload.

    The node has no inputs and produces two outputs: ``ok`` is always ``True``
    and ``message`` is always ``"game-primitives"``. Running the node must not
    read or mutate scene state.
    """

    def setup(self):
        """Add the fixed debug output sockets for the health-check node.

        Creates an ``ok`` boolean output and a ``message`` string output on the
        node instance. The method does not read or mutate scene state.

        Returns:
            None.
        """
        self.add_output("ok", socket_type="bool")
        self.add_output("message", socket_type="str")

    async def run(self, state: GraphState):
        """Write the deterministic health-check values to the node outputs.

        Args:
            state: Graph execution state supplied by the node runner. The
                health-check node does not read values from the graph state.

        Returns:
            None. The node writes ``ok=True`` and
            ``message="game-primitives"`` to its output sockets.
        """
        self.set_output_values({"ok": True, "message": "game-primitives"})


import talemate.game.engine.nodes.primitives.conditions  # noqa: E402,F401
import talemate.game.engine.nodes.primitives.decks  # noqa: E402,F401
import talemate.game.engine.nodes.primitives.effects  # noqa: E402,F401
import talemate.game.engine.nodes.primitives.relationships  # noqa: E402,F401
import talemate.game.engine.nodes.primitives.roll_tables  # noqa: E402,F401
import talemate.game.engine.nodes.primitives.selection  # noqa: E402,F401
