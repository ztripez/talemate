"""Canonical root and anchor schemas for the Game Primitives store."""

from __future__ import annotations

from typing import Any

import pydantic

from talemate.game.primitives.anchors import PrimitiveRef
from talemate.game.primitives.constants import (
    CURRENT_VERSION,
)
from talemate.game.primitives.containers import (
    AnchorPayload,
    PrimitiveDefinitions,
    normalize_anchor_payloads,
)
from talemate.game.primitives.draft_schema import PrimitiveDraft
from talemate.game.primitives.ledger import LedgerEntry


class PrimitiveRootPayload(pydantic.BaseModel):
    """Persist the complete Game Primitives state under scene variables.

    Attributes:
        version: Strict integer equal to the runtime's current schema version.
        definitions: Reusable primitive definitions grouped by kind and id.
        anchors: Validated anchor payloads keyed by canonical reference.
        runtime: JSON-compatible subsystem runtime data.
        ledger: Ordered operation audit records.
        drafts: Authoring drafts keyed by canonical draft identifier.

    Invariants:
        The version equals ``CURRENT_VERSION``. Anchor and draft keys are
        canonical and unique; each draft key equals its nested ``id``. Unknown
        fields and non-finite values are rejected.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )
    version: pydantic.StrictInt
    definitions: PrimitiveDefinitions
    anchors: dict[str, AnchorPayload]
    runtime: dict[str, pydantic.JsonValue]
    ledger: list[LedgerEntry]
    drafts: dict[str, PrimitiveDraft]

    @pydantic.field_validator("drafts")
    @classmethod
    def validate_draft_keys(
        cls, value: dict[str, PrimitiveDraft]
    ) -> dict[str, PrimitiveDraft]:
        """Normalize draft keys and require each key to match its draft id.

        Args:
            value: Draft mapping supplied for root validation.

        Returns:
            New mapping keyed by canonical draft identifiers.

        Raises:
            ValueError: If canonical identifiers duplicate or a key differs from
                the nested draft identifier.

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
        """Normalize root anchor keys to canonical addresses.

        Args:
            value: Validated anchor models keyed by supplied references.

        Returns:
            New mapping keyed by unique canonical anchor references.

        Raises:
            ValueError: If canonical anchor keys collide.
            pydantic.ValidationError: If a key is not a valid anchor reference.

        """
        return normalize_anchor_payloads(value)

    @pydantic.field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        """Require the persisted schema version supported by this runtime.

        Args:
            value: Strict persisted schema version integer.

        Returns:
            The supported version unchanged.

        Raises:
            ValueError: If ``value`` differs from ``CURRENT_VERSION``.

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
        A new anchor mapping with every built-in primitive collection initialized.

    Side Effects:
        None; each call returns independent collections.

    """
    return AnchorPayload().model_dump(mode="json")


def default_root() -> dict[str, Any]:
    """Create the complete current-version primitive root storage shape.

    Returns:
        A new JSON-compatible root with empty definitions, anchors, runtime,
        ledger, and drafts.

    Side Effects:
        None; each call returns independent collections.

    """
    return PrimitiveRootPayload(
        version=CURRENT_VERSION,
        definitions=PrimitiveDefinitions(),
        anchors={},
        runtime={},
        ledger=[],
        drafts={},
    ).model_dump(mode="json")
