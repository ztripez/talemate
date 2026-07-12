"""Revision-guarded UI editing operations for primitive drafts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.authoring.draft_store import PrimitiveDraftStore
from talemate.game.primitives.authoring.validator import PrimitiveDraftValidator
from talemate.game.primitives.constants import DEFAULT_LEDGER_LIMIT
from talemate.game.primitives.definitions import EditableDefinitionKind
from talemate.game.primitives.draft_schema import DraftDefinitionTarget, PrimitiveDraft
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.schema import (
    AnchorPayload,
)
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class PrimitiveDraftEditingService:
    """Apply strict revision-guarded changes to persisted primitive drafts.

    ``drafts`` owns atomic storage; ``validator`` owns candidate commit. Mutations
    require the exact root revision and reset prior validation.
    """

    def __init__(self) -> None:
        """Create the draft store and complete-candidate validator."""
        self.drafts = PrimitiveDraftStore()
        self.validator = PrimitiveDraftValidator()

    def create_draft(
        self,
        scene: "Scene",
        draft_id: str | None = None,
        *,
        created_by: str = "ui",
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Create an isolated draft against an exact root revision.

        Args:
            scene: Scene storing the draft.
            draft_id: Optional identifier; omission generates an identifier.
            created_by: Non-empty creator identifier.
            expected_revision: Exact root revision required before creation.

        Returns:
            Detached newly persisted empty draft.

        Raises:
            PrimitiveStoreError: If revision, identity, or root is invalid.
            pydantic.ValidationError: If draft fields are invalid.
        Side Effects:
            Atomically adds the draft to the primitive root.

        """
        return self.drafts.create(
            scene,
            draft_id,
            created_by=created_by,
            expected_revision=expected_revision,
        )

    def list_drafts(self, scene: "Scene") -> list[PrimitiveDraft]:
        """Return detached drafts in deterministic identifier order.

        Args:
            scene: Scene containing the drafts.

        Returns:
            Validated detached drafts sorted by identifier.

        Raises:
            PrimitiveStoreError: If persisted state is invalid.
        Side Effects:
            None.

        """
        return self.drafts.list(scene)

    def get_draft(self, scene: "Scene", draft_id: str) -> PrimitiveDraft:
        """Return one detached canonical draft.

        Args:
            scene: Scene containing the draft.
            draft_id: Exact persisted draft identifier.

        Returns:
            Validated copy whose mutation cannot alter scene state.

        Raises:
            PrimitiveStoreError: If the draft is missing or state is invalid.
        Side Effects:
            None.

        """
        return self.drafts.get(scene, draft_id)

    def delete_draft(
        self, scene: "Scene", draft_id: str, *, expected_revision: str
    ) -> None:
        """Delete a draft against an exact root revision.

        Args:
            scene: Scene containing the draft.
            draft_id: Exact persisted draft identifier.
            expected_revision: Exact revision before deletion.

        Returns:
            None.

        Raises:
            PrimitiveStoreError: If revision, draft, or root is invalid.
        Side Effects:
            Atomically removes the draft; failure preserves the root.

        """
        self.drafts.delete(scene, draft_id, expected_revision=expected_revision)

    def upsert_definition(
        self,
        scene: "Scene",
        draft_id: str,
        kind: EditableDefinitionKind,
        definition_id: str,
        value: dict,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Stage a typed definition create or intentional replacement.

        Args:
            scene: Scene containing the draft.
            draft_id: Target draft identifier.
            kind: Definition collection containing the target.
            definition_id: Canonical definition map identifier.
            value: Complete typed definition payload.
            expected_revision: Exact root revision required before mutation.

        Returns:
            Detached draft with deletion removed and replacement intent as needed.

        Raises:
            PrimitiveStoreError: If revision, draft state, or root is invalid.
            ValueError: If collection, identity, or value is invalid.
            pydantic.ValidationError: If typed validation fails.
        Side Effects:
            Atomically stages the value and resets validation.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id)
        committed = snapshot.get_definition(kind, definition_id)
        draft.definitions.set_item(kind, definition_id, value)
        target = DraftDefinitionTarget(kind=kind, id=definition_id)
        draft.deletions.definitions = [
            item for item in draft.deletions.definitions if item != target
        ]
        if committed is not None and target not in draft.replacements.definitions:
            draft.replacements.definitions.append(target)
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def upsert_anchor(
        self,
        scene: "Scene",
        draft_id: str,
        anchor: AnchorRef,
        *,
        tags: list[str],
        meta: dict,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Stage complete anchor metadata without replacing anchor primitives.

        Args:
            scene: Scene containing the draft.
            draft_id: Target draft identifier.
            anchor: Canonical anchor target.
            tags: Complete replacement tag list.
            meta: Complete replacement metadata mapping.
            expected_revision: Exact revision before mutation.

        Returns:
            Detached draft with deletion removed and replacement intent as needed.

        Raises:
            PrimitiveStoreError: If revision, draft state, or root is invalid.
            pydantic.ValidationError: If anchor data is invalid.
        Side Effects:
            Atomically stages metadata and resets validation; commit merges primitives.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id)
        anchor_key = anchor.key()
        payload = draft.anchors.setdefault(anchor_key, AnchorPayload())
        payload.tags = tags
        payload.meta = meta
        draft.deletions.anchors = [
            item for item in draft.deletions.anchors if item != anchor_key
        ]
        if (
            snapshot.get_anchor(anchor) is not None
            and anchor_key not in draft.replacements.anchors
        ):
            draft.replacements.anchors.append(anchor_key)
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def upsert_primitive(
        self,
        scene: "Scene",
        draft_id: str,
        ref: PrimitiveRef,
        value: dict,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Stage a typed primitive create or intentional replacement.

        Args:
            scene: Scene containing the draft.
            draft_id: Target draft identifier.
            ref: Canonical primitive target.
            value: Complete typed primitive payload.
            expected_revision: Exact revision before mutation.

        Returns:
            Detached draft with deletion removed and replacement intent as needed.

        Raises:
            PrimitiveStoreError: If revision, draft state, or root is invalid.
            ValueError: If reference and payload identities disagree.
            pydantic.ValidationError: If typed validation fails.
        Side Effects:
            Atomically stages only the target primitive and resets validation.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        candidate_store = PrimitiveStore(
            snapshot.detached_root_model().model_dump(mode="json"),
            DEFAULT_LEDGER_LIMIT,
        )
        payload = candidate_store._validate_primitive_payload(ref, value)
        draft = self._draft_from_snapshot(snapshot, draft_id)
        anchor = draft.anchors.setdefault(ref.anchor.key(), AnchorPayload())
        anchor.primitives.set_item(ref.kind, ref.id, payload)
        draft.deletions.primitives = [
            item for item in draft.deletions.primitives if item != ref.key()
        ]
        if (
            snapshot.get_primitive(ref) is not None
            and ref.key() not in draft.replacements.primitives
        ):
            draft.replacements.primitives.append(ref.key())
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def delete_definition(
        self,
        scene: "Scene",
        draft_id: str,
        kind: EditableDefinitionKind,
        definition_id: str,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Stage a definition tombstone or cancel a staged-only create.

        Args:
            scene: Scene containing the target draft.
            draft_id: Target draft identifier.
            kind: Definition collection containing the target.
            definition_id: Definition identifier to delete.
            expected_revision: Exact revision before mutation.

        Returns:
            Detached draft with replacement removed and a committed-state tombstone.

        Raises:
            PrimitiveStoreError: If revision, target, draft state, or root is invalid.
        Side Effects:
            Atomically stores a tombstone or removes a create and resets validation.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id)
        target = DraftDefinitionTarget(kind=kind, id=definition_id)
        staged = draft.definitions.get(target.kind, {})
        if snapshot.get_definition(target.kind, target.id) is None:
            if target.id not in staged:
                raise PrimitiveStoreError(
                    f"Primitive definition not found: {target.kind}/{target.id}"
                )
            del staged[target.id]
        else:
            staged.pop(target.id, None)
            if target not in draft.deletions.definitions:
                draft.deletions.definitions.append(target)
        draft.replacements.definitions = [
            item for item in draft.replacements.definitions if item != target
        ]
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def delete_anchor(
        self,
        scene: "Scene",
        draft_id: str,
        anchor: AnchorRef,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Stage an anchor tombstone or cancel a staged-only create.

        Args:
            scene: Scene containing the target draft.
            draft_id: Target draft identifier.
            anchor: Canonical anchor to delete.
            expected_revision: Exact revision before mutation.

        Returns:
            Detached draft without replacement markers and with an anchor tombstone.

        Raises:
            PrimitiveStoreError: If revision, target, draft state, or root is invalid.
        Side Effects:
            Stores a tombstone or removes a create without cascading references.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id)
        anchor_key = anchor.key()
        if snapshot.get_anchor(anchor) is None:
            if anchor_key not in draft.anchors:
                raise PrimitiveStoreError(f"Primitive anchor not found: {anchor_key}")
            del draft.anchors[anchor_key]
        else:
            draft.anchors.pop(anchor_key, None)
            if anchor_key not in draft.deletions.anchors:
                draft.deletions.anchors.append(anchor_key)
        draft.replacements.anchors = [
            item for item in draft.replacements.anchors if item != anchor_key
        ]
        draft.replacements.primitives = [
            text
            for text in draft.replacements.primitives
            if PrimitiveRef.parse(text).anchor.key() != anchor_key
        ]
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def delete_primitive(
        self,
        scene: "Scene",
        draft_id: str,
        ref: PrimitiveRef,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Stage a primitive tombstone or cancel a staged-only create.

        Args:
            scene: Scene containing the target draft.
            draft_id: Target draft identifier.
            ref: Canonical primitive to delete.
            expected_revision: Exact revision before mutation.

        Returns:
            Detached draft without replacement intent and with a primitive tombstone.

        Raises:
            PrimitiveStoreError: If revision, target, draft state, or root is invalid.
        Side Effects:
            Stores a tombstone or removes a create without removing parent or siblings.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id)
        staged_anchor = draft.anchors.get(ref.anchor.key())
        staged = staged_anchor.primitives.get(ref.kind, {}) if staged_anchor else {}
        if snapshot.get_primitive(ref) is None:
            if ref.id not in staged:
                raise PrimitiveStoreError(f"Primitive not found: {ref.key()}")
            del staged[ref.id]
        else:
            staged.pop(ref.id, None)
            if ref.key() not in draft.deletions.primitives:
                draft.deletions.primitives.append(ref.key())
        draft.replacements.primitives = [
            item for item in draft.replacements.primitives if item != ref.key()
        ]
        if (
            snapshot.get_primitive(ref) is None
            and staged_anchor is not None
            and not staged_anchor.tags
            and not staged_anchor.meta
            and not any(staged_anchor.primitives.values())
            and ref.anchor.key() not in draft.replacements.anchors
        ):
            draft.anchors.pop(ref.anchor.key(), None)
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def validate_draft(
        self, scene: "Scene", draft_id: str, *, expected_revision: str
    ) -> PrimitiveDraft:
        """Validate and persist a draft outcome against an exact revision.

        Args:
            scene: Scene containing the draft.
            draft_id: Target draft identifier.
            expected_revision: Exact revision before validation persistence.

        Returns:
            Detached draft with findings and status based on whether errors exist.

        Raises:
            PrimitiveStoreError: If revision, draft state, or root is invalid.
        Side Effects:
            Atomically stores findings without applying staged resources.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id, changed=False)
        draft.validation = self.validator.validate(scene, draft)
        draft.status = "validated" if draft.validation.ok else "draft"
        return self.drafts.put(scene, draft, expected_revision=expected_revision)

    def commit_draft(
        self, scene: "Scene", draft_id: str, *, expected_revision: str
    ) -> PrimitiveDraft:
        """Validate and atomically commit a draft against an exact revision.

        Args:
            scene: Scene receiving valid changes.
            draft_id: Target draft identifier.
            expected_revision: Exact revision before commit.

        Returns:
            Committed draft record with validation retained and staged data cleared.

        Raises:
            PrimitiveStoreError: If revision, draft state, or root is invalid.
            ValueError: If complete-candidate validation reports a blocking error.
            pydantic.ValidationError: If candidate construction is invalid.
        Side Effects:
            Installs the complete root on success; failure leaves state unchanged.

        """
        snapshot = self.drafts.require_revision(scene, expected_revision)
        draft = self._draft_from_snapshot(snapshot, draft_id, changed=False)
        return self.validator.commit(scene, draft)

    def _draft_from_snapshot(
        self,
        snapshot,
        draft_id: str,
        *,
        changed: bool = True,
    ) -> PrimitiveDraft:
        payload = snapshot.iter_drafts().get(draft_id)
        if payload is None:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft_id}")
        draft = PrimitiveDraft.model_validate(payload)
        if draft.status == "committed":
            raise PrimitiveStoreError(
                "Primitive draft cannot be modified after committed"
            )
        return self.drafts.mark_changed(draft) if changed else draft
