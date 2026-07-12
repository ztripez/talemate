"""Draft lifecycle and reusable-definition request contracts."""

from typing import Annotated, Literal

import pydantic

from talemate.game.primitives.adventure import AdventureDefinition
from talemate.game.primitives.deck_schema import DeckDefinition
from talemate.game.primitives.definitions import (
    ClockPayload,
    EditableDefinitionKind,
    MeterPayload,
)
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.roll_tables import RollTableDefinition

from .game_primitives_transport import (
    GamePrimitivesRequestModel,
    GamePrimitivesTransportModel,
)


class ListGamePrimitiveDraftsPayload(GamePrimitivesRequestModel):
    """Request all persisted drafts in deterministic identifier order."""

    action: Literal["list_game_primitive_drafts"]


class CreateGamePrimitiveDraftPayload(GamePrimitivesRequestModel):
    """Request creation of one revision-guarded UI draft."""

    action: Literal["create_game_primitive_draft"]
    draft_id: str | None = None
    expected_revision: str = pydantic.Field(min_length=1)


class DraftActionPayload(GamePrimitivesRequestModel):
    """Target one persisted primitive draft identifier."""

    draft_id: str = pydantic.Field(min_length=1)


class DraftMutationPayload(DraftActionPayload):
    """Require the exact pre-mutation root revision."""

    expected_revision: str = pydantic.Field(min_length=1)


class GetGamePrimitiveDraftPayload(DraftActionPayload):
    """Request one detached canonical draft."""

    action: Literal["get_game_primitive_draft"]


class DeleteGamePrimitiveDraftPayload(DraftMutationPayload):
    """Request atomic deletion of one persisted draft."""

    action: Literal["delete_game_primitive_draft"]


class ValidateGamePrimitiveDraftPayload(DraftMutationPayload):
    """Request validation and persistence of a draft status."""

    action: Literal["validate_game_primitive_draft"]


class CommitGamePrimitiveDraftPayload(DraftMutationPayload):
    """Request validated atomic installation of a draft change set."""

    action: Literal["commit_game_primitive_draft"]


class DefinitionChangeBase(GamePrimitivesTransportModel):
    """Require a definition map identifier to equal its value identifier."""

    id: str = pydantic.Field(min_length=1)

    @pydantic.model_validator(mode="after")
    def validate_value_id(self):
        """Reject disagreement between map and payload identifiers.

        Returns:
            The validated definition change.

        Raises:
            ValueError: The outer identifier differs from the value identifier.

        """
        if self.value.id != self.id:
            raise ValueError(
                f"Definition id '{self.id}' must match value id '{self.value.id}'"
            )
        return self


class DeckDefinitionChange(DefinitionChangeBase):
    """Carry a deck definition replacement keyed by the ``decks`` kind."""

    kind: Literal["decks"]
    value: DeckDefinition


class RollTableDefinitionChange(DefinitionChangeBase):
    """Carry a roll-table definition replacement and matching identifier."""

    kind: Literal["roll_tables"]
    value: RollTableDefinition


class ModifierDefinitionChange(DefinitionChangeBase):
    """Carry a modifier definition replacement and matching identifier."""

    kind: Literal["modifiers"]
    value: RollModifier


class MeterDefinitionChange(DefinitionChangeBase):
    """Carry a meter definition replacement and matching identifier."""

    kind: Literal["meters"]
    value: MeterPayload


class ClockDefinitionChange(DefinitionChangeBase):
    """Carry a clock definition replacement and matching identifier."""

    kind: Literal["clocks"]
    value: ClockPayload


class AdventureDefinitionChange(DefinitionChangeBase):
    """Carry an adventure definition replacement and matching identifier."""

    kind: Literal["adventures"]
    value: AdventureDefinition


DefinitionChange = Annotated[
    DeckDefinitionChange
    | RollTableDefinitionChange
    | ModifierDefinitionChange
    | MeterDefinitionChange
    | ClockDefinitionChange
    | AdventureDefinitionChange,
    pydantic.Field(discriminator="kind"),
]


class UpsertGamePrimitiveDefinitionPayload(DraftMutationPayload):
    """Request staging of one typed definition create or replacement."""

    action: Literal["upsert_game_primitive_definition"]
    definition: DefinitionChange


class DeleteGamePrimitiveDefinitionPayload(DraftMutationPayload):
    """Request a definition tombstone or cancellation of a staged create."""

    action: Literal["delete_game_primitive_definition"]
    kind: EditableDefinitionKind
    id: str = pydantic.Field(min_length=1)
