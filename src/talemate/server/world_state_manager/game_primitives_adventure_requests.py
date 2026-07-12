"""Adventure runtime request contracts."""

from typing import Literal

import pydantic

from .game_primitives_transport import GamePrimitivesRequestModel


class GetGamePrimitivesPayload(GamePrimitivesRequestModel):
    """Request the authoritative Game Primitives snapshot.

    Attributes:
        action: Wire discriminator fixed to ``get_game_primitives``.

    """

    action: Literal["get_game_primitives"]


class GetGamePrimitiveEditorMetadataPayload(GamePrimitivesRequestModel):
    """Request canonical editor metadata without requiring an active scene.

    Attributes:
        action: Wire discriminator fixed to
            ``get_game_primitive_editor_metadata``.
    """

    action: Literal["get_game_primitive_editor_metadata"]


class ActivateGamePrimitiveAdventurePayload(GamePrimitivesRequestModel):
    """Request activation of a stored adventure definition.

    Attributes:
        action: Wire discriminator fixed to ``activate_game_primitive_adventure``.
        adventure_id: Non-empty identifier of the adventure to activate.

    """

    action: Literal["activate_game_primitive_adventure"]
    adventure_id: str = pydantic.Field(min_length=1)


class TakeGamePrimitiveAdventureTransitionPayload(GamePrimitivesRequestModel):
    """Request traversal of an available adventure transition.

    Attributes:
        action: Wire discriminator for transition traversal.
        transition_id: Non-empty identifier of the transition to take.

    """

    action: Literal["take_game_primitive_adventure_transition"]
    transition_id: str = pydantic.Field(min_length=1)
