"""Anchor, instance, preview, and adjustment action handlers."""

from talemate.game.primitives.effects import Effect, apply_effect
from talemate.game.primitives.authoring.deletion_preview import (
    PrimitiveDeletionPreviewService,
)
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot

from .game_primitives_anchor_instance_requests import (
    AdjustGamePrimitivePayload,
    DeleteGamePrimitiveAnchorPayload,
    DeleteGamePrimitivePayload,
    PreviewDeleteGamePrimitiveAnchorPayload,
    PreviewDeleteGamePrimitivePayload,
    UpsertGamePrimitiveAnchorPayload,
    UpsertGamePrimitivePayload,
)
from .game_primitives_anchor_instance_responses import (
    GamePrimitiveCandidateCounts,
    GamePrimitiveCandidateSummary,
    GamePrimitiveDeletionPreviewResponse,
    GamePrimitiveDeletionTarget,
)


class GamePrimitivesAnchorInstanceHandlers:
    """Handle anchor and primitive draft edits, previews, and adjustments."""

    async def handle_upsert_game_primitive_anchor(
        self, payload: UpsertGamePrimitiveAnchorPayload
    ) -> None:
        """Stage an anchor upsert and queue the updated draft."""
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.upsert_anchor(
                self.scene,
                payload.draft_id,
                payload.anchor,
                tags=payload.value.tags,
                meta=payload.value.meta,
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_delete_game_primitive_anchor(
        self, payload: DeleteGamePrimitiveAnchorPayload
    ) -> None:
        """Stage an anchor deletion and queue the updated draft."""
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.delete_anchor(
                self.scene,
                payload.draft_id,
                payload.anchor,
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_upsert_game_primitive(
        self, payload: UpsertGamePrimitivePayload
    ) -> None:
        """Stage a primitive upsert and queue the updated draft."""
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.upsert_primitive(
                self.scene,
                payload.draft_id,
                payload.ref,
                payload.primitive.value.model_dump(mode="json"),
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_delete_game_primitive(
        self, payload: DeleteGamePrimitivePayload
    ) -> None:
        """Stage a primitive deletion and queue the updated draft."""
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.delete_primitive(
                self.scene,
                payload.draft_id,
                payload.ref,
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_adjust_game_primitive(
        self, payload: AdjustGamePrimitivePayload
    ) -> None:
        """Apply a revision-guarded meter or clock delta and queue a snapshot."""
        def mutate():
            actual_revision = self._primitive_revision()
            if actual_revision != payload.expected_revision:
                raise PrimitiveStoreError(
                    "Stale Game Primitives revision: expected "
                    f"{payload.expected_revision}, current {actual_revision}"
                )
            if PrimitiveStore.for_scene(self.scene).get_primitive(payload.ref) is None:
                raise ValueError(f"Primitive not found: {payload.ref.key()}")
            operation = "inc" if payload.delta > 0 else "dec"
            return apply_effect(
                PrimitiveStore.for_scene(self.scene),
                Effect(op=operation, target=payload.ref.key(), by=abs(payload.delta)),
                reason="Game Systems runtime adjustment",
            )

        await self._run_primitive_mutation(
            payload.request_id, payload.action, mutate, self._queue_snapshot
        )

    @staticmethod
    def _candidate_counts(
        snapshot: PrimitiveStoreSnapshot,
    ) -> GamePrimitiveCandidateCounts:
        """Return definition, anchor, and primitive counts for ``snapshot``."""
        root = snapshot.detached_root_model()
        return GamePrimitiveCandidateCounts(
            definitions=sum(len(values) for values in root.definitions.values()),
            anchors=len(root.anchors),
            primitives=sum(
                len(values)
                for anchor in root.anchors.values()
                for values in anchor.primitives.values()
            ),
        )

    def _queue_deletion_preview(
        self, request_id, revision, target_kind, target_ref, draft, before, candidate
    ) -> None:
        """Queue a correlated deletion preview without persisting the candidate."""
        response = GamePrimitiveDeletionPreviewResponse(
            request_id=request_id,
            revision=revision,
            target=GamePrimitiveDeletionTarget(kind=target_kind, ref=target_ref),
            draft=draft,
            validation=draft.validation,
            candidate=GamePrimitiveCandidateSummary(
                before=self._candidate_counts(before),
                after=self._candidate_counts(candidate),
                candidate_revision=candidate.revision_token(),
            ),
        )
        self.websocket_handler.queue_put(response.model_dump(mode="json"))

    async def handle_preview_delete_game_primitive_anchor(
        self, payload: PreviewDeleteGamePrimitiveAnchorPayload
    ) -> None:
        """Build and queue a non-persisted anchor-deletion preview."""
        preview = PrimitiveDeletionPreviewService().preview_anchor(
            self.scene, payload.anchor, expected_revision=payload.expected_revision
        )
        self._queue_deletion_preview(
            payload.request_id,
            payload.expected_revision,
            "anchor",
            payload.anchor.key(),
            preview.draft,
            preview.before,
            preview.candidate,
        )

    async def handle_preview_delete_game_primitive(
        self, payload: PreviewDeleteGamePrimitivePayload
    ) -> None:
        """Build and queue a non-persisted primitive-deletion preview."""
        preview = PrimitiveDeletionPreviewService().preview_primitive(
            self.scene, payload.ref, expected_revision=payload.expected_revision
        )
        self._queue_deletion_preview(
            payload.request_id,
            payload.expected_revision,
            "primitive",
            payload.ref.key(),
            preview.draft,
            preview.before,
            preview.candidate,
        )
