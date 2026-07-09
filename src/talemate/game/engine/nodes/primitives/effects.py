"""Node wrappers for Game Primitives effects."""

from talemate.context import active_scene
from talemate.game.engine.nodes.core import GraphState, Node
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.effects import apply_effects
from talemate.game.primitives.store import PrimitiveStore

__all__ = ["ApplyEffects"]


@register("primitives/effects/ApplyEffects")
class ApplyEffects(Node):
    """Apply a list of primitive effects to the active scene."""

    def setup(self):
        """Declare effect input sockets and batch result outputs."""
        self.add_input("effects", socket_type="list,dict")
        self.add_input("reason", socket_type="str", optional=True)
        self.add_output("ok", socket_type="bool")
        self.add_output("results", socket_type="list")

    async def run(self, state: GraphState):
        """Apply the provided effects to the active scene's primitive store."""
        scene = active_scene.get()
        store = PrimitiveStore.for_scene(scene)
        result = apply_effects(
            store,
            self.require_input("effects"),
            reason=self.normalized_input_value("reason"),
        )
        self.set_output_values(
            {
                "ok": result.ok,
                "results": [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in result.results
                ],
            }
        )
