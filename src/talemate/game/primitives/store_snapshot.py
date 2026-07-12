"""Detached read-only snapshots of Game Primitives scene state."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.schema import PrimitiveRootPayload


class PrimitiveStoreSnapshot:
    """Provide detached, validated state for repeated read-only operations.

    Attributes:
        No mutable state is publicly exposed; accessors return detached copies.

    Invariants:
        Construction accepts only a validated ``PrimitiveRootPayload``. The
        captured root never changes, and no returned model or collection aliases
        snapshot storage.

    """

    def __init__(self, validated_root: PrimitiveRootPayload):
        """Create detached storage from an explicitly validated root model.

        Args:
            validated_root: Complete validated root state to capture by deep copy.

        Raises:
            TypeError: If ``validated_root`` is not a ``PrimitiveRootPayload``.

        Side Effects:
            Allocates private deep copies; the supplied model is not modified.

        """
        if not isinstance(validated_root, PrimitiveRootPayload):
            raise TypeError("PrimitiveStoreSnapshot requires PrimitiveRootPayload")
        self.__root_model = validated_root.model_copy(deep=True)
        self.__root = self.__root_model.model_dump(mode="json")

    def detached_root_model(self) -> PrimitiveRootPayload:
        """Return a deep detached copy of the validated root model.

        Callers may freely mutate the result to build candidates. Neither the
        snapshot nor scene persistence can be changed through the returned model.

        Returns:
            Deep copy of the complete validated root model.

        Side Effects:
            None; mutating the result cannot alter the snapshot.

        """
        return self.__root_model.model_copy(deep=True)

    def get_anchor(self, anchor: AnchorRef | str, create: bool = False) -> dict | None:
        """Return a detached anchor payload without revalidating the root.

        Args:
            anchor: Canonical or parseable anchor reference to retrieve.
            create: Must remain ``False`` because snapshots cannot create anchors.

        Returns:
            Deep-copied JSON anchor payload, or ``None`` when absent.

        Raises:
            PrimitiveStoreError: If ``create`` is true.
            pydantic.ValidationError: If ``anchor`` is not a valid reference.

        """
        if create:
            raise PrimitiveStoreError("PrimitiveStoreSnapshot is read-only")
        anchor_ref = (
            anchor if isinstance(anchor, AnchorRef) else AnchorRef.parse(anchor)
        )
        payload = self.__root["anchors"].get(anchor_ref.key())
        return copy.deepcopy(payload) if payload is not None else None

    def get_primitive(self, ref: PrimitiveRef | str, default: Any = None) -> Any:
        """Return a detached primitive payload without revalidating the root.

        Args:
            ref: Canonical or parseable primitive reference to retrieve.
            default: Value returned when the anchor, kind, or primitive is absent.

        Returns:
            Deep copy of the payload or ``default``; mutable defaults are also
            copied when reached through an existing anchor.

        Raises:
            pydantic.ValidationError: If ``ref`` is not a valid reference.

        """
        primitive_ref = (
            ref if isinstance(ref, PrimitiveRef) else PrimitiveRef.parse(ref)
        )
        anchor = self.__root["anchors"].get(primitive_ref.anchor.key())
        if anchor is None:
            return default
        payload = (
            anchor["primitives"]
            .get(primitive_ref.kind, {})
            .get(primitive_ref.id, default)
        )
        return copy.deepcopy(payload)

    def get_definition(self, kind: str, definition_id: str, default: Any = None) -> Any:
        """Return a detached reusable definition payload.

        Args:
            kind: Definition collection name.
            definition_id: Identifier within the collection.
            default: Value copied and returned when the definition is absent.

        Returns:
            Deep copy of the definition payload or ``default``.

        """
        payload = self.__root["definitions"].get(kind, {}).get(definition_id, default)
        return copy.deepcopy(payload)

    def get_runtime(self, key: str, default: Any = None) -> Any:
        """Return a detached subsystem runtime value.

        Args:
            key: Runtime mapping key.
            default: Value copied and returned when ``key`` is absent.

        Returns:
            Deep copy of the runtime value or ``default``.

        """
        return copy.deepcopy(self.__root["runtime"].get(key, default))

    def iter_definition_kinds(self) -> list[str]:
        """Return definition collection names in persisted insertion order.

        Returns:
            New list of definition kind names.

        """
        return list(self.__root["definitions"])

    def iter_definitions(self, kind: str) -> dict[str, Any]:
        """Return one detached definition collection.

        Args:
            kind: Definition collection name.

        Returns:
            Deep-copied identifier-to-definition mapping, or an empty mapping for
            an unknown kind.

        """
        return copy.deepcopy(self.__root["definitions"].get(kind, {}))

    def iter_drafts(self) -> dict[str, Any]:
        """Return all detached validated authoring drafts.

        Returns:
            Deep-copied mapping from draft identifiers to serialized drafts.

        """
        return copy.deepcopy(self.__root["drafts"])

    def recent_ledger(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return up to ``limit`` detached recent ledger entries.

        Args:
            limit: Positive, non-boolean integer maximum number of entries.

        Returns:
            Deep-copied entries in persisted chronological order.

        Raises:
            PrimitiveStoreError: If ``limit`` is not a positive integer.

        """
        if type(limit) is not int or limit < 1:
            raise PrimitiveStoreError("ledger limit must be a positive integer")
        return copy.deepcopy(self.__root["ledger"][-limit:])

    def revision_token(self) -> str:
        """Return a deterministic token for the complete validated state.

        Returns:
            Lowercase SHA-256 hexadecimal digest of canonical model JSON.

        """
        canonical = self.__root_model.model_dump_json().encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def iter_anchor_keys(self, kind: str | None = None) -> list[str]:
        """Return canonical anchor keys, optionally filtered by anchor kind.

        Args:
            kind: Optional exact anchor-kind value to include.

        Returns:
            New list in persisted insertion order.

        """
        keys = []
        for key in self.__root["anchors"]:
            anchor = AnchorRef.parse(key)
            if kind is None or anchor.kind == kind:
                keys.append(anchor.key())
        return keys

    def iter_primitives(self, anchor: AnchorRef | str, kind: str) -> dict[str, Any]:
        """Return a detached primitive collection owned by an anchor.

        Args:
            anchor: Canonical or parseable owner reference.
            kind: Primitive collection name.

        Returns:
            Deep-copied identifier-to-payload mapping, or an empty mapping when
            the anchor or collection is absent.

        Raises:
            pydantic.ValidationError: If ``anchor`` is not a valid reference.

        """
        anchor_ref = (
            anchor if isinstance(anchor, AnchorRef) else AnchorRef.parse(anchor)
        )
        payload = self.__root["anchors"].get(anchor_ref.key())
        if payload is None:
            return {}
        return copy.deepcopy(payload["primitives"].get(kind, {}))
