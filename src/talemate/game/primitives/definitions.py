"""Reusable definition schemas and validation for Game Primitives."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, MutableMapping
from importlib import import_module
from types import MappingProxyType
from typing import Any

import pydantic

from talemate.game.primitives.anchors import PrimitiveRef
from talemate.game.primitives.render import RenderPolicy

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

#: Lazy model locations for definition kinds with typed payload schemas.
_DEFINITION_MODEL_LOCATIONS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        "decks": ("talemate.game.primitives.decks", "DeckDefinition"),
        "roll_tables": (
            "talemate.game.primitives.roll_tables",
            "RollTableDefinition",
        ),
        "modifiers": ("talemate.game.primitives.modifiers", "RollModifier"),
        "meters": ("talemate.game.primitives.definitions", "MeterPayload"),
        "clocks": ("talemate.game.primitives.definitions", "ClockPayload"),
        "adventures": ("talemate.game.primitives.adventure", "AdventureDefinition"),
    }
)


class MeterPayload(pydantic.BaseModel):
    """Represent a canonical bounded numeric meter definition or instance.

    Attributes:
        id: Canonical non-empty meter identifier.
        label: Optional human-readable meter label.
        min: Finite inclusive lower bound for the meter value.
        max: Finite inclusive upper bound for the meter value.
        value: Finite current value within the inclusive bounds.
        render_policy: Policy controlling whether and how the meter is rendered.

    Invariants:
        ``min <= value <= max`` and all three numeric fields are finite. The
        identifier is a valid primitive path segment, and unknown fields are
        rejected.

    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    min: pydantic.StrictInt | pydantic.StrictFloat
    max: pydantic.StrictInt | pydantic.StrictFloat
    value: pydantic.StrictInt | pydantic.StrictFloat
    render_policy: RenderPolicy = "hidden"

    @pydantic.model_validator(mode="after")
    def validate_bounds(self) -> "MeterPayload":
        """Validate and normalize the meter identifier and numeric bounds.

        Returns:
            The meter with a canonical identifier and validated numeric fields.

        Raises:
            ValueError: If a numeric field is non-finite, the minimum exceeds the
                maximum, the value lies outside the inclusive bounds, or the
                identifier is empty or contains ``/``.

        Invariants:
            The returned meter has a canonical identifier and satisfies
            ``min <= value <= max`` with finite numeric fields.

        """
        for value in (self.min, self.max, self.value):
            if not math.isfinite(float(value)):
                raise ValueError("Meter values must be finite")
        if self.min > self.max:
            raise ValueError("Meter min cannot exceed max")
        if not self.min <= self.value <= self.max:
            raise ValueError("Meter value must be within min and max")
        self.id = PrimitiveRef.validate_path_segment(self.id)
        return self


class ClockPayload(pydantic.BaseModel):
    """Represent a canonical bounded integer progress clock.

    Attributes:
        id: Canonical non-empty clock identifier.
        label: Optional human-readable clock label.
        max: Positive integer number of progress segments.
        value: Current non-negative number of completed segments.
        render_policy: Policy controlling whether and how the clock is rendered.

    Invariants:
        ``0 <= value <= max`` and ``max`` is positive. The identifier is a valid
        primitive path segment, and unknown fields are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    max: pydantic.StrictInt = pydantic.Field(gt=0)
    value: pydantic.StrictInt = pydantic.Field(default=0, ge=0)
    render_policy: RenderPolicy = "summary"

    @pydantic.model_validator(mode="after")
    def validate_bounds(self) -> "ClockPayload":
        """Validate and normalize the clock identifier and progress bound.

        Returns:
            The clock with a canonical identifier and bounded progress value.

        Raises:
            ValueError: If the current value exceeds the maximum or the identifier
                is empty or contains ``/``.

        Invariants:
            The returned clock has a canonical identifier and satisfies
            ``0 <= value <= max`` with a positive maximum.

        """
        self.id = PrimitiveRef.validate_path_segment(self.id)
        if self.value > self.max:
            raise ValueError("Clock value cannot exceed max")
        return self


def _definition_model_for_kind(kind: str) -> type[pydantic.BaseModel] | None:
    """Return the registered payload model for a definition kind, if any."""
    model_location = _DEFINITION_MODEL_LOCATIONS.get(kind)
    if model_location is None:
        return None
    module_name, model_name = model_location
    return getattr(import_module(module_name), model_name)


def coerce_definition_payload(
    kind: str, definition_id: str, value: Any
) -> dict[str, Any]:
    """Validate and serialize one definition with its registered schema.

    Definition kinds without a registered typed schema are validated as generic
    primitive payloads. Typed definitions must contain an id matching their map
    key.

    Args:
        kind: Definition collection name used to select the payload schema.
        definition_id: Definition map key that typed payload ids must match.
        value: Raw mapping or model-compatible value to validate.

    Returns:
        A canonical JSON-compatible definition dictionary.

    Raises:
        pydantic.ValidationError: If ``value`` does not satisfy the selected
            definition schema.
        ValueError: If a typed payload id differs from ``definition_id``.

    """
    model_type = _definition_model_for_kind(kind)
    if model_type is None:
        # Deferred to avoid a definitions -> schema -> definitions import cycle.
        from talemate.game.primitives.schema import PrimitivePayload

        return PrimitivePayload.model_validate(value).model_dump(mode="json")

    model = model_type.model_validate(value)
    if model.id != definition_id:
        label = kind.removesuffix("s").replace("_", " ").capitalize()
        raise ValueError(f"{label} key '{definition_id}' must match id '{model.id}'")
    return model.model_dump(mode="json")


class PrimitiveDefinitions(
    pydantic.RootModel[dict[str, dict[str, pydantic.JsonValue]]],
    MutableMapping[str, dict[str, pydantic.JsonValue]],
):
    """Store validated reusable primitive definitions grouped by kind.

    Attributes:
        root: Definition payloads grouped first by canonical definition kind and
            then by canonical definition identifier. Every built-in kind in
            ``DEFINITION_KINDS`` is present, even when its collection is empty.

    Invariants:
        Kind and definition identifiers are canonical and unique after
        normalization. Registered definition kinds contain payloads validated by
        their typed schemas; unregistered kinds contain JSON-compatible objects.

    """

    model_config = pydantic.ConfigDict(
        allow_inf_nan=False, revalidate_instances="always"
    )
    root: dict[str, dict[str, pydantic.JsonValue]] = pydantic.Field(
        default_factory=lambda: {kind: {} for kind in DEFINITION_KINDS}
    )

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, value: Any) -> Any:
        """Normalize keys and initialize built-in definition kinds.

        Args:
            value: Raw root input, an existing ``PrimitiveDefinitions`` instance,
                or another value passed through for Pydantic type validation.

        Returns:
            A mapping with canonical kind and definition keys plus every built-in
            definition kind, or the original non-mapping input unchanged.

        Raises:
            ValueError: If a kind or definition identifier is empty, contains
                ``/``, or duplicates another key after normalization.

        Invariants:
            Mapping results contain every kind in ``DEFINITION_KINDS`` exactly
            once, and all processed map keys are canonical and unique.

        """
        if isinstance(value, cls):
            value = value.root
        if not isinstance(value, dict):
            return value

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
            if not isinstance(definition_map, dict):
                normalized[canonical_kind] = definition_map
                original_kinds[canonical_kind] = definition_kind
                continue

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

        for kind in DEFINITION_KINDS:
            normalized.setdefault(kind, {})
        return normalized

    @pydantic.model_validator(mode="after")
    def validate_typed_definitions(self) -> "PrimitiveDefinitions":
        """Validate and normalize definitions with registered schemas.

        Returns:
            The definitions model with each payload serialized to a canonical,
            JSON-compatible dictionary.

        Raises:
            pydantic.ValidationError: If a payload does not satisfy its registered
                definition schema or is not a JSON object for an unregistered kind.
            ValueError: If a typed payload identifier differs from its definition
                map key.

        Invariants:
            Every returned typed payload satisfies its registered model and has an
            identifier equal to its map key; every payload is JSON-compatible.

        """
        for kind, definitions in self.root.items():
            for definition_id, payload in definitions.items():
                self.root[kind][definition_id] = coerce_definition_payload(
                    kind, definition_id, payload
                )
        return self

    def __getitem__(self, key: str) -> dict[str, pydantic.JsonValue]:
        """Return the definition collection stored under a kind key."""
        return self.root[key]

    def __setitem__(self, key: str, value: dict[str, pydantic.JsonValue]) -> None:
        """Store a definition collection under a kind key."""
        self.root[key] = value

    def __delitem__(self, key: str) -> None:
        """Delete the definition collection stored under a kind key."""
        del self.root[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over definition kind keys in insertion order."""
        return iter(self.root)

    def __len__(self) -> int:
        """Return the number of definition kind collections."""
        return len(self.root)
