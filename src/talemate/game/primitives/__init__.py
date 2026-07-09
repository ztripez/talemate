"""Provide the public namespace for deterministic Game Primitives runtime code.

Game Primitives are deterministic game-runtime building blocks for storage,
references, effects, selection, and rendering helpers. Importing this package
does not mutate scene state.
"""

from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    character_anchor,
    object_anchor,
    relationship_anchor,
    scene_anchor,
)
from talemate.game.primitives.conditions import (
    PrimitiveCondition,
    PrimitiveConditionGroup,
    evaluate_condition_input,
)
from talemate.game.primitives.effects import (
    Effect,
    EffectBatchResult,
    EffectResult,
    apply_effect,
    apply_effects,
)
from talemate.game.primitives.exceptions import (
    InvalidAnchorRef,
    InvalidPrimitiveRef,
    PrimitiveError,
    PrimitiveStoreError,
)
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.store import PrimitiveStore

__all__ = [
    "AnchorRef",
    "Effect",
    "EffectBatchResult",
    "EffectResult",
    "InvalidAnchorRef",
    "InvalidPrimitiveRef",
    "LedgerEntry",
    "PrimitiveError",
    "PrimitiveCondition",
    "PrimitiveConditionGroup",
    "PrimitiveRef",
    "PrimitiveStore",
    "PrimitiveStoreError",
    "apply_effect",
    "apply_effects",
    "character_anchor",
    "evaluate_condition_input",
    "object_anchor",
    "relationship_anchor",
    "scene_anchor",
]
