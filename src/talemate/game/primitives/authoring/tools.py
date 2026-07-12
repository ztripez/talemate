"""Narrow validated mutation tools for primitive authoring drafts."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    relationship_anchor,
)
from talemate.game.primitives.authoring.draft_store import PrimitiveDraftStore
from talemate.game.primitives.authoring.schema import (
    CreateAnchorRequest,
    CreateAttributeSourceRequest,
    CreateClockRequest,
    CreateDeckRequest,
    CreateMeterRequest,
    CreateModifierRequest,
    CreateRelationshipRequest,
    CreateRollTableRequest,
    OptionalAnchoredDefinitionRequest,
)
from talemate.game.primitives.authoring.validator import PrimitiveDraftValidator
from talemate.game.primitives.deck_schema import DeckDefinition
from talemate.game.primitives.deck_state import DeckInstancePayload
from talemate.game.primitives.primitive_payloads import RollTableInstancePayload
from talemate.game.primitives.roll_tables import RollTableDefinition
from talemate.game.primitives.schema import (
    AnchorPayload,
)

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class PrimitiveAuthoringService:
    """Apply schema-validated mutations to isolated primitive drafts.

    Attributes:
        drafts: Persistent draft store used to load and save staged changes.
        validator: Draft validator used to inspect and commit staged changes.

    """

    def __init__(self):
        """Initialize independent draft storage and validation collaborators."""
        self.drafts = PrimitiveDraftStore()
        self.validator = PrimitiveDraftValidator()

    def create_draft(
        self,
        scene: "Scene",
        draft_id: str | None = None,
        *,
        created_by: str = "llm",
        expected_revision: str,
    ):
        """Create and persist an empty primitive authoring draft.

        Args:
            scene: Scene whose primitive root will store the draft.
            draft_id: Optional draft identifier; omitting the value generates a
                unique identifier.
            created_by: Non-empty creator identifier stored with the draft.
            expected_revision: Exact primitive-root revision required before writing.

        Returns:
            A detached validated copy of the newly persisted draft.

        Raises:
            PrimitiveStoreError: If a supplied revision is stale, the identifier
                already exists, or persisted primitive state is invalid.
            pydantic.ValidationError: If the requested draft is invalid.

        Side Effects:
            Adds an empty draft to the scene's persisted primitive root.

        """
        return self.drafts.create(
            scene,
            draft_id,
            created_by=created_by,
            expected_revision=expected_revision,
        )

    def create_anchor(self, scene: "Scene", request: CreateAnchorRequest):
        """Stage anchor tags and metadata in an existing draft.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated anchor request identifying the draft, anchor, tags,
                and metadata.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the draft is missing, terminal, or persisted
                primitive state is invalid.
            ValueError: If the anchor kind or identifier is invalid.

        Side Effects:
            Creates the staged anchor when absent, replaces its tags and metadata,
            clears stale draft validation, and persists the updated draft.

        """
        draft = self.drafts.mark_changed(self.drafts.get(scene, request.draft_id))
        anchor = AnchorRef(kind=request.kind, id=request.id)
        payload = draft.anchors.setdefault(anchor.key(), AnchorPayload())
        payload.tags = request.tags
        payload.meta = request.meta
        return self.drafts.put(
            scene,
            draft,
            expected_revision=request.expected_revision,
        )

    def create_meter(self, scene: "Scene", request: CreateMeterRequest):
        """Stage a unique bounded meter under a draft anchor.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated meter request containing the draft and anchor
                boundaries plus the canonical meter fields.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the anchor reference is invalid or the draft anchor
                already contains the meter identifier.

        Side Effects:
            Stages the meter, clears stale validation, and persists the draft.

        """
        return self._set_primitive(
            scene,
            request.draft_id,
            request.anchor,
            "meters",
            request.id,
            request.canonical_payload,
            expected_revision=request.expected_revision,
        )

    def create_clock(self, scene: "Scene", request: CreateClockRequest):
        """Stage a unique progress clock under a draft anchor.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated clock request containing the draft and anchor
                boundaries plus canonical clock fields.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the anchor reference is invalid or the draft anchor
                already contains the clock identifier.

        Side Effects:
            Stages the clock, clears stale validation, and persists the draft.

        """
        return self._set_primitive(
            scene,
            request.draft_id,
            request.anchor,
            "clocks",
            request.id,
            request.canonical_payload,
            expected_revision=request.expected_revision,
        )

    def create_deck(self, scene: "Scene", request: CreateDeckRequest):
        """Stage a unique reusable deck definition in a draft.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated deck request containing canonical deck fields.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the draft already contains the deck identifier.

        Side Effects:
            Stages the deck definition, clears stale validation, and persists the
            draft.

        """
        definition = DeckDefinition.model_validate(request.canonical_payload)
        return self._set_optional_anchored_definition(
            scene,
            "decks",
            request,
            lambda ref: DeckInstancePayload.create(definition, ref).model_dump(
                mode="json"
            ),
        )

    def create_roll_table(self, scene: "Scene", request: CreateRollTableRequest):
        """Stage a unique reusable roll-table definition in a draft.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated request containing canonical roll-table fields.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the draft already contains the roll-table identifier.

        Side Effects:
            Stages the roll-table definition, clears stale validation, and
            persists the draft.

        """
        definition = RollTableDefinition.model_validate(request.canonical_payload)
        return self._set_optional_anchored_definition(
            scene,
            "roll_tables",
            request,
            lambda _ref: RollTableInstancePayload(definition=definition.id).model_dump(
                mode="json"
            ),
        )

    def create_relationship(self, scene: "Scene", request: CreateRelationshipRequest):
        """Stage a unique directional relationship anchor in a draft.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated relationship request containing source, target,
                dimension meters, and tags.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the relationship anchor reference is invalid or the
                draft already contains the directional relationship.

        Side Effects:
            Creates a staged relationship anchor and its meter dimensions, clears
            stale validation, and persists the draft.

        """
        anchor = relationship_anchor(request.source, request.target)
        draft = self.drafts.get(scene, request.draft_id)
        self._reject_duplicate(draft.anchors, "relationship anchor", anchor.key())
        draft = self.drafts.mark_changed(draft)
        payload = AnchorPayload(tags=request.tags)
        payload.primitives.set_collection(
            "meters",
            {
                dimension.id: dimension.model_dump(mode="json")
                for dimension in request.dimensions
            },
        )
        draft.anchors[anchor.key()] = payload
        return self.drafts.put(
            scene,
            draft,
            expected_revision=request.expected_revision,
        )

    def create_modifier(self, scene: "Scene", request: CreateModifierRequest):
        """Stage a unique reusable roll modifier in a draft.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated modifier request converted to canonical modifier
                fields before storage.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the draft already contains the modifier identifier.
            pydantic.ValidationError: If canonical modifier conversion fails.

        Side Effects:
            Stages the modifier definition, clears stale validation, and persists
            the draft.

        """
        return self._set_definition(
            scene,
            request.draft_id,
            "modifiers",
            "modifier",
            request.id,
            request.canonical_payload,
            expected_revision=request.expected_revision,
        )

    def create_attribute_source(
        self, scene: "Scene", request: CreateAttributeSourceRequest
    ):
        """Stage a unique attribute source under a draft anchor.

        Args:
            scene: Scene containing the target primitive draft.
            request: Validated attribute source request containing draft and anchor
                boundaries plus canonical source fields.

        Returns:
            A detached copy of the updated persisted draft.

        Raises:
            PrimitiveStoreError: If the target draft cannot be edited.
            ValueError: If the anchor reference is invalid or the draft anchor
                already contains the attribute identifier.

        Side Effects:
            Stages the attribute source, clears stale validation, and persists the
            draft.

        """
        return self._set_primitive(
            scene,
            request.draft_id,
            request.anchor,
            "attributes",
            request.id,
            request.canonical_payload,
            expected_revision=request.expected_revision,
        )

    def validate_draft(
        self,
        scene: "Scene",
        draft_id: str,
        *,
        expected_revision: str,
    ):
        """Validate a persisted draft and save its latest validation outcome.

        Args:
            scene: Scene containing committed primitive state and the target draft.
            draft_id: Identifier of the persisted draft to validate.
            expected_revision: Exact revision required before persisting validation.

        Returns:
            A detached copy of the draft with its validation outcome and lifecycle
            status updated.

        Raises:
            PrimitiveStoreError: If a supplied revision is stale, the draft is
                missing or terminal, or persisted primitive state is invalid.

        Side Effects:
            Persists validation errors and warnings and sets the draft status to
            ``validated`` on success or ``draft`` on failure.

        """
        draft = self.drafts.get(scene, draft_id)
        draft.validation = self.validator.validate(scene, draft)
        draft.status = "validated" if draft.validation.ok else "draft"
        return self.drafts.put(
            scene,
            draft,
            expected_revision=expected_revision,
        )

    def commit_draft(
        self,
        scene: "Scene",
        draft_id: str,
        *,
        expected_revision: str,
    ):
        """Revalidate and atomically commit a persisted primitive draft.

        Args:
            scene: Scene whose committed primitive root receives staged content.
            draft_id: Identifier of the persisted draft to commit.
            expected_revision: Exact revision required before commit.

        Returns:
            The committed draft record with staged definitions and anchors cleared.

        Raises:
            PrimitiveStoreError: If the draft is missing or primitive state is
                invalid.
            ValueError: If draft validation reports blocking errors.
            pydantic.ValidationError: If candidate root validation fails.

        Side Effects:
            On success, atomically installs the complete validated candidate,
            including explicit replacements and deletions, and marks the persisted
            draft committed. Stale revisions, validation failures, and replacement
            failures leave persisted state unchanged; failed validation mutates only
            the detached draft used by this call.

        """
        self.drafts.require_revision(scene, expected_revision)
        draft = self.drafts.get(scene, draft_id)
        try:
            return self.validator.commit(scene, draft)
        except ValueError:
            raise

    def _set_primitive(
        self,
        scene,
        draft_id,
        anchor,
        kind,
        primitive_id,
        primitive_payload,
        *,
        expected_revision: str,
    ):
        draft = self.drafts.get(scene, draft_id)
        anchor_ref = AnchorRef.parse(anchor)
        existing_anchor = draft.anchors.get(anchor_ref.key())
        existing = existing_anchor.primitives.get(kind, {}) if existing_anchor else {}
        self._reject_duplicate(existing, kind[:-1], primitive_id)
        draft = self.drafts.mark_changed(draft)
        payload = draft.anchors.setdefault(anchor_ref.key(), AnchorPayload())
        payload.primitives.set_item(kind, primitive_id, primitive_payload)
        return self.drafts.put(
            scene,
            draft,
            expected_revision=expected_revision,
        )

    def _set_definition(
        self,
        scene,
        draft_id,
        kind,
        category,
        definition_id,
        definition_payload,
        *,
        instance: tuple[PrimitiveRef, dict] | None = None,
        expected_revision: str,
    ):
        draft = self.drafts.get(scene, draft_id)
        definitions = draft.definitions.get(kind, {})
        self._reject_duplicate(definitions, category, definition_id)
        if instance is not None:
            instance_ref, _ = instance
            anchor = draft.anchors.get(instance_ref.anchor.key())
            primitives = anchor.primitives.get(kind, {}) if anchor else {}
            self._reject_duplicate(primitives, category, instance_ref.id)
        draft = self.drafts.mark_changed(draft)
        draft.definitions.set_item(kind, definition_id, definition_payload)
        if instance is not None:
            instance_ref, payload = instance
            anchor = draft.anchors.setdefault(
                instance_ref.anchor.key(), AnchorPayload()
            )
            anchor.primitives.set_item(kind, instance_ref.id, payload)
        return self.drafts.put(
            scene,
            draft,
            expected_revision=expected_revision,
        )

    def _set_optional_anchored_definition(
        self,
        scene,
        kind: str,
        request: OptionalAnchoredDefinitionRequest,
        instance_payload_factory: Callable[[PrimitiveRef], dict],
    ):
        instance = None
        if request.anchor is not None:
            instance_ref = PrimitiveRef(
                anchor=AnchorRef.parse(request.anchor),
                kind=kind,
                id=request.instance_id or request.id,
            )
            instance = (instance_ref, instance_payload_factory(instance_ref))
        return self._set_definition(
            scene,
            request.draft_id,
            kind,
            kind.replace("_", " ")[:-1],
            request.id,
            request.canonical_payload,
            instance=instance,
            expected_revision=request.expected_revision,
        )

    @staticmethod
    def _reject_duplicate(values, category: str, value_id: str) -> None:
        if value_id in values:
            raise ValueError(f"Duplicate staged {category} id: {value_id}")
