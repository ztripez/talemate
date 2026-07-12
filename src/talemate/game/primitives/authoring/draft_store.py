"""Persistent isolated draft storage for primitive authoring."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.draft_schema import DraftValidation, PrimitiveDraft
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class PrimitiveDraftStore:
    """Persist revision-guarded drafts through atomic primitive-root replacement.

    Attributes:
        PrimitiveDraftStore has no instance attributes; each operation reads or
        replaces the primitive root owned by the supplied scene.

    Invariants:
        Read results are detached from scene state. Every mutation requires an
        exact pre-mutation revision and installs one fully validated candidate
        root, so stale or invalid writes do not partially alter persisted state.

    """

    def create(
        self,
        scene: "Scene",
        draft_id: str | None = None,
        *,
        created_by: str = "llm",
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Create and persist an empty primitive draft.

        Args:
            scene: Scene whose primitive root will store the draft.
            draft_id: Optional draft identifier. A unique ``draft-`` identifier is
                generated when no identifier is supplied.
            created_by: Non-empty identifier for the author or subsystem creating
                the draft.
            expected_revision: Exact revision token for the primitive root before
                creation.

        Returns:
            A validated deep copy of the newly persisted empty draft.

        Raises:
            PrimitiveStoreError: If the revision is stale, the draft identifier
                already exists, or the scene's primitive store is invalid.
            pydantic.ValidationError: If the identifier or author value cannot
                form a valid primitive draft.

        Side Effects:
            Adds the draft to the scene's persisted primitive root and normalizes
            the complete root schema.

        """
        snapshot = self.require_revision(scene, expected_revision)
        identifier = f"draft-{uuid.uuid4().hex}" if draft_id is None else draft_id
        draft = PrimitiveDraft(id=identifier, created_by=created_by)
        candidate = snapshot.detached_root_model()
        if draft.id in candidate.drafts:
            raise PrimitiveStoreError(f"Primitive draft already exists: {draft.id}")
        candidate.drafts[draft.id] = draft
        PrimitiveStore.for_scene(scene).replace_validated_root(candidate)
        return draft.model_copy(deep=True)

    def get(self, scene: "Scene", draft_id: str) -> PrimitiveDraft:
        """Return a validated deep copy of one persisted draft.

        Args:
            scene: Scene whose primitive root contains the draft.
            draft_id: Exact persisted draft identifier to retrieve.

        Returns:
            A detached validated draft whose mutation does not change scene state.

        Raises:
            PrimitiveStoreError: If the draft does not exist or the scene's
                primitive store is invalid.
            pydantic.ValidationError: If the persisted draft payload is invalid.

        Side Effects:
            None; the returned draft is detached from persisted state.

        """
        payload = (
            PrimitiveStore.read_snapshot_for_scene(scene).iter_drafts().get(draft_id)
        )
        if payload is None:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft_id}")
        return PrimitiveDraft.model_validate(payload)

    def list(self, scene: "Scene") -> list[PrimitiveDraft]:
        """Return detached drafts sorted by canonical identifier.

        Args:
            scene: Scene whose primitive root contains the drafts.

        Returns:
            Validated detached draft copies in ascending identifier order.

        Raises:
            PrimitiveStoreError: If the scene's primitive root is malformed.
            pydantic.ValidationError: If a persisted draft payload is invalid.

        Side Effects:
            None; reading does not initialize or mutate primitive state.

        """
        drafts = PrimitiveStore.read_snapshot_for_scene(scene).iter_drafts()
        return [
            PrimitiveDraft.model_validate(payload)
            for _, payload in sorted(drafts.items())
        ]

    def delete(self, scene: "Scene", draft_id: str, *, expected_revision: str) -> None:
        """Delete one persisted draft through atomic root replacement.

        Args:
            scene: Scene whose primitive root contains the draft.
            draft_id: Exact persisted draft identifier to remove.
            expected_revision: Exact revision token for the root before deletion.

        Returns:
            None.

        Raises:
            PrimitiveStoreError: If the revision is stale, the draft does not
                exist, or persisted primitive state is invalid.

        Side Effects:
            Removes the draft by installing one validated candidate root. Failure
            leaves the persisted root unchanged.

        """
        snapshot = self.require_revision(scene, expected_revision)
        candidate = snapshot.detached_root_model()
        if draft_id not in candidate.drafts:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft_id}")
        del candidate.drafts[draft_id]
        PrimitiveStore.for_scene(scene).replace_validated_root(candidate)

    def put(
        self,
        scene: "Scene",
        draft: PrimitiveDraft,
        *,
        expected_revision: str,
    ) -> PrimitiveDraft:
        """Replace an editable persisted draft and return a detached copy.

        Args:
            scene: Scene whose primitive root contains the draft.
            draft: Complete draft state to validate and persist.
            expected_revision: Exact revision token for the root before replacement.

        Returns:
            A validated deep copy of the newly persisted draft state.

        Raises:
            PrimitiveStoreError: If the revision is stale, the draft does not
                exist, has already reached terminal ``committed`` state, or the
                scene's primitive store is invalid.
            pydantic.ValidationError: If the supplied or persisted draft payload
                is invalid.

        Side Effects:
            Replaces the matching draft in the scene's persisted primitive root
            and normalizes the complete root schema.

        """
        snapshot = self.require_revision(scene, expected_revision)
        candidate = snapshot.detached_root_model()
        current = candidate.drafts.get(draft.id)
        if current is None:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft.id}")
        if current.status == "committed":
            raise PrimitiveStoreError(
                f"Primitive draft cannot be modified after {current.status}"
            )
        normalized = PrimitiveDraft.model_validate(draft.model_dump(mode="python"))
        candidate.drafts[draft.id] = normalized
        PrimitiveStore.for_scene(scene).replace_validated_root(candidate)
        return normalized.model_copy(deep=True)

    @staticmethod
    def require_revision(
        scene: "Scene", expected_revision: str
    ) -> PrimitiveStoreSnapshot:
        """Read a snapshot only when its revision matches the caller's token.

        Args:
            scene: Scene whose detached primitive snapshot is required.
            expected_revision: Exact canonical revision token expected by the
                caller.

        Returns:
            A detached, read-only primitive snapshot at ``expected_revision``.

        Raises:
            PrimitiveStoreError: If persisted primitive state is invalid or its
                current revision differs from ``expected_revision``.

        Side Effects:
            None; a mismatch is detected before any candidate mutation.

        """
        snapshot = PrimitiveStore.read_snapshot_for_scene(scene)
        actual_revision = snapshot.revision_token()
        if actual_revision != expected_revision:
            raise PrimitiveStoreError(
                "Stale Game Primitives revision: expected "
                f"{expected_revision}, current {actual_revision}"
            )
        return snapshot

    def mark_changed(self, draft: PrimitiveDraft) -> PrimitiveDraft:
        """Reset lifecycle and validation state after a draft changes.

        Args:
            draft: Mutable draft whose previous validation is now stale.

        Returns:
            The same draft object with ``status`` set to ``draft`` and an empty
            validation result.

        Side Effects:
            Mutates the supplied draft object in memory; the method does not
            persist the draft.

        """
        draft.status = "draft"
        draft.validation = DraftValidation()
        return draft
