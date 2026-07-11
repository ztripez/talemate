"""Node wrappers for Game Primitives roll tables."""

import asyncio

from talemate.context import active_scene
from talemate.game.engine.nodes.core import UNRESOLVED, GraphState, Node
from talemate.game.engine.nodes.registry import register
from talemate.game.primitives.roll_tables import (
    RollTableEngine,
    RollTablePreviewRequest,
    RollTableRollRequest,
    _compute_odds_preview,
)

__all__ = ["PreviewOdds", "Roll"]


@register("primitives/roll_tables/Roll")
class Roll(Node):
    """Resolve one roll table selection against the active scene.

    The optional ``context`` input is trace metadata copied into roll debug and
    ledger output; it does not affect selection behavior.
    """

    def setup(self):
        """Declare roll table input and selection result output sockets."""
        self.add_input("table", socket_type="str,dict")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_input("context", socket_type="dict", optional=True)
        self.add_input("apply_effects", socket_type="bool", optional=True)
        self.add_output("result", socket_type="dict")
        self.add_output("result_id", socket_type="str")
        self.add_output("label", socket_type="str")
        self.add_output("text", socket_type="str")
        self.add_output("effects", socket_type="list")
        self.add_output("debug", socket_type="dict")

    async def run(self, state: GraphState):
        """Roll the input table using the active scene and publish outputs."""
        scene = active_scene.get()
        context = self.get_input_value("context")
        apply_effects = self.get_input_value("apply_effects")
        request = RollTableRollRequest.model_validate(
            {
                "table": self.require_input("table"),
                "anchor": self.normalized_input_value("anchor"),
                "context": {} if context is UNRESOLVED else context,
                "apply_effects": (
                    False if apply_effects is UNRESOLVED else apply_effects
                ),
            }
        )
        result = RollTableEngine().roll(
            scene,
            request.table,
            anchor=request.anchor,
            context=request.context,
            apply_effects=request.apply_effects,
        )
        payload = result.model_dump(mode="json", exclude_none=True)
        self.set_output_values(
            {
                "result": payload,
                "result_id": result.result_id,
                "label": result.label,
                "text": result.text,
                "effects": [
                    effect.model_dump(mode="json", exclude_none=True)
                    for effect in result.effects
                ],
                "debug": payload["debug"],
            }
        )


@register("primitives/roll_tables/PreviewOdds")
class PreviewOdds(Node):
    """Preview roll table odds without mutating primitive state."""

    def setup(self):
        """Declare roll table odds preview input and output sockets."""
        self.add_input("table", socket_type="str,dict")
        self.add_input("anchor", socket_type="str", optional=True)
        self.add_output("odds", socket_type="dict")

    async def run(self, state: GraphState):
        """Compute preview odds for the provided roll table."""
        scene = active_scene.get()
        request = RollTablePreviewRequest.model_validate(
            {
                "table": self.require_input("table"),
                "anchor": self.normalized_input_value("anchor"),
            }
        )
        prepared = RollTableEngine()._prepare_odds_preview(
            scene,
            request.table,
            anchor=request.anchor,
        )
        odds = await asyncio.to_thread(_compute_odds_preview, prepared)
        self.set_output_values({"odds": odds})
