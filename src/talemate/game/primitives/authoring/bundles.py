"""Capture and atomically apply authored Game Primitive bundles."""

from __future__ import annotations

import uuid
from typing import Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.containers import AnchorPayload, PrimitiveDefinitions
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot
from talemate.world_state.templates.game_primitive_bundle import GamePrimitiveBundle


class BundleSelection(pydantic.BaseModel):
    """Select authored definitions and complete exact anchors for capture.

    Attributes:
        definitions: Unique canonical ``kind/id`` definition references.
        anchors: Unique canonical exact-anchor references.

    Invariants:
        Unknown fields and coercion are rejected. Each reference is canonicalized,
        valid for its reference type, and unique within its collection.
    """

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    definitions: list[str] = pydantic.Field(default_factory=list)
    anchors: list[str] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("definitions")
    @classmethod
    def validate_definitions(cls, values: list[str]) -> list[str]:
        """Canonicalize and deduplicate selected definition references.

        Args:
            values: Definition references in ``kind/id`` form.

        Returns:
            Definition references with both path segments canonicalized.

        Raises:
            ValueError: A reference does not contain exactly one kind and identifier
                portion, a path segment is invalid, or canonical references repeat.

        """
        canonical = []
        for value in values:
            parts = value.split("/", 1)
            if len(parts) != 2:
                raise ValueError("Definition selection must be 'kind/id'")
            canonical.append(
                "/".join(PrimitiveRef.validate_path_segment(v) for v in parts)
            )
        if len(canonical) != len(set(canonical)):
            raise ValueError("Duplicate definition selection")
        return canonical

    @pydantic.field_validator("anchors")
    @classmethod
    def validate_anchors(cls, values: list[str]) -> list[str]:
        """Canonicalize and deduplicate selected exact-anchor references.

        Args:
            values: Exact-anchor references accepted by :class:`AnchorRef`.

        Returns:
            Canonical anchor keys derived from the supplied references.

        Raises:
            ValueError: An anchor reference is invalid or canonical references repeat.

        """
        canonical = [AnchorRef.parse(value).key() for value in values]
        if len(canonical) != len(set(canonical)):
            raise ValueError("Duplicate anchor selection")
        return canonical


class BundleCollision(pydantic.BaseModel):
    """Describe one exact resource conflict blocking bundle application.

    Attributes:
        resource: Resource category that conflicts, either definition or anchor.
        ref: Canonical definition or exact-anchor reference.
        location: Existing store area containing the conflicting resource.

    Invariants:
        Instances are strict, immutable, and contain no unknown fields.
    """

    model_config = pydantic.ConfigDict(extra="forbid", strict=True, frozen=True)
    resource: Literal["definition", "anchor"]
    ref: str
    location: Literal["committed", "draft"]


class BundleApplicationResult(pydantic.BaseModel):
    """Return deterministic preview or successful application details.

    Attributes:
        applied: Whether the bundle was installed rather than only previewed.
        draft_id: Target draft identifier, or ``None`` for a new-draft preview.
        revision: Authoritative store revision associated with the result.
        definition_count: Number of definitions projected from the bundle.
        anchor_count: Number of exact anchors projected from the bundle.
        collisions: Deterministically discovered resources blocking application.

    Invariants:
        Unknown fields and coercion are rejected. Successful applications identify
        their target draft and contain no collisions.
    """

    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    applied: bool
    draft_id: str | None = None
    revision: str
    definition_count: int
    anchor_count: int
    collisions: list[BundleCollision] = pydantic.Field(default_factory=list)


class GamePrimitiveBundleService:
    """Project authored content and install bundles through isolated drafts."""

    @staticmethod
    def capture(
        scene,
        *,
        name: str,
        selection: BundleSelection,
        source: Literal["committed", "draft"],
        expected_revision: str,
        draft_id: str | None = None,
    ) -> GamePrimitiveBundle:
        """Capture selected authored resources as an independent bundle template.

        Args:
            scene: Scene whose Game Primitive store supplies the authored resources.
            name: Display name assigned to the captured bundle.
            selection: Canonical definition and exact-anchor references to capture.
            source: Store area from which to capture committed or draft resources.
            expected_revision: Revision token that the store must currently have.
            draft_id: Draft identifier required for ``draft`` source and forbidden for
                ``committed`` source.

        Returns:
            A bundle containing deep-independent selected definitions and anchors.

        Raises:
            PrimitiveStoreError: The revision is stale, the source and draft identifier
                disagree, the draft does not exist, or a selected resource is absent.
            pydantic.ValidationError: Persisted draft or anchor data is invalid.

        Side Effects:
            Reads the scene's Game Primitive store without modifying scene state.

        """
        snapshot = GamePrimitiveBundleService._require_revision(
            scene, expected_revision
        )
        if source == "draft":
            if draft_id is None:
                raise PrimitiveStoreError("draft_id is required for draft capture")
            payload = snapshot.iter_drafts().get(draft_id)
            if payload is None:
                raise PrimitiveStoreError(f"Primitive draft not found: {draft_id}")
            draft = PrimitiveDraft.model_validate(payload)
            definitions = draft.definitions
            anchors = draft.anchors
        else:
            if draft_id is not None:
                raise PrimitiveStoreError("draft_id is invalid for committed capture")
            root = snapshot.detached_root_model()
            definitions = root.definitions
            anchors = root.anchors

        selected_definitions = PrimitiveDefinitions()
        for ref in selection.definitions:
            kind, definition_id = ref.split("/", 1)
            value = definitions.get(kind, {}).get(definition_id)
            if value is None:
                raise PrimitiveStoreError(f"Selected definition not found: {ref}")
            selected_definitions.set_item(kind, definition_id, value)
        selected_anchors = {}
        for ref in selection.anchors:
            value = anchors.get(ref)
            if value is None:
                raise PrimitiveStoreError(f"Selected anchor not found: {ref}")
            selected_anchors[ref] = AnchorPayload.model_validate(
                value.model_dump(mode="python")
            )
        return GamePrimitiveBundle(
            name=name, definitions=selected_definitions, anchors=selected_anchors
        )

    @staticmethod
    def preview(
        scene,
        bundle: GamePrimitiveBundle,
        *,
        expected_revision: str,
        draft_id: str | None = None,
    ) -> BundleApplicationResult:
        """Preview bundle installation against committed and draft resources.

        Args:
            scene: Scene whose Game Primitive store is checked for conflicts.
            bundle: Bundle whose definitions and anchors would be installed.
            expected_revision: Revision token that the store must currently have.
            draft_id: Existing non-committed draft to target, or ``None`` to preview
                installation into a new draft.

        Returns:
            A non-applied result containing resource counts and every collision.

        Raises:
            PrimitiveStoreError: The revision is stale, the requested draft is absent,
                or the requested draft is already committed.
            pydantic.ValidationError: Persisted draft data is invalid.

        Side Effects:
            Reads the scene's Game Primitive store without modifying scene state.

        """
        snapshot = GamePrimitiveBundleService._require_revision(
            scene, expected_revision
        )
        draft = GamePrimitiveBundleService._target_draft(snapshot, draft_id)
        collisions = GamePrimitiveBundleService._collisions(snapshot, draft, bundle)
        return BundleApplicationResult(
            applied=False,
            draft_id=draft_id,
            revision=expected_revision,
            definition_count=sum(len(values) for values in bundle.definitions.values()),
            anchor_count=len(bundle.anchors),
            collisions=collisions,
        )

    @staticmethod
    def apply(
        scene,
        bundle: GamePrimitiveBundle,
        *,
        expected_revision: str,
        draft_id: str | None = None,
    ) -> BundleApplicationResult:
        """Atomically install a collision-free bundle into an authoring draft.

        Args:
            scene: Scene whose Game Primitive store receives the bundle resources.
            bundle: Bundle containing definitions and exact anchors to install.
            expected_revision: Revision token that the store must currently have.
            draft_id: Existing non-committed target draft, or ``None`` to create one.

        Returns:
            An applied result with the target draft identifier, new store revision,
            installed resource counts, and no collisions.

        Raises:
            PrimitiveStoreError: The revision is stale, the target draft is absent or
                committed, bundle resources collide, or validated replacement fails.
            pydantic.ValidationError: Persisted or resulting draft data is invalid.

        Side Effects:
            Creates or updates a draft in the scene's Game Primitive store and replaces
            the validated primitive root, producing a new revision token.

        """
        snapshot = GamePrimitiveBundleService._require_revision(
            scene, expected_revision
        )
        draft = GamePrimitiveBundleService._target_draft(snapshot, draft_id)
        collisions = GamePrimitiveBundleService._collisions(snapshot, draft, bundle)
        if collisions:
            refs = ", ".join(collision.ref for collision in collisions)
            raise PrimitiveStoreError(f"Game Primitive bundle collisions: {refs}")
        if draft is None:
            draft = PrimitiveDraft(
                id=f"draft-{uuid.uuid4().hex}", created_by="template"
            )
        for kind, values in bundle.definitions.items():
            for definition_id, value in values.items():
                draft.definitions.set_item(kind, definition_id, value)
        draft.anchors.update(
            {key: value.model_copy(deep=True) for key, value in bundle.anchors.items()}
        )
        candidate = snapshot.detached_root_model()
        candidate.drafts[draft.id] = PrimitiveDraft.model_validate(draft)
        PrimitiveStore.for_scene(scene).replace_validated_root(candidate)
        revision = PrimitiveStore.read_snapshot_for_scene(scene).revision_token()
        return BundleApplicationResult(
            applied=True,
            draft_id=draft.id,
            revision=revision,
            definition_count=sum(len(values) for values in bundle.definitions.values()),
            anchor_count=len(bundle.anchors),
        )

    @staticmethod
    def _require_revision(scene, expected_revision: str) -> PrimitiveStoreSnapshot:
        snapshot = PrimitiveStore.read_snapshot_for_scene(scene)
        current = snapshot.revision_token()
        if current != expected_revision:
            raise PrimitiveStoreError(
                f"Stale Game Primitives revision: expected {expected_revision}, current {current}"
            )
        return snapshot

    @staticmethod
    def _target_draft(
        snapshot: PrimitiveStoreSnapshot, draft_id: str | None
    ) -> PrimitiveDraft | None:
        if draft_id is None:
            return None
        payload = snapshot.iter_drafts().get(draft_id)
        if payload is None:
            raise PrimitiveStoreError(f"Primitive draft not found: {draft_id}")
        draft = PrimitiveDraft.model_validate(payload)
        if draft.status == "committed":
            raise PrimitiveStoreError("Committed primitive draft cannot be modified")
        return draft

    @staticmethod
    def _collisions(snapshot, draft, bundle) -> list[BundleCollision]:
        collisions = []
        drafts = {
            draft_id: PrimitiveDraft.model_validate(payload)
            for draft_id, payload in snapshot.iter_drafts().items()
        }
        if draft is not None:
            drafts[draft.id] = draft
        for kind, values in bundle.definitions.items():
            committed = snapshot.iter_definitions(kind)
            for definition_id in values:
                ref = f"{kind}/{definition_id}"
                if definition_id in committed:
                    collisions.append(
                        BundleCollision(
                            resource="definition", ref=ref, location="committed"
                        )
                    )
                if any(
                    definition_id in item.definitions.get(kind, {})
                    for item in drafts.values()
                ):
                    collisions.append(
                        BundleCollision(
                            resource="definition", ref=ref, location="draft"
                        )
                    )
        committed_anchors = set(snapshot.iter_anchor_keys())
        for ref in bundle.anchors:
            if ref in committed_anchors:
                collisions.append(
                    BundleCollision(resource="anchor", ref=ref, location="committed")
                )
            if any(ref in item.anchors for item in drafts.values()):
                collisions.append(
                    BundleCollision(resource="anchor", ref=ref, location="draft")
                )
        return collisions


__all__ = [
    "BundleApplicationResult",
    "BundleCollision",
    "BundleSelection",
    "GamePrimitiveBundleService",
]
