"""Websocket handlers for reusable Game Primitive bundle templates."""

from talemate.game.primitives.authoring.bundles import GamePrimitiveBundleService
from talemate.world_state.templates.game_primitive_bundle import GamePrimitiveBundle

from .game_primitives_bundle_requests import (
    ApplyGamePrimitiveBundlePayload,
    CaptureGamePrimitiveBundlePayload,
    PreviewGamePrimitiveBundlePayload,
)
from .game_primitives_bundle_responses import (
    GamePrimitiveBundleApplicationResponse,
    GamePrimitiveBundleCapturedResponse,
)


class GamePrimitivesBundleHandlers:
    """Capture, preview, and atomically apply global bundle templates."""

    def _bundle_template(self, group_uid: str, template_uid: str) -> GamePrimitiveBundle:
        template = self.world_state_manager.template_collection.find_template(
            group_uid, template_uid
        )
        if not isinstance(template, GamePrimitiveBundle):
            raise ValueError("Game Primitive bundle template not found")
        return template.model_copy(deep=True)

    async def handle_capture_game_primitive_bundle(
        self, payload: CaptureGamePrimitiveBundlePayload
    ) -> None:
        """Capture selected resources and queue the correlated bundle response.

        ``payload`` supplies the live-or-draft source, selected resources, expected
        revision, bundle name, and correlation ID. Capture does not persist scene
        state; it queues one ``game_primitive_bundle_captured`` response. Invalid
        revisions, sources, drafts, selections, stored data, or response data fail
        before success is reported, and websocket transport failures propagate.

        """
        bundle = GamePrimitiveBundleService.capture(
            self.scene,
            name=payload.name,
            selection=payload.selection,
            source=payload.source,
            expected_revision=payload.expected_revision,
            draft_id=payload.draft_id,
        )
        response = GamePrimitiveBundleCapturedResponse(
            request_id=payload.request_id,
            revision=payload.expected_revision,
            data=bundle,
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    async def handle_preview_game_primitive_bundle(
        self, payload: PreviewGamePrimitiveBundlePayload
    ) -> None:
        """Preview a stored bundle and queue its correlated application result.

        ``payload`` identifies the stored template, target draft, expected revision,
        and correlation ID. Preview does not persist its candidate; it queues one
        non-applied ``game_primitive_bundle_application`` response. Missing or invalid
        templates, revisions, drafts, stored data, and response data fail before
        success is reported, and websocket transport failures propagate.

        """
        result = GamePrimitiveBundleService.preview(
            self.scene,
            self._bundle_template(payload.group_uid, payload.template_uid),
            expected_revision=payload.expected_revision,
            draft_id=payload.draft_id,
        )
        response = GamePrimitiveBundleApplicationResponse(
            request_id=payload.request_id, data=result
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    async def handle_apply_game_primitive_bundle(
        self, payload: ApplyGamePrimitiveBundlePayload
    ) -> None:
        """Apply a stored bundle through rollback-safe mutation orchestration.

        ``payload`` identifies the stored template and target draft and carries the
        expected revision, action, and correlation ID. A valid, collision-free apply
        persists the bundle in a new or existing draft and queues its application and
        operation-done responses. Invalid input, rejection, or pre-commit failure
        restores the primitive root; post-commit transport failure preserves the
        commit and attempts to report an indeterminate result.

        """
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: GamePrimitiveBundleService.apply(
                self.scene,
                self._bundle_template(payload.group_uid, payload.template_uid),
                expected_revision=payload.expected_revision,
                draft_id=payload.draft_id,
            ),
            self._queue_bundle_application,
        )

    def _queue_bundle_application(self, result, request_id: str) -> None:
        response = GamePrimitiveBundleApplicationResponse(
            request_id=request_id, data=result
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))
