"""Persistent isolated draft storage for primitive authoring."""

from __future__ import annotations

import copy
import uuid
from typing import TYPE_CHECKING

from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.schema import DraftValidation, PrimitiveDraft
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class PrimitiveDraftStore:
    """Persist isolated authoring drafts without changing committed primitives."""

    def create(
        self, scene: "Scene", draft_id: str | None = None, *, created_by: str = "llm"
    ) -> PrimitiveDraft:
        """Create and persist an empty primitive draft.

        Args:
            scene: Scene whose primitive root will store the draft.
            draft_id: Optional draft identifier. A unique ``draft-`` identifier is
                generated when no identifier is supplied.
            created_by: Non-empty identifier for the author or subsystem creating
                the draft.

        Returns:
            A validated deep copy of the newly persisted empty draft.

        Raises:
            PrimitiveStoreError: If the draft identifier already exists or the
                scene's primitive store is invalid.
            pydantic.ValidationError: If the identifier or author value cannot
                form a valid primitive draft.

        Side Effects:
            Adds the draft to the scene's persisted primitive root and normalizes
            the complete root schema.

        """
        store = PrimitiveStore.for_scene(scene)
        identifier = f"draft-{uuid.uuid4().hex}" if draft_id is None else draft_id
        draft = PrimitiveDraft(id=identifier, created_by=created_by)
        if draft.id in store.root["drafts"]:
            raise PrimitiveStoreError(f"Primitive draft already exists: {draft.id}")
        store.root["drafts"][draft.id] = draft.model_dump(mode="json")
        store.ensure_shape()
        return self.get(scene, draft.id)

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

        """
        store = PrimitiveStore.for_scene(scene)
        payload = store.root["drafts"].get(draft_id)
        if payload is None:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft_id}")
        return PrimitiveDraft.model_validate(copy.deepcopy(payload))

    def put(self, scene: "Scene", draft: PrimitiveDraft) -> PrimitiveDraft:
        """Replace an editable persisted draft and return a detached copy.

        Args:
            scene: Scene whose primitive root contains the draft.
            draft: Complete draft state to validate and persist.

        Returns:
            A validated deep copy of the newly persisted draft state.

        Raises:
            PrimitiveStoreError: If the draft does not exist, has already reached
                a terminal ``committed`` state, or the scene's
                primitive store is invalid.
            pydantic.ValidationError: If the supplied or persisted draft payload
                is invalid.

        Side Effects:
            Replaces the matching draft in the scene's persisted primitive root
            and normalizes the complete root schema.

        """
        store = PrimitiveStore.for_scene(scene)
        current = store.root["drafts"].get(draft.id)
        if current is None:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft.id}")
        current_draft = PrimitiveDraft.model_validate(current)
        if current_draft.status == "committed":
            raise PrimitiveStoreError(
                f"Primitive draft cannot be modified after {current_draft.status}"
            )
        normalized = PrimitiveDraft.model_validate(draft.model_dump(mode="python"))
        store.root["drafts"][draft.id] = normalized.model_dump(mode="json")
        store.ensure_shape()
        return self.get(scene, draft.id)

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
