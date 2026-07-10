"""Primitive-aware condition evaluation for Game Primitives."""

from __future__ import annotations

import copy
from typing import Any, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.values import primitive_payload_value
from talemate.game.schema import (
    ConditionOperator,
    compare_condition_values,
    read_condition_path,
)

#: Comparison operators accepted by primitive-aware conditions.
Operator = ConditionOperator


class PrimitiveCondition(pydantic.BaseModel):
    """Validated predicate over scene game state or primitive state.

    ``kind`` selects the required fields: path and primitive conditions require
    ``path``; tag conditions require ``anchor`` and ``tag``; anchored meter,
    relationship, and clock conditions require enough fields to build a
    primitive reference.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    kind: Literal[
        "path",
        "primitive",
        "anchor_has_tag",
        "anchor_missing_tag",
        "meter",
        "clock_complete",
        "relationship",
        "always",
        "never",
    ] = "path"
    path: str | None = None
    operator: Operator | None = None
    value: pydantic.JsonValue | None = None
    anchor: str | None = None
    tag: str | None = None
    dimension: str | None = None
    data: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_kind_payload(self) -> "PrimitiveCondition":
        """Validate the fields required by this condition kind."""
        if self.kind == "path":
            _require_text(self.path, "path condition requires path")
        elif self.kind == "primitive":
            PrimitiveRef.parse(
                _require_text(self.path, "primitive condition requires path")
            )
        elif self.kind in {"anchor_has_tag", "anchor_missing_tag"}:
            AnchorRef.parse(
                _require_text(self.anchor, f"Condition {self.kind} requires anchor")
            )
            _require_text(self.tag, f"Condition {self.kind} requires tag")
        elif self.kind == "meter":
            if self.path:
                PrimitiveRef.parse(self.path)
            else:
                _anchored_ref(self.anchor, "meters", self.dimension)
        elif self.kind == "relationship":
            anchor = AnchorRef.parse(
                _require_text(self.anchor, "relationship condition requires anchor")
            )
            if anchor.kind != "relationship":
                raise ValueError("relationship condition requires relationship anchor")
            _anchored_ref(self.anchor, "meters", self.dimension)
        elif self.kind == "clock_complete":
            if self.path:
                PrimitiveRef.parse(self.path)
            else:
                _anchored_ref(self.anchor, "clocks", self.dimension)
        return self


class PrimitiveConditionResult(pydantic.BaseModel):
    """Debug result for one primitive condition evaluation."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    matches: bool
    kind: str
    path: str | None = None
    actual: pydantic.JsonValue | None = None
    expected: pydantic.JsonValue | None = None
    operator: str | None = None
    message: str | None = None


class PrimitiveConditionGroup(pydantic.BaseModel):
    """AND/OR group of primitive-aware conditions."""

    model_config = pydantic.ConfigDict(extra="forbid")

    operator: Literal["and", "or"] = "and"
    conditions: list[PrimitiveCondition] = pydantic.Field(default_factory=list)


class PrimitiveConditionGroupResult(pydantic.BaseModel):
    """Debug result for one evaluated primitive condition group."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    operator: Literal["and", "or"]
    matches: bool
    conditions: list[PrimitiveConditionResult]


def evaluate_condition_input(
    scene: Any, condition: dict | list | PrimitiveCondition | PrimitiveConditionGroup
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluate a condition, group, or group list and return matches plus debug."""
    groups = _normalize_condition_groups(condition)
    store = PrimitiveStore.for_scene(scene) if _groups_require_store(groups) else None
    all_debug: list[PrimitiveConditionGroupResult] = []
    for group in groups:
        result = evaluate_condition_group(scene, store, group)
        all_debug.append(result)
        if result.matches:
            return True, [
                item.model_dump(mode="json", exclude_none=True) for item in all_debug
            ]
    return False, [
        item.model_dump(mode="json", exclude_none=True) for item in all_debug
    ]


def evaluate_condition_group(
    scene: Any, store: PrimitiveStore | None, group: PrimitiveConditionGroup
) -> PrimitiveConditionGroupResult:
    """Evaluate one primitive condition group."""
    if not group.conditions:
        return PrimitiveConditionGroupResult(
            operator=group.operator, matches=False, conditions=[]
        )
    results = [
        evaluate_condition(scene, store, condition) for condition in group.conditions
    ]
    matches = (
        all(result.matches for result in results)
        if group.operator == "and"
        else any(result.matches for result in results)
    )
    return PrimitiveConditionGroupResult(
        operator=group.operator, matches=matches, conditions=results
    )


def evaluate_condition(
    scene: Any, store: PrimitiveStore | None, condition: PrimitiveCondition | dict
) -> PrimitiveConditionResult:
    """Evaluate one primitive-aware condition without mutating state."""
    cond = (
        condition
        if isinstance(condition, PrimitiveCondition)
        else PrimitiveCondition.model_validate(condition)
    )
    if cond.kind == "always":
        return PrimitiveConditionResult(matches=True, kind=cond.kind, message="always")
    if cond.kind == "never":
        return PrimitiveConditionResult(matches=False, kind=cond.kind, message="never")
    if cond.kind == "anchor_has_tag" or cond.kind == "anchor_missing_tag":
        if store is None:
            raise ValueError(f"Condition {cond.kind} requires a primitive store")
        return _evaluate_anchor_tag(store, cond)

    actual, path = _condition_value(scene, store, cond)
    operator = cond.operator or ("is_true" if cond.value is None else "==")
    matches = compare_values(actual, operator, cond.value)
    return PrimitiveConditionResult(
        matches=matches,
        kind=cond.kind,
        path=path,
        actual=actual,
        expected=cond.value,
        operator=operator,
    )


def compare_values(actual: Any, operator: str, expected: Any = None) -> bool:
    """Compare values using Talemate game-state condition operator semantics."""
    return compare_condition_values(actual, operator, expected)


def _groups_require_store(groups: list[PrimitiveConditionGroup]) -> bool:
    """Return whether any condition in the normalized groups reads primitives."""
    primitive_kinds = {
        "primitive",
        "anchor_has_tag",
        "anchor_missing_tag",
        "meter",
        "clock_complete",
        "relationship",
    }
    return any(
        condition.kind in primitive_kinds
        for group in groups
        for condition in group.conditions
    )


def _normalize_condition_groups(
    condition: dict | list | PrimitiveCondition | PrimitiveConditionGroup,
) -> list[PrimitiveConditionGroup]:
    """Normalize accepted condition wire shapes into groups."""
    if isinstance(condition, PrimitiveConditionGroup):
        return [condition]
    if isinstance(condition, PrimitiveCondition):
        return [PrimitiveConditionGroup(conditions=[condition])]
    if isinstance(condition, dict):
        if "conditions" in condition:
            return [PrimitiveConditionGroup.model_validate(condition)]
        return [
            PrimitiveConditionGroup(
                conditions=[PrimitiveCondition.model_validate(condition)]
            )
        ]
    if isinstance(condition, list):
        if not condition:
            return []
        if all(isinstance(item, dict) and "conditions" in item for item in condition):
            return [PrimitiveConditionGroup.model_validate(item) for item in condition]
        return [
            PrimitiveConditionGroup(
                conditions=[
                    PrimitiveCondition.model_validate(item) for item in condition
                ]
            )
        ]
    raise ValueError("Condition input must be a dict, list, condition, or group")


def _evaluate_anchor_tag(
    store: PrimitiveStore, cond: PrimitiveCondition
) -> PrimitiveConditionResult:
    """Evaluate anchor tag membership conditions."""
    anchor = AnchorRef.parse(cond.anchor)
    payload = store.get_anchor(anchor)
    if payload is None:
        return PrimitiveConditionResult(
            matches=False,
            kind=cond.kind,
            path=anchor.key(),
            actual=None,
            expected=cond.tag,
            operator="has_tag" if cond.kind == "anchor_has_tag" else "missing_tag",
            message="anchor missing",
        )
    tags = payload.get("tags", [])
    has_tag = cond.tag in tags
    matches = has_tag if cond.kind == "anchor_has_tag" else not has_tag
    return PrimitiveConditionResult(
        matches=matches,
        kind=cond.kind,
        path=anchor.key(),
        actual=copy.deepcopy(tags),
        expected=cond.tag,
        operator="has_tag" if cond.kind == "anchor_has_tag" else "missing_tag",
    )


def _condition_value(
    scene: Any, store: PrimitiveStore | None, cond: PrimitiveCondition
) -> tuple[Any, str | None]:
    """Resolve the current value for a condition."""
    if cond.kind == "path":
        found, value = read_condition_path(scene.game_state, cond.path)
        return value if found else None, cond.path
    if cond.kind == "primitive":
        if store is None:
            raise ValueError("primitive condition requires a primitive store")
        ref = PrimitiveRef.parse(cond.path)
        return primitive_payload_value(store.get_primitive(ref)), ref.key()
    if cond.kind == "meter":
        if store is None:
            raise ValueError("meter condition requires a primitive store")
        ref = (
            PrimitiveRef.parse(cond.path)
            if cond.path
            else _anchored_ref(cond.anchor, "meters", cond.dimension)
        )
        return primitive_payload_value(store.get_primitive(ref)), ref.key()
    if cond.kind == "relationship":
        if store is None:
            raise ValueError("relationship condition requires a primitive store")
        ref = _anchored_ref(cond.anchor, "meters", cond.dimension)
        return primitive_payload_value(store.get_primitive(ref)), ref.key()
    if cond.kind == "clock_complete":
        if store is None:
            raise ValueError("clock_complete condition requires a primitive store")
        ref = (
            PrimitiveRef.parse(cond.path)
            if cond.path
            else _anchored_ref(cond.anchor, "clocks", cond.dimension)
        )
        payload = store.get_primitive(ref)
        return _clock_complete(payload), ref.key()
    raise ValueError(f"Unknown condition kind: {cond.kind}")


def _anchored_ref(
    anchor: str | None, kind: str, primitive_id: str | None
) -> PrimitiveRef:
    """Build a primitive reference from anchor, kind, and primitive id fields."""
    if not anchor or not primitive_id:
        raise ValueError(f"{kind} condition requires anchor and dimension")
    return PrimitiveRef(anchor=AnchorRef.parse(anchor), kind=kind, id=primitive_id)


def _require_text(value: str | None, message: str) -> str:
    """Return non-empty text or raise a validation error message."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value


def _clock_complete(payload: Any) -> bool:
    """Return whether a clock payload is complete."""
    if not isinstance(payload, dict):
        return False
    if payload.get("complete") is True:
        return True
    value = payload.get("value")
    target = payload.get("target")
    return (
        isinstance(value, (int, float))
        and isinstance(target, (int, float))
        and value >= target
    )
