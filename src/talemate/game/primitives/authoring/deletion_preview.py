"""Detached deletion previews for committed primitive targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.authoring.draft_store import PrimitiveDraftStore
from talemate.game.primitives.authoring.validator import PrimitiveDraftValidator
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


@dataclass(frozen=True)
class PrimitiveDeletionPreview:
    """Validated detached deletion candidate and its source snapshot."""

    before: PrimitiveStoreSnapshot
    draft: PrimitiveDraft
    candidate: PrimitiveStoreSnapshot


class PrimitiveDeletionPreviewService:
    """Build deletion candidates without mutating persisted primitive state."""

    def __init__(self) -> None:
        self.drafts = PrimitiveDraftStore()
        self.validator = PrimitiveDraftValidator()

    def preview_anchor(
        self,
        scene: "Scene",
        anchor: AnchorRef,
        *,
        expected_revision: str,
    ) -> PrimitiveDeletionPreview:
        """Preview deletion of one committed anchor."""
        return self._preview(scene, anchor, expected_revision=expected_revision)

    def preview_primitive(
        self,
        scene: "Scene",
        ref: PrimitiveRef,
        *,
        expected_revision: str,
    ) -> PrimitiveDeletionPreview:
        """Preview deletion of one committed primitive."""
        return self._preview(scene, ref, expected_revision=expected_revision)

    def _preview(
        self,
        scene: "Scene",
        target: AnchorRef | PrimitiveRef,
        *,
        expected_revision: str,
    ) -> PrimitiveDeletionPreview:
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._setup_target(snapshot, target)
        draft.validation = self.validator.validate_candidate(scene, snapshot, draft)
        draft.status = "validated" if draft.validation.ok else "draft"
        candidate = self.validator.candidate_root(snapshot, draft)
        return PrimitiveDeletionPreview(
            before=snapshot,
            draft=draft,
            candidate=PrimitiveStoreSnapshot(candidate),
        )

    @overload
    def _setup_target(
        self, snapshot: PrimitiveStoreSnapshot, target: AnchorRef
    ) -> PrimitiveDraft: ...

    @overload
    def _setup_target(
        self, snapshot: PrimitiveStoreSnapshot, target: PrimitiveRef
    ) -> PrimitiveDraft: ...

    def _setup_target(
        self, snapshot: PrimitiveStoreSnapshot, target: AnchorRef | PrimitiveRef
    ) -> PrimitiveDraft:
        """Validate and stage exactly one typed preview target."""
        if isinstance(target, PrimitiveRef):
            if snapshot.get_primitive(target) is None:
                raise PrimitiveStoreError(f"Primitive not found: {target.key()}")
            draft = PrimitiveDraft(
                id="preview-delete-primitive", created_by="ui-preview"
            )
            draft.deletions.primitives.append(target.key())
            return draft

        if snapshot.get_anchor(target) is None:
            raise PrimitiveStoreError(f"Primitive anchor not found: {target.key()}")
        draft = PrimitiveDraft(id="preview-delete-anchor", created_by="ui-preview")
        draft.deletions.anchors.append(target.key())
        return draft
