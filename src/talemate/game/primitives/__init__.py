"""Provide the public namespace for deterministic Game Primitives runtime code.

Game Primitives are deterministic game-runtime building blocks for storage,
references, effects, roll tables, deck selection, and shared selection result
payloads. Importing this package does not mutate scene state.
"""

from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    character_anchor,
    object_anchor,
    relationship_anchor,
    relationship_participants,
    scene_anchor,
)
from talemate.game.primitives.attributes import (
    AttributeResolution,
    AttributeResolver,
    AttributeSource,
)
from talemate.game.primitives.conditions import (
    PrimitiveCondition,
    PrimitiveConditionGroup,
    evaluate_condition_input,
)
from talemate.game.primitives.decks import (
    DeckCard,
    DeckDefinition,
    DeckDrawOptions,
    DeckEngine,
    DeckRuntimeState,
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
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.relationships import (
    RelationshipDimension,
    RelationshipGraph,
)
from talemate.game.primitives.roll_tables import (
    RollTableDefinition,
    RollTableEngine,
    RollTableRow,
    parse_dice,
    parse_range,
)
from talemate.game.primitives.selection import SelectionResult
from talemate.game.primitives.store import PrimitiveStore

__all__ = [
    "AnchorRef",
    "AttributeResolution",
    "AttributeResolver",
    "AttributeSource",
    "DeckCard",
    "DeckDefinition",
    "DeckDrawOptions",
    "DeckEngine",
    "DeckRuntimeState",
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
    "RollModifier",
    "RelationshipDimension",
    "RelationshipGraph",
    "RollTableDefinition",
    "RollTableEngine",
    "RollTableRow",
    "SelectionResult",
    "PrimitiveStore",
    "PrimitiveStoreError",
    "apply_effect",
    "apply_effects",
    "character_anchor",
    "evaluate_condition_input",
    "object_anchor",
    "parse_dice",
    "parse_range",
    "relationship_anchor",
    "relationship_participants",
    "scene_anchor",
]
