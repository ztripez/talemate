"""Typed grouped containers for definitions and anchored primitives."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any

import pydantic

from talemate.game.primitives.adventure import AdventureDefinition
from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.attribute_model import AttributeSource
from talemate.game.primitives.constants import DEFINITION_KINDS, PRIMITIVE_KINDS
from talemate.game.primitives.deck_schema import DeckDefinition
from talemate.game.primitives.deck_state import DeckInstancePayload
from talemate.game.primitives.definitions import ClockPayload, MeterPayload
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.primitive_payloads import (
    PrimitivePayload,
    RollTableInstancePayload,
)
from talemate.game.primitives.roll_tables import RollTableDefinition


def _normalize_grouped_maps(value: Any) -> Any:
    if isinstance(value, pydantic.BaseModel):
        value = value.model_dump(mode="json")
    if not isinstance(value, Mapping):
        return value
    normalized: dict[str, Any] = {}
    original_groups: dict[str, str] = {}
    for group, values in value.items():
        canonical_group = PrimitiveRef.validate_path_segment(group)
        if canonical_group in normalized:
            raise ValueError(
                f"Duplicate collection keys normalize to '{canonical_group}': "
                f"'{original_groups[canonical_group]}' and '{group}'"
            )
        if not isinstance(values, Mapping):
            normalized[canonical_group] = values
            original_groups[canonical_group] = group
            continue
        normalized_values: dict[str, Any] = {}
        original_ids: dict[str, str] = {}
        for item_id, payload in values.items():
            canonical_id = PrimitiveRef.validate_path_segment(item_id)
            if canonical_id in normalized_values:
                raise ValueError(
                    f"Duplicate ids normalize to '{canonical_id}' in collection "
                    f"'{canonical_group}': '{original_ids[canonical_id]}' and "
                    f"'{item_id}'"
                )
            normalized_values[canonical_id] = payload
            original_ids[canonical_id] = item_id
        normalized[canonical_group] = normalized_values
        original_groups[canonical_group] = group
    return normalized


def _validate_internal_ids(container: Mapping[str, Mapping[str, Any]]) -> None:
    for kind, values in container.items():
        for item_id, payload in values.items():
            model_id = getattr(payload, "id", None)
            if model_id is not None and model_id != item_id:
                label = kind.removesuffix("s").replace("_", " ").capitalize()
                raise ValueError(f"{label} key '{item_id}' must match id '{model_id}'")


class _GroupedModel(pydantic.BaseModel, MutableMapping[str, dict[str, Any]]):
    model_config = pydantic.ConfigDict(
        extra="allow", allow_inf_nan=False, revalidate_instances="always"
    )
    __pydantic_extra__: dict[str, dict[str, PrimitivePayload]]

    @pydantic.model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, value: Any) -> Any:
        """Canonicalize collection and item map keys before field validation."""
        return _normalize_grouped_maps(value)

    def __getitem__(self, key: str) -> dict[str, Any]:
        if key in type(self).model_fields:
            return getattr(self, key)
        return (self.__pydantic_extra__ or {})[key]

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        if key in type(self).model_fields:
            setattr(self, key, value)
        else:
            self.__pydantic_extra__[key] = value

    def __delitem__(self, key: str) -> None:
        if key in type(self).model_fields:
            setattr(self, key, {})
        else:
            del self.__pydantic_extra__[key]

    def __iter__(self) -> Iterator[str]:
        yield from type(self).model_fields
        yield from self.__pydantic_extra__ or {}

    def __len__(self) -> int:
        return len(type(self).model_fields) + len(self.__pydantic_extra__ or {})

    def set_item(self, kind: str, item_id: str, value: Any) -> None:
        """Validate and store one item through its declared collection field."""
        validated = type(self).model_validate({kind: {item_id: value}})
        self[kind][item_id] = validated[kind][item_id]

    def set_collection(self, kind: str, values: Mapping[str, Any]) -> None:
        """Validate and replace one complete declared or extension collection."""
        self[kind] = type(self).model_validate({kind: values})[kind]


class PrimitiveDefinitions(_GroupedModel):
    """Store typed reusable definitions grouped by kind and identifier."""

    decks: dict[str, DeckDefinition] = pydantic.Field(default_factory=dict)
    roll_tables: dict[str, RollTableDefinition] = pydantic.Field(default_factory=dict)
    meters: dict[str, MeterPayload] = pydantic.Field(default_factory=dict)
    clocks: dict[str, ClockPayload] = pydantic.Field(default_factory=dict)
    relationship_models: dict[str, PrimitivePayload] = pydantic.Field(
        default_factory=dict
    )
    modifiers: dict[str, RollModifier] = pydantic.Field(default_factory=dict)
    attribute_sources: dict[str, PrimitivePayload] = pydantic.Field(
        default_factory=dict
    )
    adventures: dict[str, AdventureDefinition] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_ids(self) -> "PrimitiveDefinitions":
        """Require typed definition ids to equal their containing map keys."""
        _validate_internal_ids(self)
        return self


class AnchorPrimitives(_GroupedModel):
    """Store typed primitive instances grouped by kind and identifier."""

    meters: dict[str, MeterPayload] = pydantic.Field(default_factory=dict)
    clocks: dict[str, ClockPayload] = pydantic.Field(default_factory=dict)
    decks: dict[str, DeckInstancePayload] = pydantic.Field(default_factory=dict)
    roll_tables: dict[str, RollTableInstancePayload] = pydantic.Field(
        default_factory=dict
    )
    attributes: dict[str, AttributeSource] = pydantic.Field(default_factory=dict)
    modifiers: dict[str, RollModifier] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_ids(self) -> "AnchorPrimitives":
        """Require typed primitive ids to equal their containing map keys."""
        _validate_internal_ids(self)
        return self


class AnchorPayload(pydantic.BaseModel):
    """Persist metadata and typed primitive collections for one anchor."""

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )
    tags: list[str] = pydantic.Field(default_factory=list)
    primitives: AnchorPrimitives = pydantic.Field(default_factory=AnchorPrimitives)
    meta: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


def normalize_anchor_payloads(value: Mapping[str, Any]) -> dict[str, AnchorPayload]:
    """Canonicalize anchor keys and validate every typed anchor payload."""
    normalized: dict[str, AnchorPayload] = {}
    original_keys: dict[str, str] = {}
    for key, payload in value.items():
        canonical_key = AnchorRef.model_validate(key).key()
        if canonical_key in normalized:
            raise ValueError(
                "Duplicate anchor keys normalize to "
                f"'{canonical_key}': '{original_keys[canonical_key]}' and '{key}'"
            )
        normalized[canonical_key] = AnchorPayload.model_validate(payload)
        original_keys[canonical_key] = key
    return normalized


assert tuple(PrimitiveDefinitions.model_fields) == DEFINITION_KINDS
assert tuple(AnchorPrimitives.model_fields) == PRIMITIVE_KINDS
