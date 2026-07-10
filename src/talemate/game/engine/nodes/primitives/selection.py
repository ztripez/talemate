"""Node aliases for shared Game Primitives selection behavior."""

from talemate.game.engine.nodes.primitives.effects import (
    ApplyEffects as EffectsApplyEffects,
)
from talemate.game.engine.nodes.registry import register

__all__ = ["ApplyEffects"]


@register("primitives/selection/ApplyEffects")
class ApplyEffects(EffectsApplyEffects):
    """Apply effects carried by a selection result.

    This node reuses the canonical primitive effect application node while
    exposing the issue #10 selection namespace expected by roll table results.
    """
