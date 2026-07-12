"""Strict websocket requests for Game Primitive bundle templates."""

from typing import Literal

import pydantic

from talemate.game.primitives.authoring.bundles import BundleSelection

from .game_primitives_transport import GamePrimitivesRequestModel


class CaptureGamePrimitiveBundlePayload(GamePrimitivesRequestModel):
    """Request capture of selected authored resources as a reusable bundle.

    Attributes:
        type: Websocket subsystem discriminator; always ``world_state_manager``.
        action: Requested operation; always ``capture_game_primitive_bundle``.
        request_id: Non-empty identifier correlating the request and response.
        name: Display name assigned to the captured bundle template.
        source: Authored resource area to capture, either committed state or a draft.
        expected_revision: Primitive-store revision required for a consistent capture.
        draft_id: Draft source identifier, or ``None`` for committed capture.
        selection: Definition and exact-anchor references included in the bundle.

    Invariants:
        Unknown fields and coercion are rejected. ``draft_id`` is present exactly when
        ``source`` is ``draft``; selection references are canonical and unique.

    """

    action: Literal["capture_game_primitive_bundle"]
    name: str
    source: Literal["committed", "draft"]
    expected_revision: str
    draft_id: str | None = None
    selection: BundleSelection

    @pydantic.model_validator(mode="after")
    def validate_capture_source(self) -> "CaptureGamePrimitiveBundlePayload":
        """Enforce the canonical capture source and draft identifier pairing.

        Args:
            self: Fully field-validated capture request to inspect.

        Returns:
            This request unchanged when draft capture has a ``draft_id`` and
            committed capture does not.

        Raises:
            ValueError: ``source`` is ``draft`` without a ``draft_id``, or is
                ``committed`` with a ``draft_id``.

        """
        if self.source == "draft" and self.draft_id is None:
            raise ValueError("draft_id is required for draft capture")
        if self.source == "committed" and self.draft_id is not None:
            raise ValueError("draft_id is invalid for committed capture")
        return self


class PreviewGamePrimitiveBundlePayload(GamePrimitivesRequestModel):
    """Request a non-mutating collision preview for a stored bundle template.

    Attributes:
        type: Websocket subsystem discriminator; always ``world_state_manager``.
        action: Requested operation; always ``preview_game_primitive_bundle``.
        request_id: Non-empty identifier correlating the request and response.
        group_uid: Template-group identifier containing the bundle.
        template_uid: Bundle template identifier within the selected group.
        expected_revision: Primitive-store revision against which to preview.
        draft_id: Existing target draft identifier, or ``None`` for a new draft.

    Invariants:
        Unknown fields and coercion are rejected, and ``request_id`` is non-empty.

    """

    action: Literal["preview_game_primitive_bundle"]
    group_uid: str
    template_uid: str
    expected_revision: str
    draft_id: str | None = None


class ApplyGamePrimitiveBundlePayload(GamePrimitivesRequestModel):
    """Request atomic installation of a stored bundle into an authoring draft.

    Attributes:
        type: Websocket subsystem discriminator; always ``world_state_manager``.
        action: Requested operation; always ``apply_game_primitive_bundle``.
        request_id: Non-empty identifier correlating the request and response.
        group_uid: Template-group identifier containing the bundle.
        template_uid: Bundle template identifier within the selected group.
        expected_revision: Primitive-store revision required before installation.
        draft_id: Existing target draft identifier, or ``None`` to create a draft.

    Invariants:
        Unknown fields and coercion are rejected, and ``request_id`` is non-empty.

    """

    action: Literal["apply_game_primitive_bundle"]
    group_uid: str
    template_uid: str
    expected_revision: str
    draft_id: str | None = None
