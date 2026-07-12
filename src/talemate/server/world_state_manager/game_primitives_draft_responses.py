"""Draft action response contracts."""

from typing import Literal

from talemate.game.primitives.draft_schema import PrimitiveDraft

from .game_primitives_transport import GamePrimitivesTransportModel


class GamePrimitiveDraftResponse(GamePrimitivesTransportModel):
    """Return one persisted draft and the authoritative root revision."""

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_draft"] = "game_primitive_draft"
    request_id: str
    data: PrimitiveDraft
    revision: str


class GamePrimitiveDraftsResponse(GamePrimitivesTransportModel):
    """Return persisted drafts and the authoritative root revision."""

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_drafts"] = "game_primitive_drafts"
    request_id: str
    data: list[PrimitiveDraft]
    revision: str
