"""Deterministic effect application for Game Primitives."""

from __future__ import annotations

import copy
from typing import Any, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.values import (
    primitive_payload_value,
    primitive_value_payload,
)


class Effect(pydantic.BaseModel):
    """Validated wire model for a primitive mutation request."""

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, revalidate_instances="always"
    )

    op: Literal[
        "set",
        "unset",
        "inc",
        "dec",
        "add_tag",
        "remove_tag",
        "append",
        "extend",
    ]
    target: str | None = None
    value: pydantic.JsonValue | None = None
    by: pydantic.StrictInt | pydantic.StrictFloat | None = None
    data: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_operation_payload(self) -> "Effect":
        """Validate operation-specific target and value requirements."""
        if not self.target:
            raise ValueError(f"Effect {self.op} requires target")
        if self.op in {"add_tag", "remove_tag"}:
            AnchorRef.parse(self.target)
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError(f"Effect {self.op} requires a non-empty string tag")
            return self

        PrimitiveRef.parse(self.target)
        if self.op == "extend" and not isinstance(self.value, list):
            raise ValueError("Effect extend requires list value")
        return self


class EffectResult(pydantic.BaseModel):
    """Result emitted after applying one primitive effect."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    ok: bool
    op: str
    target: str | None = None
    previous: pydantic.JsonValue | None = None
    current: pydantic.JsonValue | None = None
    message: str | None = None
    error: str | None = None


class EffectBatchResult(pydantic.BaseModel):
    """Result emitted after applying a list of primitive effects."""

    model_config = pydantic.ConfigDict(extra="forbid")

    ok: bool
    results: list[EffectResult]


def apply_effects(
    store: PrimitiveStore,
    effects: Effect | dict | list[Effect | dict],
    *,
    reason: str | None = None,
) -> EffectBatchResult:
    """Apply effects in order and stop on the first validation or mutation error."""
    results: list[EffectResult] = []

    if isinstance(effects, (Effect, dict)):
        raw_effects = [effects]
    elif isinstance(effects, list):
        raw_effects = effects
    else:
        return EffectBatchResult(
            ok=False,
            results=[
                EffectResult(
                    ok=False,
                    op="apply_effects",
                    error="Effects must be an effect object, dict, or list",
                )
            ],
        )

    for raw_effect in raw_effects:
        effect = raw_effect if isinstance(raw_effect, Effect) else None
        try:
            effect = Effect.model_validate(raw_effect)
            result = apply_effect(store, effect, reason=reason)
        except Exception as exc:
            op = effect.op if effect is not None else "effect"
            target = effect.target if effect is not None else None
            result = EffectResult(ok=False, op=op, target=target, error=str(exc))
        results.append(result)
        if not result.ok:
            break

    return EffectBatchResult(ok=all(result.ok for result in results), results=results)


def apply_effect(
    store: PrimitiveStore, effect: Effect | dict, *, reason: str | None = None
) -> EffectResult:
    """Apply one validated primitive effect and append an effect ledger entry."""
    effect_model = Effect.model_validate(effect)
    op = effect_model.op
    if op in {"add_tag", "remove_tag"}:
        result = _apply_tag_effect(store, effect_model)
    else:
        result = _apply_primitive_effect(store, effect_model)

    store.append_ledger(
        LedgerEntry(
            op=f"effect.{op}",
            ref=result.target if "/" in (result.target or "") else None,
            anchor=result.target if "/" not in (result.target or "") else None,
            input=effect_model.model_dump(
                mode="json", exclude_defaults=True, exclude_none=True
            ),
            output=result.model_dump(mode="json", exclude_none=True),
            message=reason,
        )
    )
    return result


def _apply_tag_effect(store: PrimitiveStore, effect: Effect) -> EffectResult:
    """Apply ``add_tag`` or ``remove_tag`` to an anchor payload."""
    anchor = AnchorRef.parse(effect.target)
    payload = store.get_anchor(anchor)
    if payload is None and effect.op == "remove_tag":
        raise PrimitiveError(f"Effect {effect.op} target anchor does not exist")
    if payload is None:
        payload = {"tags": []}
    previous = copy.deepcopy(payload.get("tags", []))
    tags = list(previous)
    tag = effect.value.strip()

    if effect.op == "add_tag" and tag not in tags:
        tags.append(tag)
    elif effect.op == "remove_tag":
        tags = [existing for existing in tags if existing != tag]

    store.set_anchor_tags(anchor, tags)
    return EffectResult(
        ok=True,
        op=effect.op,
        target=anchor.key(),
        previous=previous,
        current=copy.deepcopy(tags),
    )


def _apply_primitive_effect(store: PrimitiveStore, effect: Effect) -> EffectResult:
    """Apply a value effect to a primitive payload."""
    ref = PrimitiveRef.parse(effect.target)
    previous_payload = store.get_primitive(ref)
    previous_value = primitive_payload_value(previous_payload)

    if effect.op == "set":
        current_payload = _updated_value_payload(ref, previous_payload, effect.value)
    elif effect.op == "unset":
        existed = store.delete_primitive(ref)
        return EffectResult(
            ok=True,
            op=effect.op,
            target=ref.key(),
            previous=previous_value,
            current=None,
            message="deleted" if existed else "missing",
        )
    elif effect.op in {"inc", "dec"}:
        amount = 1 if effect.by is None else effect.by
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise PrimitiveError(f"Effect {effect.op} requires numeric 'by'")
        base = 0 if previous_value is None else previous_value
        if not isinstance(base, (int, float)) or isinstance(base, bool):
            raise PrimitiveError(f"Effect {effect.op} target value must be numeric")
        current_payload = _updated_value_payload(
            ref,
            previous_payload,
            base + amount if effect.op == "inc" else base - amount,
        )
    elif effect.op in {"append", "extend"}:
        values = (
            [] if previous_value is None else _require_list(previous_value, effect.op)
        )
        values = copy.deepcopy(values)
        if effect.op == "append":
            values.append(effect.value)
        else:
            values.extend(effect.value)
        current_payload = primitive_value_payload(values)
    else:  # pragma: no cover - Effect Literal prevents this.
        raise PrimitiveError(f"Unknown effect op: {effect.op}")

    store.set_primitive(ref, current_payload)
    return EffectResult(
        ok=True,
        op=effect.op,
        target=ref.key(),
        previous=previous_value,
        current=primitive_payload_value(current_payload),
    )


def _require_list(value: Any, op: str) -> list:
    """Return ``value`` if it is a list, otherwise raise a primitive error."""
    if not isinstance(value, list):
        raise PrimitiveError(f"Effect {op} target value must be a list")
    return value


def _updated_value_payload(
    ref: PrimitiveRef, previous_payload: Any, value: Any
) -> dict[str, Any]:
    """Return a value payload preserving existing value-bearing metadata."""
    if ref.anchor.kind == "relationship" and ref.kind == "meters":
        from talemate.game.primitives.relationships import relationship_value_payload

        return relationship_value_payload(ref, previous_payload, value)
    if isinstance(previous_payload, dict) and "value" in previous_payload:
        payload = copy.deepcopy(previous_payload)
        payload["value"] = copy.deepcopy(value)
        return payload
    return primitive_value_payload(value)
