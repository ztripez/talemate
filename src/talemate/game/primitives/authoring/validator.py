"""Candidate construction and atomic commit for primitive authoring drafts."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pydantic

from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    relationship_participants,
)
from talemate.game.primitives.authoring.reference_validation import (
    PrimitiveReferenceValidator,
)
from talemate.game.primitives.authoring.runtime_validation import (
    PrimitiveRuntimeValidator,
)
from talemate.game.primitives.containers import PrimitiveDefinitions
from talemate.game.primitives.draft_schema import (
    DraftChangeTargets,
    DraftValidation,
    PrimitiveDraft,
)
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.schema import PrimitiveRootPayload
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class PrimitiveDraftValidator:
    """Build complete candidates, coordinate validation, and commit atomically."""

    def __init__(self) -> None:
        """Initialize focused reference and runtime validation collaborators."""
        self.references = PrimitiveReferenceValidator()
        self.runtime = PrimitiveRuntimeValidator()

    def validate(self, scene: "Scene", draft: PrimitiveDraft) -> DraftValidation:
        """Collect all validation errors and warnings for a primitive draft."""
        snapshot = PrimitiveStore.read_snapshot_for_scene(scene)
        return self.validate_candidate(scene, snapshot, draft)

    def validate_candidate(
        self,
        scene: "Scene",
        snapshot: PrimitiveStoreSnapshot,
        draft: PrimitiveDraft,
    ) -> DraftValidation:
        """Validate a detached draft against one already revision-checked snapshot.

        Args:
            scene: Scene supplying relationship participant identities.
            snapshot: Exact detached root represented by the caller's revision.
            draft: Detached change set to evaluate without persistence.

        Returns:
            Structured blocking errors and non-blocking warnings.

        Side Effects:
            None; neither ``draft`` nor its complete candidate is persisted.
        """
        errors: list[str] = []
        warnings: list[str] = []
        try:
            self._validate_collisions(snapshot, draft, errors)
            candidate = self.candidate_root(snapshot, draft)
            self._validate_relationship_characters(scene, candidate, errors)
            self.references.validate(candidate, errors, warnings)
            self.runtime.validate(candidate, errors)
        except (PrimitiveError, pydantic.ValidationError, ValueError) as exc:
            errors.append(str(exc))
        return DraftValidation(ok=not errors, errors=errors, warnings=warnings)

    @staticmethod
    def _validate_relationship_characters(
        scene: "Scene", root: PrimitiveRootPayload, errors: list[str]
    ) -> None:
        """Reject relationship anchors with missing scene participants."""
        character_names = set(scene.all_character_names)
        for anchor_key in sorted(root.anchors):
            anchor = AnchorRef.parse(anchor_key)
            if anchor.kind != "relationship":
                continue
            source, target = relationship_participants(anchor)
            missing = [name for name in (source, target) if name not in character_names]
            if missing:
                errors.append(
                    f"Relationship anchor '{anchor_key}' references missing "
                    f"character(s): {', '.join(missing)}"
                )

    def candidate_root(
        self, snapshot: PrimitiveStoreSnapshot, draft: PrimitiveDraft
    ) -> PrimitiveRootPayload:
        """Build a normalized committed-root candidate without persistence."""
        root = snapshot.detached_root_model().model_dump(mode="python")
        for target in draft.deletions.definitions:
            root["definitions"].get(target.kind, {}).pop(target.id, None)
        for primitive_text in draft.deletions.primitives:
            primitive = PrimitiveRef.parse(primitive_text)
            anchor = root["anchors"].get(primitive.anchor.key())
            if anchor is not None:
                anchor["primitives"].get(primitive.kind, {}).pop(primitive.id, None)
        for anchor_key in draft.deletions.anchors:
            root["anchors"].pop(anchor_key, None)
        for kind, values in draft.definitions.items():
            root["definitions"].setdefault(kind, {}).update(copy.deepcopy(values))
        replacement_anchors = set(draft.replacements.anchors)
        for anchor_key, staged in draft.anchors.items():
            staged_payload = staged.model_dump(mode="json")
            committed = root["anchors"].get(anchor_key)
            if committed is None:
                root["anchors"][anchor_key] = staged_payload
                continue
            if anchor_key in replacement_anchors:
                committed["tags"] = staged_payload["tags"]
                committed["meta"] = staged_payload["meta"]
            for kind, primitives in staged_payload["primitives"].items():
                committed["primitives"].setdefault(kind, {}).update(primitives)
        return PrimitiveRootPayload.model_validate(root)

    def commit(self, scene: "Scene", draft: PrimitiveDraft) -> PrimitiveDraft:
        """Revalidate and atomically commit a draft into the primitive root."""
        snapshot = PrimitiveStore.read_snapshot_for_scene(scene)
        candidate, committed_draft = self.committed_candidate(scene, snapshot, draft)
        PrimitiveStore.for_scene(scene).replace_validated_root(candidate)
        return committed_draft

    def committed_candidate(
        self,
        scene: "Scene",
        snapshot: PrimitiveStoreSnapshot,
        draft: PrimitiveDraft,
    ) -> tuple[PrimitiveRootPayload, PrimitiveDraft]:
        """Build a validated candidate with canonical committed draft evidence."""
        validation = self.validate_candidate(scene, snapshot, draft)
        draft.validation = validation
        if not validation.ok:
            draft.status = "draft"
            raise ValueError(
                "Primitive draft validation failed: " + "; ".join(validation.errors)
            )
        candidate = self.candidate_root(snapshot, draft)
        committed_draft = candidate.drafts[draft.id]
        committed_draft.status = "committed"
        committed_draft.validation = validation
        committed_draft.definitions = PrimitiveDefinitions()
        committed_draft.anchors = {}
        committed_draft.replacements = DraftChangeTargets()
        committed_draft.deletions = DraftChangeTargets()
        return candidate, committed_draft

    def _validate_collisions(
        self,
        snapshot: PrimitiveStoreSnapshot,
        draft: PrimitiveDraft,
        errors: list[str],
    ) -> None:
        root = snapshot.detached_root_model().model_dump(mode="json")
        replacements = {
            (target.kind, target.id) for target in draft.replacements.definitions
        }
        for kind, values in draft.definitions.items():
            committed = root["definitions"].get(kind, {})
            for definition_id in values.keys() & committed.keys():
                if (kind, definition_id) not in replacements:
                    errors.append(f"Definition already exists: {kind}/{definition_id}")
        for anchor_key in draft.anchors.keys() & root["anchors"].keys():
            if anchor_key not in draft.replacements.anchors and not any(
                primitives
                for key, anchor in draft.anchors.items()
                if key == anchor_key
                for primitives in anchor.primitives.values()
            ):
                errors.append(f"Anchor already exists: {anchor_key}")
        replacement_primitives = set(draft.replacements.primitives)
        for anchor_key, staged_anchor in draft.anchors.items():
            committed_anchor = root["anchors"].get(anchor_key)
            if committed_anchor is None:
                continue
            for kind, primitives in staged_anchor.primitives.items():
                committed_primitives = committed_anchor["primitives"].get(kind, {})
                for primitive_id in primitives.keys() & committed_primitives.keys():
                    ref = f"{anchor_key}/{kind}/{primitive_id}"
                    if ref not in replacement_primitives:
                        errors.append(f"Primitive already exists: {ref}")
        self._validate_change_targets(root, draft, errors)

    @staticmethod
    def _validate_change_targets(
        root: dict, draft: PrimitiveDraft, errors: list[str]
    ) -> None:
        """Require replacement and deletion targets to exist in committed state."""
        for target in [
            *draft.replacements.definitions,
            *draft.deletions.definitions,
        ]:
            if target.id not in root["definitions"].get(target.kind, {}):
                errors.append(f"Definition not found: {target.kind}/{target.id}")
        for anchor_key in [*draft.replacements.anchors, *draft.deletions.anchors]:
            if anchor_key not in root["anchors"]:
                errors.append(f"Anchor not found: {anchor_key}")
        for primitive_text in [
            *draft.replacements.primitives,
            *draft.deletions.primitives,
        ]:
            primitive = PrimitiveRef.parse(primitive_text)
            anchor = root["anchors"].get(primitive.anchor.key())
            if anchor is None or primitive.id not in anchor["primitives"].get(
                primitive.kind, {}
            ):
                errors.append(f"Primitive not found: {primitive.key()}")
