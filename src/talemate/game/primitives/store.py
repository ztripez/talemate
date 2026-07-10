"""Persistent store wrapper for Game Primitives scene state."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.exceptions import PrimitiveStoreError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.schema import (
    DEFAULT_LEDGER_LIMIT,
    GAME_PRIMITIVES_KEY,
    AnchorPayload,
    PrimitivePayload,
    PrimitiveRootPayload,
    default_anchor,
)

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class PrimitiveStore:
    """Wrapper around ``scene.game_state.variables['game_primitives']``.

    The store owns initialization, validation, and migration of the persisted
    primitive root shape while leaving the scene schema unchanged.
    """

    def __init__(self, root: dict[str, Any], max_ledger_length: int):
        """Create a store wrapper for an existing primitive root dictionary.

        Args:
            root: Mutable primitive root dictionary stored in ``game_state``.
            max_ledger_length: Positive integer maximum number of ledger entries
                to retain.

        Raises:
            PrimitiveStoreError: If ``max_ledger_length`` is not a positive
                integer.
        """
        self._validate_ledger_limit(max_ledger_length)
        self._root = root
        self.max_ledger_length = max_ledger_length
        self.ensure_shape()

    @classmethod
    def for_scene(
        cls, scene: "Scene", max_ledger_length: int = DEFAULT_LEDGER_LIMIT
    ) -> "PrimitiveStore":
        """Return a validated primitive store for a scene.

        Args:
            scene: Talemate scene whose ``game_state.variables`` contains the
                primitive store root.
            max_ledger_length: Positive integer maximum number of ledger entries
                to retain.

        Returns:
            Store wrapper with the base shape initialized and validated.

        Raises:
            PrimitiveStoreError: If ``max_ledger_length`` is not a positive
                integer, or if existing primitive state has an invalid root shape
                that cannot be safely migrated.
        """
        cls._validate_ledger_limit(max_ledger_length)
        variables = scene.game_state.variables
        if GAME_PRIMITIVES_KEY not in variables:
            root = {}
            variables[GAME_PRIMITIVES_KEY] = root
        else:
            root = variables[GAME_PRIMITIVES_KEY]

        return cls(root, max_ledger_length=max_ledger_length)

    @property
    def root(self) -> dict[str, Any]:
        """Return the mutable primitive root dictionary persisted by the scene.

        Returns:
            Canonical primitive root dictionary stored in ``game_state``.
        """
        return self._root

    def ensure_shape(self) -> None:
        """Validate and normalize the primitive root persisted schema.

        Raises:
            PrimitiveStoreError: If an existing container has an incompatible
                type or the stored version is unsupported.
        """
        self._replace_root(self._coerce_root_payload(self.root))

    def migrate(self) -> None:
        """Apply safe initialization for missing primitive store metadata.

        Raises:
            PrimitiveStoreError: If an existing version value is missing support
                or is not the current schema version.
        """
        self.ensure_shape()

    def get_anchor(self, anchor: AnchorRef | str, create: bool = False) -> dict | None:
        """Return an anchor payload, optionally creating it.

        Args:
            anchor: Anchor reference object or string key.
            create: Whether to create the anchor if it does not already exist.

        Returns:
            Deep copy of the anchor payload dictionary, or ``None`` when absent
            and ``create`` is false. Mutating the returned dictionary does not
            change scene state.

        Raises:
            InvalidAnchorRef: If ``anchor`` is a string that cannot be parsed.
            PrimitiveStoreError: If the persisted anchor payload is invalid.
        """
        anchor_ref = self._coerce_anchor(anchor)
        payload = self._get_anchor_payload(anchor_ref, create=create)
        if payload is None:
            return None
        return copy.deepcopy(payload)

    def ensure_anchor(self, anchor: AnchorRef | str) -> dict:
        """Return an existing anchor payload or create the default anchor shell.

        Args:
            anchor: Anchor reference object or canonical anchor string identifying
                the primitive owner namespace.

        Returns:
            Deep copy of the persisted anchor payload after the anchor exists.
            Mutating the returned dictionary does not change scene state.

        Raises:
            InvalidAnchorRef: If ``anchor`` is a string that cannot be parsed.
            PrimitiveStoreError: If the persisted anchor payload is invalid.
        """
        return copy.deepcopy(
            self._get_anchor_payload(self._coerce_anchor(anchor), create=True)
        )

    def get_primitive(self, ref: PrimitiveRef | str, default: Any = None) -> Any:
        """Return a primitive payload attached to an anchor.

        Args:
            ref: Primitive reference object or string key.
            default: Value returned when the anchor, primitive kind, or primitive
                id is absent.

        Returns:
            Deep copy of the primitive payload, or the provided default value
            when the anchor, primitive kind, or primitive id is absent. Mutating
            a returned primitive payload does not change scene state.

        Raises:
            InvalidPrimitiveRef: If ``ref`` is a string that cannot be parsed.
            PrimitiveStoreError: If persisted anchor or primitive collection
                data is invalid.
        """
        primitive_ref = self._coerce_primitive(ref)
        anchor_payload = self._get_anchor_payload(primitive_ref.anchor, create=False)
        if anchor_payload is None:
            return default

        primitive_kind = self._get_primitive_kind_payload(
            anchor_payload, primitive_ref.kind, create=False
        )
        if primitive_kind is None:
            return default
        if primitive_ref.id not in primitive_kind:
            return default
        return copy.deepcopy(primitive_kind[primitive_ref.id])

    def set_anchor_tags(self, anchor: AnchorRef | str, tags: list[str]) -> None:
        """Persist a validated tag list on an anchor.

        Args:
            anchor: Anchor reference object or canonical anchor string.
            tags: Non-empty tag strings to store. Duplicate normalized tags are
                removed while preserving order.

        Raises:
            PrimitiveStoreError: If any tag is not a non-empty string or the
                persisted anchor data is invalid.
        """
        anchor_ref = self._coerce_anchor(anchor)
        clean_tags = []
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                raise PrimitiveStoreError("Anchor tags must be non-empty strings")
            normalized = tag.strip()
            if normalized not in clean_tags:
                clean_tags.append(normalized)
        payload = self._get_anchor_payload(anchor_ref, create=True)
        payload["tags"] = clean_tags

    def get_definition(self, kind: str, definition_id: str, default: Any = None) -> Any:
        """Return a primitive definition payload by kind and id.

        Args:
            kind: Definition collection name. Known schema-validated kinds
                include ``"roll_tables"``, ``"modifiers"``, and ``"decks"``.
            definition_id: Definition identifier within the collection.
            default: Value returned when the definition is absent.

        Returns:
            Deep copy of the definition payload or ``default`` when absent.

        Raises:
            PrimitiveStoreError: If the persisted root shape is invalid.
        """
        self.ensure_shape()
        definitions = self.root["definitions"]
        if kind not in definitions or definition_id not in definitions[kind]:
            return default
        return copy.deepcopy(definitions[kind][definition_id])

    def set_definition(self, kind: str, definition_id: str, value: dict) -> None:
        """Persist a primitive definition payload by kind and id.

        Args:
            kind: Definition collection name. Known schema-validated kinds
                include ``"roll_tables"``, ``"modifiers"``, and ``"decks"``.
            definition_id: Definition identifier within the collection.
            value: JSON-compatible definition object.

        Raises:
            PrimitiveStoreError: If the root shape or definition payload is
                invalid.
        """
        self.ensure_shape()
        definition_payload = self._coerce_definition_payload(kind, definition_id, value)
        definitions = self.root["definitions"]
        if kind not in definitions:
            definitions[kind] = {}
        definitions[kind][definition_id] = definition_payload
        self.ensure_shape()

    def set_primitive(self, ref: PrimitiveRef | str, value: dict) -> None:
        """Persist a primitive payload at the referenced anchor path.

        Args:
            ref: Primitive reference object or string key.
            value: JSON-compatible primitive payload dictionary.

        Raises:
            InvalidPrimitiveRef: If ``ref`` is a string that cannot be parsed.
            PrimitiveStoreError: If ``value`` is not a JSON-compatible object or
                persisted anchor data is invalid, the persisted ledger is
                invalid, or ``max_ledger_length`` is not a positive integer.
        """
        self._set_primitive_payload(ref, value, ledger_op="primitive.set")

    def set_runtime_primitive(self, ref: PrimitiveRef | str, value: dict) -> None:
        """Persist primitive runtime state without appending a ledger entry.

        Args:
            ref: Primitive reference object or string key for the runtime state.
            value: JSON-compatible primitive payload dictionary.

        Raises:
            InvalidPrimitiveRef: If ``ref`` is a string that cannot be parsed.
            PrimitiveStoreError: If ``value`` is not a JSON-compatible object or
                persisted anchor data is invalid.
        """
        self._set_primitive_payload(ref, value, ledger_op=None)

    def delete_primitive(self, ref: PrimitiveRef | str) -> bool:
        """Delete a primitive payload if it exists.

        Args:
            ref: Primitive reference object or string key.

        Returns:
            ``True`` when a primitive was removed, otherwise ``False``.

        Raises:
            InvalidPrimitiveRef: If ``ref`` is a string that cannot be parsed.
            PrimitiveStoreError: If persisted anchor or primitive collection
                data is invalid, the persisted ledger is invalid, or
                ``max_ledger_length`` is not a positive integer.
        """
        self._validate_ledger_limit(self.max_ledger_length)
        primitive_ref = self._coerce_primitive(ref)
        anchor_payload = self._get_anchor_payload(primitive_ref.anchor, create=False)
        if anchor_payload is None:
            return False

        primitive_kind = self._get_primitive_kind_payload(
            anchor_payload, primitive_ref.kind, create=False
        )
        if primitive_kind is None or primitive_ref.id not in primitive_kind:
            return False

        previous = copy.deepcopy(primitive_kind[primitive_ref.id])
        ledger_payload = self._coerce_ledger_payload(
            LedgerEntry(
                op="primitive.delete",
                ref=primitive_ref.key(),
                output={"previous": previous},
            )
        )
        next_ledger = self._prepare_ledger_after_append(ledger_payload)

        primitive_kind.pop(primitive_ref.id)
        self.root["ledger"] = next_ledger
        return True

    def _set_primitive_payload(
        self, ref: PrimitiveRef | str, value: dict, *, ledger_op: str | None
    ) -> None:
        """Persist a primitive payload with optional ledger recording."""
        payload = self._coerce_primitive_payload(value)
        self._validate_ledger_limit(self.max_ledger_length)

        primitive_ref = self._coerce_primitive(ref)
        anchor_payload = self._get_anchor_payload(primitive_ref.anchor, create=False)
        primitive_kind = None
        if anchor_payload is not None:
            primitive_kind = self._get_primitive_kind_payload(
                anchor_payload, primitive_ref.kind, create=False
            )
        previous = (
            None
            if primitive_kind is None
            else copy.deepcopy(primitive_kind.get(primitive_ref.id))
        )
        next_ledger = None
        if ledger_op is not None:
            ledger_payload = self._coerce_ledger_payload(
                LedgerEntry(
                    op=ledger_op,
                    ref=primitive_ref.key(),
                    input={"value": payload},
                    output={"previous": previous, "current": payload},
                )
            )
            next_ledger = self._prepare_ledger_after_append(ledger_payload)

        anchor_payload = self._get_anchor_payload(primitive_ref.anchor, create=True)
        primitive_kind = self._get_primitive_kind_payload(
            anchor_payload, primitive_ref.kind, create=True
        )
        primitive_kind[primitive_ref.id] = copy.deepcopy(payload)
        if next_ledger is not None:
            self.root["ledger"] = next_ledger

    def append_ledger(self, entry: LedgerEntry | dict) -> None:
        """Append a JSON-serializable operation entry to the primitive ledger.

        Args:
            entry: Ledger model or dictionary payload to validate.

        Raises:
            PrimitiveStoreError: If the entry cannot be validated or serialized
                as JSON-compatible data, the persisted ledger is invalid, or
                ``max_ledger_length`` is not a positive integer.
        """
        self._validate_ledger_limit(self.max_ledger_length)
        ledger_payload = self._coerce_ledger_payload(entry)
        self._replace_root(self._coerce_root_payload(self.root))
        self.root["ledger"] = self._prepare_ledger_after_append(ledger_payload)

    def recent_ledger(self, limit: int = 50) -> list[dict]:
        """Return the most recent primitive ledger entries.

        Args:
            limit: Positive integer maximum number of entries to return.

        Returns:
            A deep-copied list of recent ledger payload dictionaries. Mutating
            the returned list or dictionaries does not change scene state.

        Raises:
            PrimitiveStoreError: If ``limit`` is not a positive integer or the
                persisted ledger contains invalid entries.
        """
        if type(limit) is not int or limit < 1:
            raise PrimitiveStoreError("ledger limit must be a positive integer")
        return copy.deepcopy(self._validated_ledger_payloads()[-limit:])

    def _replace_root(self, payload: dict[str, Any]) -> None:
        """Replace root contents while preserving the original dict object."""
        if not isinstance(self._root, dict):
            raise PrimitiveStoreError("Game Primitives root must be a dictionary")
        self.root.clear()
        self.root.update(payload)

    def _coerce_root_payload(self, value: Any) -> dict[str, Any]:
        """Validate and serialize a primitive root payload."""
        try:
            return PrimitiveRootPayload.model_validate(value).model_dump(mode="json")
        except pydantic.ValidationError as exc:
            raise PrimitiveStoreError(f"Invalid Game Primitives root: {exc}") from exc

    def _coerce_anchor(self, anchor: AnchorRef | str) -> AnchorRef:
        """Coerce an anchor string or object into an ``AnchorRef``."""
        if isinstance(anchor, AnchorRef):
            return AnchorRef.model_validate(anchor.model_dump())
        return AnchorRef.parse(anchor)

    def _coerce_primitive(self, ref: PrimitiveRef | str) -> PrimitiveRef:
        """Coerce a primitive string or object into a ``PrimitiveRef``."""
        if isinstance(ref, PrimitiveRef):
            return PrimitiveRef.model_validate(ref.model_dump())
        return PrimitiveRef.parse(ref)

    def _get_anchor_payload(self, anchor: AnchorRef, create: bool) -> dict | None:
        """Return the mutable validated anchor payload for internal writes."""
        self._replace_root(self._coerce_root_payload(self.root))
        anchors = self.root["anchors"]
        key = anchor.key()
        if key not in anchors:
            if not create:
                return None
            anchors[key] = default_anchor()
        return self._validate_anchor_payload(key, anchors[key])

    def _validate_anchor_payload(self, key: str, payload: Any) -> dict:
        """Validate and normalize a persisted anchor payload dictionary."""
        try:
            anchor = AnchorPayload.model_validate(payload)
        except pydantic.ValidationError as exc:
            raise PrimitiveStoreError(
                f"Invalid Game Primitives anchor {key}: {exc}"
            ) from exc

        normalized = anchor.model_dump(mode="json")
        payload.clear()
        payload.update(normalized)
        return payload

    def _get_primitive_kind_payload(
        self, anchor_payload: dict, kind: str, create: bool
    ) -> dict | None:
        """Return a primitive-kind dictionary under an anchor payload."""
        primitives = anchor_payload["primitives"]
        if kind not in primitives:
            if not create:
                return None
            primitives[kind] = {}
        return primitives[kind]

    def _coerce_primitive_payload(self, value: Any) -> dict[str, Any]:
        """Validate a primitive payload as a JSON-compatible object."""
        try:
            return PrimitivePayload.model_validate(value).model_dump(mode="json")
        except pydantic.ValidationError as exc:
            raise PrimitiveStoreError(f"Invalid primitive payload: {exc}") from exc

    def _coerce_definition_payload(
        self, kind: str, definition_id: str, value: Any
    ) -> dict[str, Any]:
        """Validate a definition payload with kind-specific schemas when known."""
        try:
            if kind == "roll_tables":
                from talemate.game.primitives.roll_tables import RollTableDefinition

                return RollTableDefinition.model_validate(value).model_dump(mode="json")
            if kind == "modifiers":
                from talemate.game.primitives.modifiers import RollModifier

                return RollModifier.model_validate(value).model_dump(mode="json")
            if kind == "decks":
                from talemate.game.primitives.decks import DeckDefinition

                return DeckDefinition.model_validate(value).model_dump(mode="json")
            return self._coerce_primitive_payload(value)
        except (pydantic.ValidationError, ValueError) as exc:
            raise PrimitiveStoreError(
                f"Invalid primitive definition {kind}/{definition_id}: {exc}"
            ) from exc

    def _coerce_ledger_payload(self, entry: LedgerEntry | dict) -> dict[str, Any]:
        """Validate and serialize a primitive ledger entry payload."""
        try:
            raw_entry = (
                entry.model_dump(mode="python")
                if isinstance(entry, LedgerEntry)
                else entry
            )
            ledger_entry = LedgerEntry.model_validate(raw_entry)
            return ledger_entry.model_dump(mode="json")
        except (pydantic.ValidationError, ValueError) as exc:
            raise PrimitiveStoreError(f"Invalid primitive ledger entry: {exc}") from exc

    def _prepare_ledger_after_append(
        self, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return a validated ledger list with one appended payload."""
        self._validate_ledger_limit(self.max_ledger_length)

        try:
            ledger = self._validated_ledger_payloads()
        except PrimitiveStoreError:
            raise

        ledger.append(payload)
        overflow = len(ledger) - self.max_ledger_length
        if overflow > 0:
            del ledger[:overflow]
        return ledger

    @staticmethod
    def _validate_ledger_limit(value: int) -> None:
        """Validate ledger retention limits before state mutation."""
        if type(value) is not int or value < 1:
            raise PrimitiveStoreError("max_ledger_length must be a positive integer")

    def _validated_ledger_payloads(self) -> list[dict[str, Any]]:
        """Return the current ledger as validated JSON payload dictionaries."""
        try:
            ledger_entries = pydantic.TypeAdapter(list[LedgerEntry]).validate_python(
                self.root["ledger"]
            )
        except (KeyError, pydantic.ValidationError, TypeError) as exc:
            raise PrimitiveStoreError(f"Invalid primitive ledger: {exc}") from exc
        return [entry.model_dump(mode="json") for entry in ledger_entries]
