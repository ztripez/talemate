"""Expose deterministic Game Primitives runtime and prompt-context APIs.

Game Primitives provide deterministic storage, references, attributes, effects,
relationships, roll tables, deck selection, shared selection results, and
prompt-safe rendering of primitive state for agent instructions. Importing this
package does not mutate scene state.
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
from talemate.game.primitives.context import (
    PrimitiveContextDebug,
    PrimitiveContextRenderer,
    PrimitiveRenderedContext,
)
from talemate.game.primitives.deck_schema import (
    DeckCard,
    DeckDefinition,
    DeckDrawOptions,
    DeckRuntimeState,
)
from talemate.game.primitives.deck_state import DeckInstancePayload
from talemate.game.primitives.decks import DeckEngine
from talemate.game.primitives.definitions import MeterPayload
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
    RelationshipGraph,
    relationship_meter,
)
from talemate.game.primitives.roll_tables import (
    RollTableDefinition,
    RollTableEngine,
    RollTablePreviewRequest,
    RollTableRollRequest,
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
    "DeckInstancePayload",
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
    "PrimitiveContextDebug",
    "PrimitiveContextRenderer",
    "PrimitiveRenderedContext",
    "PrimitiveRef",
    "RollModifier",
    "MeterPayload",
    "RelationshipGraph",
    "RollTableDefinition",
    "RollTableEngine",
    "RollTablePreviewRequest",
    "RollTableRollRequest",
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
    "relationship_meter",
    "relationship_participants",
    "scene_anchor",
]
