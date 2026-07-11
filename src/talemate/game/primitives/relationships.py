"""Directional relationship graph models and prompt-safe summary rendering."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pydantic

from talemate.game.primitives.anchors import (
    PrimitiveRef,
    relationship_anchor,
    relationship_participants,
)
from talemate.game.primitives.definitions import MeterPayload
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.render import RenderPolicy
from talemate.game.primitives.store import PrimitiveStore, PrimitiveStoreReader

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

_MISSING = object()


def relationship_meter(**payload: object) -> MeterPayload:
    """Build a canonical meter with relationship-specific defaults.

    Args:
        **payload: Meter fields. Missing ``value``, ``min``, ``max``, and
            ``render_policy`` fields default to ``0``, ``-5``, ``5``, and
            ``"summary"``, respectively.

    Returns:
        A validated canonical meter payload.

    Raises:
        pydantic.ValidationError: If the payload contains unknown fields or
            violates the canonical meter schema.

    """
    payload.setdefault("value", 0)
    payload.setdefault("min", -5)
    payload.setdefault("max", 5)
    payload.setdefault("render_policy", "summary")
    return MeterPayload.model_validate(payload)


class RelationshipSetRequest(pydantic.BaseModel):
    """Validated request for setting one relationship dimension.

    Attributes:
        source: Source participant for the directed relationship edge.
        target: Target participant for the directed relationship edge.
        dimension: Non-empty meter id to store under the relationship anchor.
        value: Finite numeric value to store.
        min: Inclusive finite lower bound for ``value``.
        max: Inclusive finite upper bound for ``value``.
        label: Optional human-readable label for summary rendering.
        render_policy: Visibility policy for prompt-safe summaries.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    source: str = pydantic.Field(min_length=1)
    target: str = pydantic.Field(min_length=1)
    dimension: str = pydantic.Field(min_length=1)
    value: pydantic.StrictInt | pydantic.StrictFloat
    min: pydantic.StrictInt | pydantic.StrictFloat = -5
    max: pydantic.StrictInt | pydantic.StrictFloat = 5
    label: str | None = None
    render_policy: RenderPolicy = "summary"

    @pydantic.model_validator(mode="after")
    def validate_request(self) -> "RelationshipSetRequest":
        """Validate numeric bounds and relationship anchor syntax."""
        relationship_anchor(self.source, self.target)
        relationship_meter(
            id=self.dimension,
            value=self.value,
            min=self.min,
            max=self.max,
            label=self.label,
            render_policy=self.render_policy,
        )
        return self


class RelationshipAdjustRequest(pydantic.BaseModel):
    """Validated request for adjusting one relationship dimension.

    Attributes:
        source: Source participant for the directed relationship edge.
        target: Target participant for the directed relationship edge.
        dimension: Non-empty meter id to adjust.
        by: Finite numeric delta added to the current value.
        min: Inclusive finite lower bound used for a new dimension.
        max: Inclusive finite upper bound used for a new dimension.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    source: str = pydantic.Field(min_length=1)
    target: str = pydantic.Field(min_length=1)
    dimension: str = pydantic.Field(min_length=1)
    by: pydantic.StrictInt | pydantic.StrictFloat
    min: pydantic.StrictInt | pydantic.StrictFloat = -5
    max: pydantic.StrictInt | pydantic.StrictFloat = 5

    @pydantic.model_validator(mode="after")
    def validate_request(self) -> "RelationshipAdjustRequest":
        """Validate finite delta, bounds, and relationship anchor syntax."""
        relationship_anchor(self.source, self.target)
        _require_finite("by", self.by)
        _require_finite("min", self.min)
        _require_finite("max", self.max)
        if self.min > self.max:
            raise ValueError("Relationship minimum cannot exceed maximum")
        return self


class RelationshipLedgerOutput(pydantic.BaseModel):
    """Validated relationship mutation ledger output payload.

    Attributes:
        previous: Previous finite numeric dimension value, or ``None``.
        current: Current finite numeric dimension value after mutation.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    previous: pydantic.StrictInt | pydantic.StrictFloat | None = None
    current: pydantic.StrictInt | pydantic.StrictFloat


class RelationshipSetNodeOutput(pydantic.BaseModel):
    """Validated output emitted by relationship set and adjust nodes.

    Attributes:
        value: Stored finite numeric dimension value.
        anchor: Relationship anchor key for the directed edge.
        summary: Prompt-safe prose summary generated after mutation.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    value: pydantic.StrictInt | pydantic.StrictFloat
    anchor: str
    summary: str


class RelationshipAdjustNodeOutput(RelationshipSetNodeOutput):
    """Validated relationship adjust node output payload.

    Attributes:
        previous: Previous finite numeric dimension value, or ``None``.
    """

    previous: pydantic.StrictInt | pydantic.StrictFloat | None = None


class RelationshipGetNodeOutput(pydantic.BaseModel):
    """Validated relationship get node output payload.

    Attributes:
        value: Stored or explicitly defaulted finite numeric dimension value.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    value: pydantic.StrictInt | pydantic.StrictFloat


class RelationshipSummaryNodeOutput(pydantic.BaseModel):
    """Validated relationship summary node output payload.

    Attributes:
        summary: Prompt-safe prose summary for one directional edge.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    summary: str


class RelationshipRelevantNodeOutput(pydantic.BaseModel):
    """Validated relevant relationship summaries node output payload.

    Attributes:
        summaries: Non-empty prompt-safe summaries for matching outbound edges.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    summaries: list[str]


class RelationshipGraph:
    """Manages directional relationship state stored as relationship anchors.

    A relationship anchor represents one directed edge from a source participant
    to a target participant, such as ``relationship:Alice->Bob``. The reverse
    edge is stored independently. Dimensions are bounded numeric meters attached
    to the relationship anchor and rendered as prompt-safe prose when visible.
    """

    def edge(
        self, scene: "Scene", source: str, target: str, create: bool = False
    ) -> dict | None:
        """Return the primitive-store payload for one directional edge.

        Args:
            scene: Talemate scene containing primitive state.
            source: Source participant for the directed edge.
            target: Target participant for the directed edge.
            create: Whether to create the anchor when absent.

        Returns:
            Anchor payload dictionary, or ``None`` when absent and not created.
        """
        store = PrimitiveStore.for_scene(scene)
        return store.get_anchor(relationship_anchor(source, target), create=create)

    def get(
        self,
        scene: "Scene",
        source: str,
        target: str,
        dimension: str,
        default=_MISSING,
        *,
        store: PrimitiveStoreReader | None = None,
    ):
        """Return one stored dimension value for a directional edge.

        Args:
            scene: Talemate scene containing primitive state.
            source: Source participant for the directed edge.
            target: Target participant for the directed edge.
            dimension: Non-empty relationship dimension id.
            default: Explicit fallback returned when the dimension is absent.
            store: Optional already validated primitive store.

        Returns:
            Stored finite numeric dimension value, or explicit fallback.

        Raises:
            PrimitiveError: If the dimension is absent and no default is given.
            pydantic.ValidationError: If stored payload validation fails.
        """
        store = store or PrimitiveStore.for_scene(scene)
        ref = _dimension_ref(source, target, dimension)
        payload = store.get_primitive(ref)
        if payload is None:
            if default is _MISSING:
                raise PrimitiveError(f"Relationship dimension not found: {ref.key()}")
            _require_finite("default", default)
            return default
        return _dimension_from_payload(dimension, payload).value

    def set(
        self,
        scene: "Scene",
        source: str,
        target: str,
        dimension: str,
        value: int | float,
        *,
        min: int | float = -5,
        max: int | float = 5,
        label: str | None = None,
        render_policy: RenderPolicy = "summary",
    ) -> MeterPayload:
        """Store one bounded dimension value and record a ledger entry.

        Args:
            scene: Talemate scene containing primitive state.
            source: Source participant for the directed edge.
            target: Target participant for the directed edge.
            dimension: Non-empty relationship dimension id.
            value: Finite numeric value to persist.
            min: Inclusive finite lower bound.
            max: Inclusive finite upper bound.
            label: Optional label used by summary rendering.
            render_policy: Visibility policy for summaries.

        Returns:
            Persisted relationship dimension model.

        Raises:
            ValueError: If bounds or value are invalid.
            pydantic.ValidationError: If request validation fails.

        Side Effects:
            Persists the dimension payload and appends ``relationship.set``.
        """
        request = RelationshipSetRequest.model_validate(
            {
                "source": source,
                "target": target,
                "dimension": dimension,
                "value": value,
                "min": min,
                "max": max,
                "label": label,
                "render_policy": render_policy,
            }
        )
        store = PrimitiveStore.for_scene(scene)
        ref = _dimension_ref(request.source, request.target, request.dimension)
        previous_payload = store.get_primitive(ref)
        previous_dimension = _dimension_from_payload(
            request.dimension, previous_payload
        )
        previous = previous_dimension.value if previous_dimension else None
        model = relationship_meter(
            id=request.dimension,
            value=request.value,
            min=request.min,
            max=request.max,
            label=request.label,
            render_policy=request.render_policy,
        )
        ledger = LedgerEntry(
            op="relationship.set",
            anchor=ref.anchor.key(),
            ref=ref.key(),
            input=request.model_dump(mode="json", exclude_none=True),
            output=RelationshipLedgerOutput(
                previous=previous, current=model.value
            ).model_dump(mode="json", exclude_none=True),
        )
        store.set_runtime_primitive(ref, model.model_dump(mode="json"))
        store.append_ledger(ledger)
        return model

    def adjust(
        self,
        scene: "Scene",
        source: str,
        target: str,
        dimension: str,
        by: int | float,
        *,
        min: int | float = -5,
        max: int | float = 5,
    ) -> tuple[MeterPayload, int | float | None]:
        """Add a numeric delta to one relationship dimension.

        Args:
            scene: Talemate scene containing primitive state.
            source: Source participant for the directed edge.
            target: Target participant for the directed edge.
            dimension: Non-empty relationship dimension id.
            by: Finite numeric delta to apply.
            min: Inclusive lower bound for a new dimension.
            max: Inclusive upper bound for a new dimension.

        Returns:
            Tuple of persisted dimension and previous value.

        Raises:
            pydantic.ValidationError: If the participant identifiers, numeric delta,
                bounds, persisted payload, or resulting bounded dimension value violates
                relationship validation rules.

        Side Effects:
            Persists the dimension payload and appends ``relationship.adjust``.
        """
        request = RelationshipAdjustRequest.model_validate(
            {
                "source": source,
                "target": target,
                "dimension": dimension,
                "by": by,
                "min": min,
                "max": max,
            }
        )
        store = PrimitiveStore.for_scene(scene)
        ref = _dimension_ref(request.source, request.target, request.dimension)
        previous_payload = store.get_primitive(ref)
        previous_dimension = _dimension_from_payload(
            request.dimension, previous_payload
        )
        previous = previous_dimension.value if previous_dimension else None
        base = 0 if previous is None else previous
        current = base + request.by
        render_policy = (
            previous_dimension.render_policy if previous_dimension else "summary"
        )
        label = previous_dimension.label if previous_dimension else None
        model = relationship_meter(
            id=request.dimension,
            value=current,
            min=previous_dimension.min if previous_dimension else request.min,
            max=previous_dimension.max if previous_dimension else request.max,
            label=label,
            render_policy=render_policy,
        )
        ledger = LedgerEntry(
            op="relationship.adjust",
            anchor=ref.anchor.key(),
            ref=ref.key(),
            input=request.model_dump(mode="json"),
            output=RelationshipLedgerOutput(
                previous=previous, current=model.value
            ).model_dump(mode="json", exclude_none=True),
        )
        store.set_runtime_primitive(ref, model.model_dump(mode="json"))
        store.append_ledger(ledger)
        return model, previous

    def summary(
        self,
        scene: "Scene",
        source: str,
        target: str,
        audience: str = "prompt",
        *,
        store: PrimitiveStoreReader | None = None,
    ) -> str:
        """Render prompt-safe prose for one directional relationship edge.

        Args:
            scene: Talemate scene containing primitive state.
            source: Source participant for the directed edge.
            target: Target participant for the directed edge.
            audience: Visibility audience; ``"prompt"`` includes ``summary`` and
                ``prompt`` render policies.
            store: Optional already validated primitive store.

        Returns:
            Prompt-safe prose without raw hidden dimension numbers.

        Raises:
            pydantic.ValidationError: If the participant identifiers violate
                relationship anchor validation rules or a persisted dimension payload is
                invalid.
        """
        visible = {"summary", "prompt"} if audience == "prompt" else {audience}
        parts = []
        for dimension in self._dimensions(scene, source, target, store=store):
            if dimension.render_policy not in visible:
                continue
            text = _default_summary(source, target, dimension)
            if text:
                parts.append(text)
        return " ".join(parts)

    def relevant_for(
        self, scene: "Scene", character: str, other: str | None = None
    ) -> list[str]:
        """Return prompt-safe summaries for outbound edges from one character.

        Args:
            scene: Talemate scene containing primitive state.
            character: Source participant whose outgoing edges should render.
            other: Optional target participant filter.

        Returns:
            Non-empty summaries for matching outbound relationship edges.

        Raises:
            PrimitiveError: If a persisted relationship anchor key cannot be parsed.
            pydantic.ValidationError: If a persisted dimension payload is invalid.
        """
        store = PrimitiveStore.for_scene(scene)
        summaries = []
        for anchor_key in store.iter_anchor_keys(kind="relationship"):
            source, target = relationship_participants(anchor_key)
            if source != character:
                continue
            if other is not None and target != other:
                continue
            summary = self.summary(scene, source, target)
            if summary:
                summaries.append(summary)
        return summaries

    def _dimensions(
        self,
        scene: "Scene",
        source: str,
        target: str,
        *,
        store: PrimitiveStoreReader | None = None,
    ) -> list[MeterPayload]:
        store = store or PrimitiveStore.for_scene(scene)
        anchor = relationship_anchor(source, target)
        return [
            _dimension_from_payload(dimension_id, payload)
            for dimension_id, payload in store.iter_primitives(anchor, "meters").items()
        ]


def _dimension_ref(source: str, target: str, dimension: str) -> PrimitiveRef:
    """Return the meter primitive reference for a relationship dimension."""
    return PrimitiveRef(
        anchor=relationship_anchor(source, target), kind="meters", id=dimension
    )


def _dimension_from_payload(
    dimension: str,
    payload: object | None,
) -> MeterPayload | None:
    """Return a validated dimension model from a primitive payload."""
    if payload is None:
        return None
    model = MeterPayload.model_validate(payload)
    if model.id != dimension:
        raise ValueError(
            f"Relationship meter key '{dimension}' must match id '{model.id}'"
        )
    return model


def relationship_value_payload(
    ref: PrimitiveRef, previous_payload: dict | None, value: int | float
) -> dict:
    """Build a validated relationship meter payload for an effect update.

    Args:
        ref: Primitive reference that must point to a relationship meter.
        previous_payload: Existing dimension payload whose metadata is preserved.
        value: Finite numeric value to store.

    Returns:
        JSON-serializable relationship dimension payload.

    Raises:
        PrimitiveError: If ``ref`` is not a relationship meter.
        pydantic.ValidationError: If ``previous_payload`` is invalid or ``value``
            violates finite numeric bounds preserved from the previous payload.
    """
    if ref.anchor.kind != "relationship" or ref.kind != "meters":
        raise PrimitiveError(
            "relationship_value_payload requires relationship meter ref"
        )
    previous = _dimension_from_payload(ref.id, previous_payload)
    model = relationship_meter(
        id=ref.id,
        value=value,
        min=previous.min if previous else -5,
        max=previous.max if previous else 5,
        label=previous.label if previous else None,
        render_policy=previous.render_policy if previous else "summary",
    )
    return model.model_dump(mode="json")


def _require_finite(name: str, value: int | float) -> None:
    """Raise when a numeric value is not finite."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _default_summary(source: str, target: str, dimension: MeterPayload) -> str:
    """Return generic prompt-safe prose for common relationship dimensions."""
    label = dimension.label or dimension.id.replace("_", " ")
    value = dimension.value
    if dimension.id == "trust":
        if value <= -3:
            phrase = "distrusts"
        elif value <= 0:
            phrase = "is guarded around"
        elif value <= 2:
            phrase = "is beginning to trust"
        else:
            phrase = "trusts"
        return f"{source} {phrase} {target}."
    if value > 0:
        return f"{source}'s {label} toward {target} is noticeable."
    if value < 0:
        return f"{source}'s {label} toward {target} is strained."
    return ""
