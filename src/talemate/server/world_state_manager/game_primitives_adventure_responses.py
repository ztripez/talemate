"""Adventure runtime action response contracts."""

from typing import Literal

from talemate.game.primitives.adventure import TransitionResult

from .game_primitives_adventure_service import AdventureActivationResult
from .game_primitives_snapshot_projections import GamePrimitivesSnapshot
from .game_primitives_transport import GamePrimitivesTransportModel


class GamePrimitiveAdventureActivationResponse(GamePrimitivesTransportModel):
    """Return an adventure activation result with its resulting snapshot."""

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_adventure_activation"] = (
        "game_primitive_adventure_activation"
    )
    request_id: str
    result: AdventureActivationResult
    data: GamePrimitivesSnapshot


class GamePrimitiveAdventureTransitionResponse(GamePrimitivesTransportModel):
    """Return a transition result with its resulting authoritative snapshot."""

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_adventure_transition"] = (
        "game_primitive_adventure_transition"
    )
    request_id: str
    result: TransitionResult
    data: GamePrimitivesSnapshot
