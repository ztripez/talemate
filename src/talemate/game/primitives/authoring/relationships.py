"""Atomic directional relationship authoring."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

from talemate.game.primitives.anchors import PrimitiveRef, relationship_anchor
from talemate.game.primitives.authoring.draft_store import PrimitiveDraftStore
from talemate.game.primitives.authoring.validator import PrimitiveDraftValidator
from talemate.game.primitives.constants import DEFAULT_LEDGER_LIMIT
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.schema import AnchorPayload
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot

if TYPE_CHECKING:
    from talemate.game.primitives.definitions import MeterPayload
    from talemate.tale_mate import Scene


class RelationshipAuthoringChange(Protocol):
    """Structural contract accepted from validated relationship transports."""

    operation: str
    dimension: "MeterPayload"
    dimension_id: str


class RelationshipAuthoringService:
    """Validate and atomically commit directional relationship edits."""

    def __init__(self) -> None:
        self.drafts = PrimitiveDraftStore()
        self.validator = PrimitiveDraftValidator()

    def author(
        self,
        scene: "Scene",
        source: str,
        target: str,
        change: RelationshipAuthoringChange,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Apply one validated relationship operation as an atomic committed draft."""
        snapshot = self.drafts.require_revision(scene, expected_revision)
        anchor = relationship_anchor(source, target)
        existing_drafts = snapshot.iter_drafts()
        draft_id = f"relationship-{uuid.uuid4().hex}"
        while draft_id in existing_drafts:
            draft_id = f"relationship-{uuid.uuid4().hex}"
        draft = PrimitiveDraft(id=draft_id, created_by="ui")

        if change.operation == "upsert_dimension":
            dimension = change.dimension
            ref = PrimitiveRef(anchor=anchor, kind="meters", id=dimension.id)
            staged_anchor = draft.anchors.setdefault(anchor.key(), AnchorPayload())
            staged_anchor.primitives.set_item(
                "meters", dimension.id, dimension.model_dump(mode="json")
            )
            if snapshot.get_primitive(ref) is not None:
                draft.replacements.primitives.append(ref.key())
        elif change.operation == "delete_dimension":
            ref = PrimitiveRef(anchor=anchor, kind="meters", id=change.dimension_id)
            if snapshot.get_primitive(ref) is None:
                raise PrimitiveStoreError(
                    f"Relationship dimension not found: {ref.key()}"
                )
            draft.deletions.primitives.append(ref.key())
        elif change.operation == "delete_edge":
            if snapshot.get_anchor(anchor) is None:
                raise PrimitiveStoreError(
                    f"Relationship edge not found: {anchor.key()}"
                )
            draft.deletions.anchors.append(anchor.key())
        else:  # pragma: no cover - strict discriminated transport prevents this
            raise ValueError(
                f"Unsupported relationship authoring operation: {change.operation}"
            )

        draft_root = snapshot.detached_root_model()
        draft_root.drafts[draft.id] = draft
        draft_snapshot = PrimitiveStoreSnapshot(draft_root)
        candidate, committed_draft = self.validator.committed_candidate(
            scene, draft_snapshot, draft
        )
        if anchor.key() in candidate.anchors:
            candidate_store = PrimitiveStore(
                candidate.model_dump(mode="json"), DEFAULT_LEDGER_LIMIT
            )
            RelationshipGraph().summary(scene, source, target, store=candidate_store)
        PrimitiveStore.for_scene(scene).replace_validated_root(candidate)
        return committed_draft
