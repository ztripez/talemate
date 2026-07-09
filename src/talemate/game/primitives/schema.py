"""Pydantic schema models and default shapes for the Game Primitives store."""

from __future__ import annotations

from typing import Any

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.ledger import LedgerEntry

#: Key in ``Scene.game_state.variables`` that stores the primitive root payload.
GAME_PRIMITIVES_KEY = "game_primitives"

#: Latest persisted schema version supported by this runtime store.
CURRENT_VERSION = 1

#: Default maximum number of ledger entries retained by ``PrimitiveStore``.
DEFAULT_LEDGER_LIMIT = 500

#: Definition collection names stored under the root ``definitions`` container.
DEFINITION_KINDS = (
    "decks",
    "roll_tables",
    "meters",
    "clocks",
    "relationship_models",
    "modifiers",
    "attribute_sources",
    "adventures",
)

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
    """JSON object payload for one primitive instance.

    Attributes:
        root: Dictionary whose values are recursively JSON-compatible values.
    """

    model_config = pydantic.ConfigDict(
        allow_inf_nan=False, revalidate_instances="always"
    )


class AnchorPayload(pydantic.BaseModel):
    """Persisted payload for one anchor namespace.

    Attributes:
        tags: Anchor tags used by primitive-aware conditions and filters.
        primitives: Mapping of primitive kind to primitive id to JSON payload.
        meta: JSON-compatible metadata for the anchor namespace.
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
        """Validate primitive kind and id map keys.

        Args:
            value: Mapping from primitive kind to primitive id to payload.

        Returns:
            Mapping with normalized primitive kind and id keys.

        Raises:
            ValueError: If a primitive kind or id is not a valid path segment.
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


class PrimitiveRootPayload(pydantic.BaseModel):
    """Persisted root payload stored under ``game_state.variables``.

    Attributes:
        version: Persisted schema version. Only ``CURRENT_VERSION`` is accepted.
        definitions: Authored reusable primitive definitions grouped by kind.
        anchors: Runtime primitive payloads grouped by canonical anchor key.
        runtime: Cross-anchor JSON-compatible runtime state.
        ledger: Deterministic operation ledger entries.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )

    version: pydantic.StrictInt = CURRENT_VERSION
    definitions: dict[str, dict[str, pydantic.JsonValue]] = pydantic.Field(
        default_factory=lambda: {kind: {} for kind in DEFINITION_KINDS}
    )
    anchors: dict[str, AnchorPayload] = pydantic.Field(default_factory=dict)
    runtime: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    ledger: list[LedgerEntry] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("definitions")
    @classmethod
    def validate_definition_keys(
        cls, value: dict[str, dict[str, pydantic.JsonValue]]
    ) -> dict[str, dict[str, pydantic.JsonValue]]:
        """Validate definition kind and id map keys.

        Args:
            value: Mapping from definition kind to definition id to payload.

        Returns:
            Mapping with normalized definition kind and id keys.

        Raises:
            ValueError: If a definition kind or id is not a valid path segment or
                duplicates another key after normalization.
        """
        normalized: dict[str, dict[str, pydantic.JsonValue]] = {}
        original_kinds: dict[str, str] = {}
        for definition_kind, definition_map in value.items():
            canonical_kind = PrimitiveRef.validate_path_segment(definition_kind)
            if canonical_kind in normalized:
                raise ValueError(
                    "Duplicate definition kind keys normalize to "
                    f"'{canonical_kind}': '{original_kinds[canonical_kind]}' and "
                    f"'{definition_kind}'"
                )

            normalized_map: dict[str, pydantic.JsonValue] = {}
            original_ids: dict[str, str] = {}
            for definition_id, payload in definition_map.items():
                canonical_id = PrimitiveRef.validate_path_segment(definition_id)
                if canonical_id in normalized_map:
                    raise ValueError(
                        "Duplicate definition ids normalize to "
                        f"'{canonical_id}' in kind '{canonical_kind}': "
                        f"'{original_ids[canonical_id]}' and '{definition_id}'"
                    )
                normalized_map[canonical_id] = payload
                original_ids[canonical_id] = definition_id

            normalized[canonical_kind] = normalized_map
            original_kinds[canonical_kind] = definition_kind
        return normalized

    @pydantic.field_validator("anchors")
    @classmethod
    def validate_anchor_keys(
        cls, value: dict[str, AnchorPayload]
    ) -> dict[str, AnchorPayload]:
        """Validate root anchor mapping keys.

        Args:
            value: Mapping from canonical anchor string to anchor payload.

        Returns:
            Mapping with normalized anchor keys.

        Raises:
            ValueError: If any anchor key is not a valid anchor reference.
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
        """Validate the persisted schema version.

        Args:
            value: Version value read from persisted primitive state.

        Returns:
            The accepted schema version.

        Raises:
            ValueError: If the value is not the current supported schema version.
        """
        if value != CURRENT_VERSION:
            raise ValueError(
                f"Unsupported Game Primitives version {value}; "
                f"current version is {CURRENT_VERSION}"
            )
        return value

    @pydantic.model_validator(mode="after")
    def ensure_definition_kinds(self) -> "PrimitiveRootPayload":
        """Ensure all built-in definition collections exist.

        Returns:
            The root payload with missing definition collections initialized.
        """
        for kind in DEFINITION_KINDS:
            self.definitions.setdefault(kind, {})
        return self


def default_anchor() -> dict[str, Any]:
    """Return a fresh anchor payload for attached primitive instances.

    Returns:
        A JSON-compatible anchor dictionary with tags, primitives, and metadata.
    """
    return AnchorPayload().model_dump(mode="json")
