"""Pydantic schema models and default shapes for the Game Primitives store."""

from __future__ import annotations

from typing import Any, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.definitions import PrimitiveDefinitions
from talemate.game.primitives.ledger import LedgerEntry

#: Key in ``Scene.game_state.variables`` that stores the primitive root payload.
GAME_PRIMITIVES_KEY = "game_primitives"

#: Latest persisted schema version supported by this runtime store.
CURRENT_VERSION = 1

#: Default maximum number of ledger entries retained by ``PrimitiveStore``.
DEFAULT_LEDGER_LIMIT = 500

#: Primitive collection names created in each new anchor payload.
ANCHOR_PRIMITIVE_KINDS = (
    "meters",
    "clocks",
    "decks",
    "roll_tables",
    "attributes",
    "modifiers",
)


class PrimitivePayload(pydantic.RootModel[dict[str, pydantic.JsonValue]]):
    """Validate the JSON object stored for one primitive instance.

    A primitive instance is runtime data stored under a primitive kind and
    identifier within an anchor payload. The schema deliberately leaves object
    keys and value shapes open so each primitive kind can define its own payload.

    Attributes:
        root: String-keyed object whose values are valid JSON values.

    Invariants:
        The root value is an object rather than another JSON value, nested values
        are JSON-compatible, and non-finite numbers are rejected. Existing model
        instances are revalidated when used as input to another Pydantic model.

    """

    model_config = pydantic.ConfigDict(
        allow_inf_nan=False, revalidate_instances="always"
    )


class AnchorPayload(pydantic.BaseModel):
    """Persist primitive instances and metadata owned by one anchor.

    An anchor is a stable ``<kind>:<id>`` address for a scene, character, object,
    relationship, or other owner of runtime primitive data. The anchor address is
    the key in ``PrimitiveRootPayload.anchors`` and is not repeated in this model.

    Attributes:
        tags: User-defined labels associated with the anchor.
        primitives: Primitive payloads grouped first by canonical primitive kind
            and then by canonical primitive identifier. A new anchor initializes
            an empty collection for every kind in ``ANCHOR_PRIMITIVE_KINDS``.
        meta: JSON-compatible metadata associated with the anchor rather than a
            specific primitive instance.

    Invariants:
        Primitive kind and identifier keys are non-empty, stripped of surrounding
        whitespace, contain no ``/``, and remain unique after normalization.
        Unknown model fields and non-finite numeric values are rejected. Mutable
        defaults are independent for every model instance.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )

    tags: list[str] = pydantic.Field(default_factory=list)
    primitives: dict[str, dict[str, dict[str, pydantic.JsonValue]]] = pydantic.Field(
        default_factory=lambda: {kind: {} for kind in ANCHOR_PRIMITIVE_KINDS}
    )
    meta: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("primitives")
    @classmethod
    def validate_primitive_keys(
        cls, value: dict[str, dict[str, dict[str, pydantic.JsonValue]]]
    ) -> dict[str, dict[str, dict[str, pydantic.JsonValue]]]:
        """Normalize primitive kind and identifier keys for anchor storage.

        Args:
            value: Primitive payloads grouped by input kind and identifier keys.

        Returns:
            A new nested mapping whose kind and identifier keys are stripped of
            surrounding whitespace.

        Raises:
            ValueError: If any kind or identifier key is empty after trimming,
                contains ``/``, or duplicates a sibling key after normalization.

        Invariants:
            Every returned kind and identifier key is a valid primitive path
            segment. Primitive payload objects are preserved unchanged.

        """
        normalized: dict[str, dict[str, dict[str, pydantic.JsonValue]]] = {}
        original_kinds: dict[str, str] = {}
        for primitive_kind, primitive_map in value.items():
            canonical_kind = PrimitiveRef.validate_path_segment(primitive_kind)
            if canonical_kind in normalized:
                raise ValueError(
                    "Duplicate primitive kind keys normalize to "
                    f"'{canonical_kind}': '{original_kinds[canonical_kind]}' and "
                    f"'{primitive_kind}'"
                )

            normalized_map: dict[str, dict[str, pydantic.JsonValue]] = {}
            original_ids: dict[str, str] = {}
            for primitive_id, payload in primitive_map.items():
                canonical_id = PrimitiveRef.validate_path_segment(primitive_id)
                if canonical_id in normalized_map:
                    raise ValueError(
                        "Duplicate primitive ids normalize to "
                        f"'{canonical_id}' in kind '{canonical_kind}': "
                        f"'{original_ids[canonical_id]}' and '{primitive_id}'"
                    )
                normalized_map[canonical_id] = payload
                original_ids[canonical_id] = primitive_id
            normalized[canonical_kind] = normalized_map
            original_kinds[canonical_kind] = primitive_kind
        return normalized


class DraftValidation(pydantic.BaseModel):
    """Record the persisted validation outcome for one primitive draft.

    Attributes:
        ok: Whether the draft passed its most recent validation.
        errors: Validation failures that prevent the draft from being committed.
        warnings: Non-fatal validation findings associated with the draft.

    Invariants:
        Unknown fields are rejected, and each findings collection is independent
        for every model instance.

    """

    model_config = pydantic.ConfigDict(extra="forbid")

    ok: bool = False
    errors: list[str] = pydantic.Field(default_factory=list)
    warnings: list[str] = pydantic.Field(default_factory=list)


class PrimitiveDraft(pydantic.BaseModel):
    """Stage isolated primitive definitions and anchors for validated commit.

    Attributes:
        id: Canonical non-empty draft identifier used as the root draft-map key.
        status: Authoring lifecycle state: ``draft``, ``validated``, or
            ``committed``.
        created_by: Non-empty identifier for the draft's creator; defaults to
            ``llm``.
        definitions: Reusable primitive definitions isolated from committed state.
        anchors: Canonically keyed anchor payloads isolated from committed state.
        validation: Persisted result of the draft's most recent validation.

    Invariants:
        The identifier is a valid primitive path segment. Definitions and anchors
        satisfy the same validation rules as their corresponding root payload
        fragments. Unknown fields and non-finite numeric values are rejected.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    status: Literal["draft", "validated", "committed"] = "draft"
    created_by: str = pydantic.Field(default="llm", min_length=1)
    definitions: PrimitiveDefinitions = pydantic.Field(
        default_factory=PrimitiveDefinitions
    )
    anchors: dict[str, AnchorPayload] = pydantic.Field(default_factory=dict)
    validation: DraftValidation = pydantic.Field(default_factory=DraftValidation)

    @pydantic.model_validator(mode="after")
    def validate_identity(self) -> "PrimitiveDraft":
        """Normalize the draft identifier and validate staged root fragments.

        Returns:
            The draft with a canonical identifier, definitions, and anchor keys.

        Raises:
            ValueError: If the identifier is empty or contains ``/``.
            pydantic.ValidationError: If the staged definitions or anchors do not
                form valid primitive root fragments.

        Invariants:
            The returned draft can supply its definitions and anchors directly to
            ``PrimitiveRootPayload`` without further normalization.

        """
        self.id = PrimitiveRef.validate_path_segment(self.id)
        candidate = PrimitiveRootPayload(
            definitions=self.definitions,
            anchors=self.anchors,
        )
        self.definitions = candidate.definitions
        self.anchors = candidate.anchors
        return self


class PrimitiveRootPayload(pydantic.BaseModel):
    """Persist the complete Game Primitives state under ``game_state.variables``.

    Attributes:
        version: Persisted schema version, which must equal ``CURRENT_VERSION``.
        definitions: Reusable primitive definitions grouped by canonical kind and
            definition identifiers.
        anchors: Primitive instance payloads grouped by canonical anchor keys.
        runtime: JSON-compatible transient state owned by primitive runtimes.
        ledger: Ordered history of primitive mutations and outcomes.
        drafts: Isolated authoring drafts grouped by canonical draft identifiers.

    Invariants:
        Root fields reject unknown keys and non-finite numeric values. Anchor and
        draft map keys are canonical and unique; every draft key equals the
        contained draft's identifier. The persisted version is exactly the version
        supported by the running application.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )

    version: pydantic.StrictInt = CURRENT_VERSION
    definitions: PrimitiveDefinitions = pydantic.Field(
        default_factory=PrimitiveDefinitions
    )
    anchors: dict[str, AnchorPayload] = pydantic.Field(default_factory=dict)
    runtime: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    ledger: list[LedgerEntry] = pydantic.Field(default_factory=list)
    drafts: dict[str, PrimitiveDraft] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("drafts")
    @classmethod
    def validate_draft_keys(
        cls, value: dict[str, PrimitiveDraft]
    ) -> dict[str, PrimitiveDraft]:
        """Normalize draft keys and require each key to match its draft id.

        Args:
            value: Drafts indexed by their persisted map keys.

        Returns:
            A new mapping indexed by canonical draft identifiers.

        Raises:
            ValueError: If a key is empty, contains ``/``, duplicates another key
                after normalization, or differs from the contained draft's id.

        Invariants:
            Every returned key is canonical, unique, and equal to the ``id`` of
            its associated ``PrimitiveDraft``.

        """
        normalized = {}
        for key, draft in value.items():
            canonical = PrimitiveRef.validate_path_segment(key)
            if canonical in normalized:
                raise ValueError(f"Duplicate draft id: {canonical}")
            if draft.id != canonical:
                raise ValueError(f"Draft key '{canonical}' must match id '{draft.id}'")
            normalized[canonical] = draft
        return normalized

    @pydantic.field_validator("anchors")
    @classmethod
    def validate_anchor_keys(
        cls, value: dict[str, AnchorPayload]
    ) -> dict[str, AnchorPayload]:
        """Normalize root anchor keys to canonical ``<kind>:<id>`` addresses.

        Args:
            value: Anchor payloads indexed by input anchor reference strings.

        Returns:
            A new mapping indexed by the canonical string representation of each
            validated anchor reference.

        Raises:
            pydantic.ValidationError: If a key is not a supported anchor kind or
                violates anchor reference or relationship participant syntax.
            ValueError: If multiple input keys resolve to the same canonical
                anchor address.

        Invariants:
            Every returned key can be parsed as an ``AnchorRef`` and is unique in
            canonical form. Associated anchor payloads are preserved unchanged.

        """
        normalized: dict[str, AnchorPayload] = {}
        original_keys: dict[str, str] = {}
        for key, payload in value.items():
            canonical_key = AnchorRef.model_validate(key).key()
            if canonical_key in normalized:
                raise ValueError(
                    "Duplicate anchor keys normalize to "
                    f"'{canonical_key}': '{original_keys[canonical_key]}' and '{key}'"
                )
            normalized[canonical_key] = payload
            original_keys[canonical_key] = key
        return normalized

    @pydantic.field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        """Require persisted state to use the runtime's current schema version.

        Args:
            value: Strict integer schema version read from the primitive root.

        Returns:
            The unchanged version when it equals ``CURRENT_VERSION``.

        Raises:
            ValueError: If the version is not supported by the running
                application.

        """
        if value != CURRENT_VERSION:
            raise ValueError(
                f"Unsupported Game Primitives version {value}; "
                f"current version is {CURRENT_VERSION}"
            )
        return value


def default_anchor() -> dict[str, Any]:
    """Create the JSON-compatible storage shape for an empty anchor.

    Returns:
        A new dictionary containing empty ``tags`` and ``meta`` collections plus
        an empty primitive mapping for every kind in
        ``ANCHOR_PRIMITIVE_KINDS``. All mutable nested collections are independent
        from those returned by earlier calls.

    """
    return AnchorPayload().model_dump(mode="json")
