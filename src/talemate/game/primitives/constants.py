"""Shared Game Primitives schema constants without model dependencies."""

from typing import Literal

GAME_PRIMITIVES_KEY = "game_primitives"
CURRENT_VERSION = 1
DEFAULT_LEDGER_LIMIT = 500

ANCHOR_KINDS = (
    "scene",
    "character",
    "object",
    "relationship",
    "location",
    "story_scene",
    "project",
)

DEFINITION_KINDS = (
    "decks",
    "roll_tables",
    "meters",
    "clocks",
    "relationship_models",
    "modifiers",
    "attribute_sources",
    "adventures",
)
TYPED_DEFINITION_KINDS = (
    "decks",
    "roll_tables",
    "meters",
    "clocks",
    "modifiers",
    "adventures",
)
EDITABLE_DEFINITION_KINDS = TYPED_DEFINITION_KINDS
DEFINITION_EDITOR_KINDS = (
    "decks",
    "roll_tables",
    "meters",
    "clocks",
    "modifiers",
)

PRIMITIVE_KINDS = (
    "meters",
    "clocks",
    "decks",
    "roll_tables",
    "attributes",
    "modifiers",
)
TYPED_PRIMITIVE_KINDS = PRIMITIVE_KINDS
EDITABLE_PRIMITIVE_KINDS = TYPED_PRIMITIVE_KINDS
PRIMITIVE_EDITOR_KINDS = (
    "meters",
    "clocks",
    "decks",
    "roll_tables",
    "attributes",
)

CONDITION_KINDS = (
    "path",
    "primitive",
    "anchor_has_tag",
    "anchor_missing_tag",
    "meter",
    "clock_complete",
    "relationship",
    "always",
    "never",
)

EFFECT_KINDS = (
    "set",
    "unset",
    "inc",
    "dec",
    "add_tag",
    "remove_tag",
    "append",
    "extend",
)

DefinitionKind = Literal[*DEFINITION_KINDS]
EditableDefinitionKind = Literal[*EDITABLE_DEFINITION_KINDS]
PrimitiveKind = Literal[*PRIMITIVE_KINDS]
EditablePrimitiveKind = Literal[*EDITABLE_PRIMITIVE_KINDS]
