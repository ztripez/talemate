"""Correlated Game Primitive bundle template responses."""

from typing import Literal

from talemate.game.primitives.authoring.bundles import BundleApplicationResult
from talemate.world_state.templates.game_primitive_bundle import GamePrimitiveBundle

from .game_primitives_transport import GamePrimitivesTransportModel


class GamePrimitiveBundleCapturedResponse(GamePrimitivesTransportModel):
    """Return a captured bundle and the revision from which it was read.

    Attributes:
        type: Websocket subsystem discriminator; always ``world_state_manager``.
        action: Response operation; always ``game_primitive_bundle_captured``.
        request_id: Identifier copied from the capture request for correlation.
        revision: Primitive-store revision from which the bundle was captured.
        data: Strict reusable bundle containing the selected authored resources.

    Correlation:
        Consumers match ``request_id`` to the originating capture request and may use
        ``revision`` to detect subsequent primitive-store changes.

    """

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_bundle_captured"] = "game_primitive_bundle_captured"
    request_id: str
    revision: str
    data: GamePrimitiveBundle


class GamePrimitiveBundleApplicationResponse(GamePrimitivesTransportModel):
    """Return the preview or application result for one bundle request.

    Attributes:
        type: Websocket subsystem discriminator; always ``world_state_manager``.
        action: Response operation; always ``game_primitive_bundle_application``.
        request_id: Identifier copied from the preview or apply request.
        data: Resource counts, collisions, target draft, revision, and applied status.

    Correlation:
        Consumers match ``request_id`` to the originating preview or apply request;
        ``data.applied`` distinguishes the non-mutating preview from installation.

    """

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_bundle_application"] = "game_primitive_bundle_application"
    request_id: str
    data: BundleApplicationResult
