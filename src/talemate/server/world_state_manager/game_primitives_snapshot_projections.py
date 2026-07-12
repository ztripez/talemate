"""Strict detached snapshot projections for Game Primitives transport."""

from typing import Annotated, Literal

import pydantic

from talemate.game.primitives.adventure import (
    AdventureDefinition,
    TransitionAvailability,
    TransitionLogEntry,
)
from talemate.game.primitives.constants import (
    ANCHOR_KINDS,
    CONDITION_KINDS,
    DEFINITION_EDITOR_KINDS,
    DEFINITION_KINDS,
    EDITABLE_DEFINITION_KINDS,
    EDITABLE_PRIMITIVE_KINDS,
    EFFECT_KINDS,
    PRIMITIVE_EDITOR_KINDS,
    PRIMITIVE_KINDS,
)
from talemate.game.primitives.containers import AnchorPrimitives
from talemate.game.primitives.deck_schema import DeckDefinition
from talemate.game.primitives.definitions import ClockPayload, MeterPayload
from talemate.game.primitives.draft_schema import DraftValidation
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.render import RENDER_POLICIES, RenderPolicy
from talemate.game.primitives.roll_tables import RollTableDefinition

from .game_primitives_request_contracts import (
    assert_game_primitives_transport_kind_coverage,
)
from .game_primitives_transport import GamePrimitivesTransportModel


class DefinitionSnapshotBase(GamePrimitivesTransportModel):
    """Expose the shared identifier and display title of a definition."""

    id: str
    title: str


class DeckDefinitionSnapshot(DefinitionSnapshotBase):
    """Project a deck definition onto the transport wire."""

    kind: Literal["decks"]
    details: DeckDefinition


class RollTableDefinitionSnapshot(DefinitionSnapshotBase):
    """Project a roll-table definition onto the transport wire."""

    kind: Literal["roll_tables"]
    details: RollTableDefinition


class ModifierDefinitionSnapshot(DefinitionSnapshotBase):
    """Project a roll modifier definition onto the transport wire."""

    kind: Literal["modifiers"]
    details: RollModifier


class MeterDefinitionSnapshot(DefinitionSnapshotBase):
    """Project a meter definition onto the transport wire."""

    kind: Literal["meters"]
    details: MeterPayload


class ClockDefinitionSnapshot(DefinitionSnapshotBase):
    """Project a clock definition onto the transport wire."""

    kind: Literal["clocks"]
    details: ClockPayload


class AdventureDefinitionSnapshot(DefinitionSnapshotBase):
    """Project an adventure definition onto the transport wire."""

    kind: Literal["adventures"]
    details: AdventureDefinition


class RelationshipModelDefinitionSnapshot(DefinitionSnapshotBase):
    """Project JSON-compatible relationship-model definition details."""

    kind: Literal["relationship_models"]
    details: dict[str, pydantic.JsonValue]


class AttributeSourceDefinitionSnapshot(DefinitionSnapshotBase):
    """Project JSON-compatible attribute-source definition details."""

    kind: Literal["attribute_sources"]
    details: dict[str, pydantic.JsonValue]


DefinitionSnapshot = Annotated[
    DeckDefinitionSnapshot
    | RollTableDefinitionSnapshot
    | ModifierDefinitionSnapshot
    | MeterDefinitionSnapshot
    | ClockDefinitionSnapshot
    | AdventureDefinitionSnapshot
    | RelationshipModelDefinitionSnapshot
    | AttributeSourceDefinitionSnapshot,
    pydantic.Field(discriminator="kind"),
]
DEFINITION_SNAPSHOT_ADAPTER = pydantic.TypeAdapter(DefinitionSnapshot)


class AnchorSnapshot(GamePrimitivesTransportModel):
    """Project one anchor, its metadata, and detached primitive instances."""

    ref: str
    kind: str
    id: str
    tags: list[str]
    meta: dict[str, pydantic.JsonValue]
    primitives: AnchorPrimitives
    primitive_counts: dict[str, pydantic.StrictInt]
    primitive_count: pydantic.StrictInt
    primitive_refs: list[str]


class RelationshipSnapshot(GamePrimitivesTransportModel):
    """Project one directional relationship and its meter dimensions."""

    anchor: str
    source: str
    target: str
    summary: str
    dimensions: list[MeterPayload]


class DraftSnapshot(GamePrimitivesTransportModel):
    """Summarize a persisted draft without exposing its complete change set."""

    id: str
    status: Literal["draft", "validated", "committed"]
    created_by: str
    definition_counts: dict[str, pydantic.StrictInt]
    anchor_count: pydantic.StrictInt
    primitive_count: pydantic.StrictInt
    validation: DraftValidation


class AdventureStateSnapshot(GamePrimitivesTransportModel):
    """Project adventure visit, completion, and transition history state."""

    visited: list[str]
    completed: list[str]
    transition_log: list[TransitionLogEntry]


class StorySceneSnapshot(GamePrimitivesTransportModel):
    """Project the currently active story scene and rendering metadata."""

    id: str
    title: str
    description: str | None
    location: str | None
    intro: str | None
    goals: list[str]
    local_anchors: list[str]
    render_policy: RenderPolicy


class CurrentAdventureSnapshot(GamePrimitivesTransportModel):
    """Project the active adventure, scene, state, and available transitions."""

    id: str
    title: str
    description: str | None
    current_story_scene: StorySceneSnapshot
    state: AdventureStateSnapshot
    transitions: list[TransitionAvailability]


class GamePrimitiveEditorMetadata(GamePrimitivesTransportModel):
    """Publish server-owned kind registries and render policies to editors."""

    definition_kinds: list[Literal[*DEFINITION_KINDS]]
    editable_definition_kinds: list[Literal[*EDITABLE_DEFINITION_KINDS]]
    primitive_kinds: list[Literal[*PRIMITIVE_KINDS]]
    editable_primitive_kinds: list[Literal[*EDITABLE_PRIMITIVE_KINDS]]
    definition_editor_kinds: list[Literal[*DEFINITION_EDITOR_KINDS]]
    primitive_editor_kinds: list[Literal[*PRIMITIVE_EDITOR_KINDS]]
    anchor_kinds: list[Literal[*ANCHOR_KINDS]]
    condition_kinds: list[Literal[*CONDITION_KINDS]]
    effect_kinds: list[Literal[*EFFECT_KINDS]]
    render_policies: list[Literal[*RENDER_POLICIES]]


class GamePrimitivesSnapshot(GamePrimitivesTransportModel):
    """Carry the complete detached Game Primitives state for frontend reads."""

    initialized: bool
    version: pydantic.StrictInt | None
    revision: str
    editor_metadata: GamePrimitiveEditorMetadata
    definition_counts: dict[str, pydantic.StrictInt]
    definitions: list[DefinitionSnapshot]
    anchor_count: pydantic.StrictInt
    primitive_count: pydantic.StrictInt
    anchors: list[AnchorSnapshot]
    active_characters: list[str]
    relationships: list[RelationshipSnapshot]
    drafts: list[DraftSnapshot]
    current_adventure: CurrentAdventureSnapshot | None
    recent_ledger: list[LedgerEntry]


assert_game_primitives_transport_kind_coverage(DefinitionSnapshot)
