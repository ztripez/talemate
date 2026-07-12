"""Common snapshot, failure, and indeterminate response contracts."""

from typing import Literal

import pydantic

from .game_primitives_snapshot_projections import (
    GamePrimitiveEditorMetadata,
    GamePrimitivesSnapshot,
)
from .game_primitives_transport import GamePrimitivesTransportModel


class GamePrimitivesResponse(GamePrimitivesTransportModel):
    """Return an authoritative snapshot correlated to one request.

    Attributes:
        type: Owning websocket channel, always ``world_state_manager``.
        action: Response discriminator, always ``game_primitives``.
        request_id: Identifier copied from the originating request.
        data: Detached authoritative Game Primitives snapshot.

    """

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitives"] = "game_primitives"
    request_id: str
    data: GamePrimitivesSnapshot


class GamePrimitiveEditorMetadataResponse(GamePrimitivesTransportModel):
    """Return canonical scene-independent metadata correlated to one request.

    Attributes:
        type: Owning websocket channel, always ``world_state_manager``.
        action: Response discriminator, always ``game_primitive_editor_metadata``.
        request_id: Identifier copied from the originating request.
        data: Metadata projected from canonical backend registries.
    """

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_editor_metadata"] = "game_primitive_editor_metadata"
    request_id: str
    data: GamePrimitiveEditorMetadata


class GamePrimitivesError(GamePrimitivesTransportModel):
    """Carry a human-readable Game Primitives transport error message."""

    message: str


class GamePrimitivesFailedResponse(GamePrimitivesTransportModel):
    """Report a request that failed before a mutation was committed."""

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitives_failed"] = "game_primitives_failed"
    request_id: str
    request_action: str
    error: GamePrimitivesError


class GamePrimitivesIndeterminateResponse(GamePrimitivesTransportModel):
    """Report a committed mutation whose response could not be confirmed.

    Attributes:
        type: Owning websocket channel.
        action: Indeterminate-outcome response discriminator.
        request_id: Identifier of the committed request.
        request_action: Action performed by the committed request.
        outcome: Fixed committed-but-unconfirmed outcome marker.
        revision: Authoritative revision after the commit.
        error: Failure encountered while emitting confirmation.

    """

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitives_indeterminate"] = "game_primitives_indeterminate"
    request_id: str
    request_action: str = pydantic.Field(min_length=1)
    outcome: Literal["committed_but_unconfirmed"] = "committed_but_unconfirmed"
    revision: str = pydantic.Field(min_length=1)
    error: GamePrimitivesError
