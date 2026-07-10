"""Primitive attributes resolved from deterministic Game Primitives sources.

Primitive attributes attach authored attribute sources to anchors under the
``attributes`` primitive kind. The resolver reads those sources and resolves
values from literal payloads, meters, relationships, decks, roll tables,
modifiers, clocks, or state references without writing to character prose fields.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Literal

import pydantic

from talemate.game.primitives.anchors import PrimitiveRef
from talemate.game.primitives.attribute_sources import (
    resolve_deck_source,
)
from talemate.game.primitives.attribute_sources import (
    resolve_modifier as _resolve_modifier,
)
from talemate.game.primitives.attribute_sources import (
    resolve_primitive_value as _resolve_primitive_value,
)
from talemate.game.primitives.attribute_sources import (
    resolve_relationship_source,
    resolve_roll_table_source,
)
from talemate.game.primitives.attribute_sources import (
    resolve_state_ref as _resolve_state_ref,
)
from talemate.game.primitives.attribute_sources import (
    validate_context as _validate_context,
)
from talemate.game.primitives.attribute_sources import (
    validated_options as _validated_options,
)
from talemate.game.primitives.conditions import (
    PrimitiveConditionGroup,
    conditions_match,
)
from talemate.game.primitives.decks import DeckEngine
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.render import (
    Audience,
    RenderPolicy,
    render_attribute_value,
    render_policy_visible,
)
from talemate.game.primitives.roll_tables import RollTableEngine
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

AttributeSourceKind = Literal[
    "literal",
    "deck",
    "roll_table",
    "meter",
    "clock",
    "relationship",
    "modifier",
    "state_ref",
]
"""Deterministic source kind used to compute a primitive attribute value.

Source values:
    literal: Uses the source's inline JSON-compatible value.
    deck: Draws from or peeks at a deck primitive.
    roll_table: Rolls a roll-table primitive.
    meter: Reads a meter primitive payload.
    clock: Reads a clock primitive payload.
    relationship: Reads or summarizes relationship primitive state.
    modifier: Reads a roll modifier when its conditions match.
    state_ref: Reads a slash-delimited path from scene game-state variables.
"""


class AttributeSource(pydantic.BaseModel):
    """Persisted primitive attribute source definition.

    Attributes:
        id: Stable non-empty attribute identifier under one anchor.
        label: Optional human-readable label used when rendering the attribute.
        source: Deterministic source kind used to resolve the value.
        render_policy: Visibility policy controlling prompt and memory rendering.
        value: Literal JSON-compatible value for ``literal`` sources.
        ref: Optional anchor, primitive, modifier, or state reference read by the
            selected source kind.
        options: JSON-compatible source-specific options.
        conditions: Primitive condition groups that gate resolution.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    label: str | None = None
    source: AttributeSourceKind
    render_policy: RenderPolicy = "hidden"
    value: pydantic.JsonValue | None = None
    ref: str | None = None
    options: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    conditions: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def validate_source_contract(self) -> "AttributeSource":
        """Validate source-specific reference and value requirements.

        Returns:
            The validated attribute source.

        Raises:
            ValueError: If the selected source kind lacks required data or has
                invalid source-specific options.
            pydantic.ValidationError: If source-specific options fail schema
                validation.
        """
        if self.source == "literal":
            if self.ref is not None:
                raise ValueError("Literal attribute sources cannot define ref")
            if "value" not in self.model_fields_set:
                raise ValueError("Literal attribute sources require explicit value")
            self.options = _validated_options(self)
            return self
        if "value" in self.model_fields_set:
            raise ValueError("Non-literal attribute sources cannot define value")
        if not self.ref or not self.ref.strip():
            raise ValueError(f"Attribute source '{self.source}' requires ref")
        self.options = _validated_options(self)
        return self


class AttributeResolution(pydantic.BaseModel):
    """Resolved primitive attribute value and render metadata.

    Attributes:
        ref: Canonical primitive attribute reference that was resolved.
        source: Source kind used for resolution.
        value: JSON-compatible resolved value, or ``None`` when conditions block
            resolution.
        rendered: Optional pre-rendered prompt-safe text from the source.
        render_policy: Visibility policy copied from the source definition.
        debug: JSON-compatible trace metadata explaining resolution.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    ref: str
    source: AttributeSourceKind
    value: pydantic.JsonValue | None = None
    rendered: str | None = None
    render_policy: RenderPolicy
    debug: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class AttributeSetRequest(pydantic.BaseModel):
    """Validated request for storing a primitive attribute source.

    Attributes:
        ref: Primitive reference whose kind must be ``attributes``.
        source: Attribute source payload to store at ``ref``.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    ref: PrimitiveRef
    source: AttributeSource

    @pydantic.model_validator(mode="before")
    @classmethod
    def populate_source_id(cls, value: object) -> object:
        """Populate a missing source id from the attribute primitive reference.

        Args:
            value: Raw request payload containing ``ref`` and ``source`` fields.

        Returns:
            Request payload with ``source.id`` present when the source was a
            mapping that omitted it.

        Raises:
            ValueError: If the request payload is not a mapping or cannot provide
                an attribute id for a source mapping.
            pydantic.ValidationError: If ``ref`` cannot be validated while deriving
                a missing source id.
        """
        if not isinstance(value, dict):
            raise ValueError("Attribute set request must be a dictionary")
        payload = copy.deepcopy(value)
        source = payload.get("source")
        if isinstance(source, AttributeSource):
            return payload
        if not isinstance(source, dict):
            raise ValueError("Attribute source must be a dictionary or model")
        source.setdefault("id", PrimitiveRef.model_validate(payload.get("ref")).id)
        payload["source"] = source
        return payload

    @pydantic.model_validator(mode="after")
    def validate_attribute_ref(self) -> "AttributeSetRequest":
        """Validate that an attribute set request writes a source under the source id.

        Returns:
            The validated attribute set request.

        Raises:
            ValueError: If ``ref`` does not target the ``attributes`` primitive kind or
                ``source.id`` does not match ``ref.id``.
        """
        _require_attribute_ref(self.ref)
        if self.source.id != self.ref.id:
            raise ValueError("Attribute source id must match attribute ref id")
        return self


class AttributeResolver:
    """Resolve primitive attributes from deterministic primitive sources.

    The resolver reads and writes ``attributes`` primitive payloads in
    ``PrimitiveStore`` and delegates deterministic mutations to the deck and roll
    table engines so those operations keep their own ledgers.
    """

    def __init__(
        self,
        deck_engine: DeckEngine | None = None,
        roll_table_engine: RollTableEngine | None = None,
        relationship_graph: RelationshipGraph | None = None,
    ):
        """Create an attribute resolver with optional source engines.

        Args:
            deck_engine: Deck engine used for deck-backed attributes.
            roll_table_engine: Roll table engine used for table-backed attributes.
            relationship_graph: Relationship graph used for relationship-backed
                attributes.
        """
        self.deck_engine = deck_engine if deck_engine is not None else DeckEngine()
        self.roll_table_engine = (
            roll_table_engine if roll_table_engine is not None else RollTableEngine()
        )
        self.relationship_graph = (
            relationship_graph
            if relationship_graph is not None
            else RelationshipGraph()
        )

    def set(
        self, scene: "Scene", ref: PrimitiveRef | str, source: AttributeSource | dict
    ) -> AttributeSource:
        """Persist one primitive attribute source.

        Args:
            scene: Talemate scene containing the primitive store.
            ref: Attribute primitive reference to write.
            source: Attribute source model or JSON-compatible source payload.

        Returns:
            Stored attribute source model.

        Raises:
            ValueError: If ``ref`` is not an attribute primitive reference.
            pydantic.ValidationError: If the source payload is invalid or
                ``source.id`` does not match ``ref.id``.
            PrimitiveStoreError: If the primitive store rejects the payload.
        """
        primitive_ref = _coerce_attribute_ref(ref)
        request = AttributeSetRequest.model_validate(
            {"ref": primitive_ref, "source": source}
        )
        source_payload = request.source.model_dump(mode="json", exclude_none=True)
        if (
            request.source.source == "literal"
            and "value" in request.source.model_fields_set
        ):
            source_payload["value"] = request.source.value
        PrimitiveStore.for_scene(scene).set_primitive(
            primitive_ref,
            source_payload,
        )
        return request.source

    def get(self, scene: "Scene", ref: PrimitiveRef | str) -> AttributeSource:
        """Return a stored primitive attribute source.

        Args:
            scene: Talemate scene containing the primitive store.
            ref: Attribute primitive reference to read.

        Returns:
            Stored attribute source model.

        Raises:
            PrimitiveError: If the attribute source is missing or persisted primitive
                store state is invalid.
            ValueError: If ``ref`` is not an attribute primitive reference.
            pydantic.ValidationError: If the stored source payload is invalid.
        """
        primitive_ref = _coerce_attribute_ref(ref)
        payload = PrimitiveStore.for_scene(scene).get_primitive(primitive_ref)
        if payload is None:
            raise PrimitiveError(f"Attribute source not found: {primitive_ref.key()}")
        return AttributeSource.model_validate(payload)

    def resolve(
        self,
        scene: "Scene",
        ref: PrimitiveRef | str,
        *,
        context: dict[str, Any] | None = None,
    ) -> AttributeResolution:
        """Resolve one primitive attribute source into a value.

        Args:
            scene: Talemate scene containing primitive state.
            ref: Attribute primitive reference to resolve.
            context: Optional JSON-compatible trace metadata copied into source
                engine calls.

        Returns:
            Attribute resolution containing value, render policy, and debug data.

        Raises:
            PrimitiveError: If the source cannot be resolved or the source engine
                reports a deterministic runtime failure.
            pydantic.ValidationError: If stored source or context payloads are invalid.
            ValueError: If ``ref`` is not an attribute primitive reference or condition
                evaluation encounters invalid condition data.
        """
        primitive_ref = _coerce_attribute_ref(ref)
        source = self.get(scene, primitive_ref)
        context_payload = _validate_context(context)
        if not conditions_match(scene, source.conditions):
            return AttributeResolution(
                ref=primitive_ref.key(),
                source=source.source,
                render_policy=source.render_policy,
                debug={"active": False, "reason": "conditions"},
            )
        value, rendered, debug = self._resolve_source(scene, source, context_payload)
        return AttributeResolution(
            ref=primitive_ref.key(),
            source=source.source,
            value=value,
            rendered=rendered,
            render_policy=source.render_policy,
            debug=debug,
        )

    def render(
        self,
        scene: "Scene",
        ref: PrimitiveRef | str,
        *,
        audience: str = "prompt",
        context: dict[str, Any] | None = None,
    ) -> str:
        """Render one primitive attribute for an audience.

        Args:
            scene: Talemate scene containing primitive state.
            ref: Attribute primitive reference to resolve and render.
            audience: Requested audience. Supported audiences are ``prompt`` and
                ``memory``.
            context: Optional JSON-compatible trace metadata copied into source
                engine calls.

        Returns:
            Prompt-safe rendered text, or an empty string when hidden or inactive.

        Raises:
            PrimitiveError: If the attribute source cannot be resolved.
            pydantic.ValidationError: If stored payloads, context, or audience are
                invalid.
            ValueError: If ``ref`` is not an attribute primitive reference, condition
                evaluation encounters invalid condition data, the render policy is
                unsupported, or a visible attribute resolves to ``None`` without
                pre-rendered text.
        """
        audience_value = _validate_audience(audience)
        resolution = self.resolve(scene, ref, context=context)
        source = self.get(scene, ref)
        return self.render_resolution(source, resolution, audience=audience_value)

    def render_resolution(
        self,
        source: AttributeSource,
        resolution: AttributeResolution,
        *,
        audience: str = "prompt",
    ) -> str:
        """Render an existing attribute resolution without resolving again.

        Args:
            source: Attribute source used to label fallback rendered text.
            resolution: Attribute resolution to render.
            audience: Requested audience. Supported audiences are ``prompt`` and
                ``memory``.

        Returns:
            Prompt-safe rendered text, or an empty string when hidden or inactive.

        Raises:
            pydantic.ValidationError: If ``audience`` is invalid.
            ValueError: If the render policy is unsupported, or if a
                visible attribute resolution has ``value=None`` without pre-rendered
                text.
        """
        audience_value = _validate_audience(audience)
        if resolution.debug.get("active") is False:
            return ""
        if not render_policy_visible(resolution.render_policy, audience_value):
            return ""
        if resolution.rendered:
            return resolution.rendered
        return render_attribute_value(
            source.label or source.id.replace("_", " ").title(),
            resolution.value,
            resolution.render_policy,
        )

    def _resolve_source(
        self,
        scene: "Scene",
        source: AttributeSource,
        context: dict[str, pydantic.JsonValue],
    ) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
        """Resolve a validated attribute source through the matching source engine.

        Args:
            scene: Talemate scene containing primitive state.
            source: Validated attribute source to resolve.
            context: JSON-compatible trace metadata passed to source engines.

        Returns:
            Tuple containing the resolved JSON-compatible value, optional
            pre-rendered text, and JSON-compatible debug metadata.

        Raises:
            PrimitiveError: If the source kind is unsupported or the selected source
                engine cannot resolve the source.
            pydantic.ValidationError: If source-specific payloads or resolved values
                are invalid.
        """
        if source.source == "literal":
            return copy.deepcopy(source.value), None, {"source": "literal"}
        if source.source == "meter":
            return _resolve_primitive_value(scene, source, "meters")
        if source.source == "clock":
            return _resolve_primitive_value(scene, source, "clocks")
        if source.source == "relationship":
            return resolve_relationship_source(scene, source, self.relationship_graph)
        if source.source == "deck":
            return resolve_deck_source(scene, source, context, self.deck_engine)
        if source.source == "roll_table":
            return resolve_roll_table_source(
                scene, source, context, self.roll_table_engine
            )
        if source.source == "modifier":
            return _resolve_modifier(scene, source)
        if source.source == "state_ref":
            return _resolve_state_ref(scene, source)
        raise PrimitiveError(f"Unsupported attribute source: {source.source}")


def _coerce_attribute_ref(ref: PrimitiveRef | str) -> PrimitiveRef:
    """Return a validated primitive attribute reference."""
    primitive_ref = ref if isinstance(ref, PrimitiveRef) else PrimitiveRef.parse(ref)
    _require_attribute_ref(primitive_ref)
    return primitive_ref


def _require_attribute_ref(ref: PrimitiveRef) -> None:
    """Raise when a primitive reference does not target ``attributes``."""
    if ref.kind != "attributes":
        raise ValueError("Attribute resolver requires an attributes primitive ref")


def _validate_audience(audience: str) -> Audience:
    """Return a validated attribute render audience."""
    return pydantic.TypeAdapter(Audience).validate_python(audience)
