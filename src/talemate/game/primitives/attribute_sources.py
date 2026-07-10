"""Source-specific helpers for primitive attribute resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import pydantic

from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    relationship_participants,
)
from talemate.game.primitives.conditions import conditions_match
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.selection import SelectionResult
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.values import primitive_payload_value

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

SelectionResultField = Literal["text", "label", "variables", "result", "result_id"]
"""Field selector for extracting data from deck or roll-table selection results.

Supported values:
    text: Extracts the selected result prose text.
    label: Extracts the selected result display label.
    variables: Extracts the selected result variable payload.
    result: Extracts the full serialized selection result.
    result_id: Extracts the selected result identifier.
"""


class DeckAttributeOptions(pydantic.BaseModel):
    """Validated options for deck-backed primitive attributes.

    Attributes:
        mode: Deck operation used during resolution. ``draw`` mutates deck state;
            ``peek`` returns runtime state without drawing.
        result_field: Optional field extracted from a draw selection result.
        include_tags: Tags every drawable card must contain.
        exclude_tags: Tags drawable cards must not contain.
        avoid_recent: Optional non-negative count of recent card ids to avoid.
        anchor: Optional owner anchor used when resolving deck definition ids.
        instance_id: Optional deck primitive id used for runtime state.
        apply_effects: Whether selected card effects run immediately.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["draw", "peek"] = "draw"
    result_field: SelectionResultField | None = None
    include_tags: list[str] = pydantic.Field(default_factory=list)
    exclude_tags: list[str] = pydantic.Field(default_factory=list)
    avoid_recent: pydantic.StrictInt | None = None
    anchor: str | None = None
    instance_id: str | None = None
    apply_effects: pydantic.StrictBool = False

    @pydantic.model_validator(mode="after")
    def validate_avoid_recent(self) -> "DeckAttributeOptions":
        """Validate non-negative recent-card avoidance and mode-specific options.

        Returns:
            The validated deck attribute options.

        Raises:
            ValueError: If ``avoid_recent`` is negative or ``peek`` mode includes
                options that only affect drawing.
        """
        if self.avoid_recent is not None and self.avoid_recent < 0:
            raise ValueError("avoid_recent must be >= 0")
        if self.mode == "peek":
            ignored = []
            if self.result_field is not None:
                ignored.append("result_field")
            if self.include_tags:
                ignored.append("include_tags")
            if self.exclude_tags:
                ignored.append("exclude_tags")
            if self.avoid_recent is not None:
                ignored.append("avoid_recent")
            if self.apply_effects:
                ignored.append("apply_effects")
            if ignored:
                raise ValueError(
                    "Deck attribute peek mode does not accept draw options: "
                    + ", ".join(ignored)
                )
        return self


class RollTableAttributeOptions(pydantic.BaseModel):
    """Validated options for roll-table-backed primitive attributes.

    Attributes:
        result_field: Optional field extracted from a roll selection result.
        anchor: Optional anchor used when resolving table definition ids.
        apply_effects: Whether selected row effects run immediately.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    result_field: SelectionResultField | None = None
    anchor: str | None = None
    apply_effects: pydantic.StrictBool = False


class RelationshipAttributeOptions(pydantic.BaseModel):
    """Validated options for relationship-backed primitive attributes.

    Attributes:
        mode: Relationship resolution mode. ``value`` reads a relationship meter;
            ``summary`` renders relationship prose for a relationship anchor.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["value", "summary"] = "value"


class EmptyAttributeOptions(pydantic.BaseModel):
    """Validated empty option payload for sources without configurable options.

    The model forbids extra fields so literal, meter, clock, modifier, and
    state-reference attribute sources cannot silently accept unsupported options.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)


def validated_options(source: Any) -> dict[str, pydantic.JsonValue]:
    """Validate and normalize option payloads for a primitive attribute source.

    Args:
        source: Attribute source object with ``source`` and ``options`` attributes.
            The ``source`` attribute selects the source-specific option schema.

    Returns:
        JSON-compatible options dictionary validated against the schema for the
        selected source kind.

    Raises:
        pydantic.ValidationError: If the option payload contains unsupported fields
            or values for the selected source kind.
    """
    if source.source == "deck":
        return DeckAttributeOptions.model_validate(source.options).model_dump(
            mode="json", exclude_none=True
        )
    if source.source == "roll_table":
        return RollTableAttributeOptions.model_validate(source.options).model_dump(
            mode="json", exclude_none=True
        )
    if source.source == "relationship":
        return RelationshipAttributeOptions.model_validate(source.options).model_dump(
            mode="json", exclude_none=True
        )
    return EmptyAttributeOptions.model_validate(source.options).model_dump(mode="json")


def validate_context(context: dict[str, Any] | None) -> dict[str, pydantic.JsonValue]:
    """Validate attribute resolution context metadata.

    Args:
        context: Optional dictionary supplied by a resolver or node caller.

    Returns:
        JSON-compatible context dictionary. ``None`` becomes an empty dictionary.

    Raises:
        pydantic.ValidationError: If ``context`` is not a JSON-compatible mapping.
    """
    return pydantic.TypeAdapter(dict[str, pydantic.JsonValue]).validate_python(
        {} if context is None else context
    )


def resolve_primitive_value(
    scene: "Scene", source: Any, expected_kind: str
) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
    """Resolve a scalar primitive payload for meter and clock attributes.

    Args:
        scene: Talemate scene containing primitive state.
        source: Attribute source object with ``id``, ``ref``, and ``source`` fields.
        expected_kind: Primitive kind required by the source, such as ``meters``.

    Returns:
        Tuple of resolved JSON value, optional pre-rendered text, and debug payload.

    Raises:
        PrimitiveError: If the source reference is missing, uses the wrong primitive
            kind, or points to a missing primitive.
        InvalidPrimitiveRef: If the source reference cannot be parsed.
    """
    ref = PrimitiveRef.parse(require_source_ref(source))
    if ref.kind != expected_kind:
        raise PrimitiveError(
            f"Attribute source '{source.id}' requires {expected_kind} ref"
        )
    payload = PrimitiveStore.for_scene(scene).get_primitive(ref)
    if payload is None:
        raise PrimitiveError(f"Primitive not found: {ref.key()}")
    return (
        primitive_payload_value(payload),
        None,
        {"source": source.source, "ref": ref.key()},
    )


def resolve_modifier(
    scene: "Scene", source: Any
) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
    """Resolve a roll modifier value when its conditions are active.

    Args:
        scene: Talemate scene containing primitive state.
        source: Attribute source object whose ``ref`` points to a modifier
            definition id or modifier primitive reference.

    Returns:
        Tuple of active modifier value, no pre-rendered text, and debug payload.

    Raises:
        PrimitiveError: If the modifier reference is missing or cannot be found.
        pydantic.ValidationError: If the modifier payload is invalid.
    """
    store = PrimitiveStore.for_scene(scene)
    ref_text = require_source_ref(source)
    if "/" in ref_text:
        payload = store.get_primitive(ref_text)
    else:
        payload = store.get_definition("modifiers", ref_text)
    if payload is None:
        raise PrimitiveError(f"Modifier not found: {ref_text}")
    modifier = RollModifier.model_validate(primitive_payload_value(payload))
    active = conditions_match(scene, modifier.when)
    return (
        modifier.add if active else 0,
        None,
        {"source": "modifier", "modifier": modifier.id, "active": active},
    )


def resolve_state_ref(
    scene: "Scene", source: Any
) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
    """Resolve a slash-delimited value from scene game-state variables.

    Args:
        scene: Talemate scene containing ``game_state.variables``.
        source: Attribute source object whose ``ref`` is a slash-delimited path.

    Returns:
        Tuple of resolved JSON value, no pre-rendered text, and debug payload.

    Raises:
        PrimitiveError: If the reference is missing, contains an empty path segment,
            or points to a missing game-state path.
        pydantic.ValidationError: If the resolved value is not JSON-compatible.
    """
    current: Any = scene.game_state.variables
    for part in require_source_ref(source).split("/"):
        if not part:
            raise PrimitiveError("State reference path segments cannot be empty")
        if not isinstance(current, dict) or part not in current:
            raise PrimitiveError(f"State reference not found: {source.ref}")
        current = current[part]
    value = pydantic.TypeAdapter(pydantic.JsonValue).validate_python(current)
    return value, None, {"source": "state_ref", "ref": source.ref}


def resolve_deck_source(
    scene: "Scene",
    source: Any,
    context: dict[str, pydantic.JsonValue],
    deck_engine: Any,
) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
    """Resolve a deck-backed primitive attribute source.

    Args:
        scene: Talemate scene containing primitive state.
        source: Attribute source whose ``ref`` identifies a deck definition or instance.
        context: JSON-compatible trace metadata passed to draw operations.
        deck_engine: Deck engine used to peek or draw the source deck.

    Returns:
        Tuple of resolved value, optional rendered text, and debug payload.

    Raises:
        PrimitiveError: If deck resolution, draw, field extraction, or effects fail.
        pydantic.ValidationError: If deck options are invalid.
    """
    options = DeckAttributeOptions.model_validate(source.options)
    if options.mode == "peek":
        value = deck_engine.peek(
            scene,
            source.ref,
            anchor=options.anchor,
            instance_id=options.instance_id,
        )
        return value, None, {"source": "deck", "mode": options.mode}
    result = deck_engine.draw(
        scene,
        source.ref,
        anchor=options.anchor,
        instance_id=options.instance_id,
        options={
            "include_tags": options.include_tags,
            "exclude_tags": options.exclude_tags,
            "avoid_recent": options.avoid_recent,
            "context": context,
            "apply_effects": options.apply_effects,
        },
    )
    value = selection_result_field(result, options.result_field)
    return value, selection_rendered_text(result, options.result_field), result.debug


def resolve_roll_table_source(
    scene: "Scene",
    source: Any,
    context: dict[str, pydantic.JsonValue],
    roll_table_engine: Any,
) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
    """Resolve a roll-table-backed primitive attribute source.

    Args:
        scene: Talemate scene containing primitive state.
        source: Attribute source whose ``ref`` identifies a roll table.
        context: JSON-compatible trace metadata passed to roll operations.
        roll_table_engine: Roll table engine used to resolve the table.

    Returns:
        Tuple of resolved value, optional rendered text, and debug payload.

    Raises:
        PrimitiveError: If roll-table resolution, rolling, field extraction, or
            effects fail.
        pydantic.ValidationError: If roll-table options are invalid.
    """
    options = RollTableAttributeOptions.model_validate(source.options)
    result = roll_table_engine.roll(
        scene,
        source.ref,
        anchor=options.anchor,
        context=context,
        apply_effects=options.apply_effects,
    )
    value = selection_result_field(result, options.result_field)
    return value, selection_rendered_text(result, options.result_field), result.debug


def resolve_relationship_source(
    scene: "Scene", source: Any, relationship_graph: Any
) -> tuple[pydantic.JsonValue | None, str | None, dict[str, pydantic.JsonValue]]:
    """Resolve a relationship-backed primitive attribute source.

    Args:
        scene: Talemate scene containing relationship primitive state.
        source: Attribute source whose ``ref`` is a relationship anchor or meter ref.
        relationship_graph: Relationship graph used to read values and summaries.

    Returns:
        Tuple of resolved value, optional relationship summary, and debug payload.

    Raises:
        PrimitiveError: If the source reference is not a relationship anchor or meter.
        InvalidAnchorRef: If a relationship anchor cannot be parsed.
        InvalidPrimitiveRef: If a relationship meter reference cannot be parsed.
        pydantic.ValidationError: If relationship attribute options are invalid.
    """
    options = RelationshipAttributeOptions.model_validate(source.options)
    source_ref = require_source_ref(source)
    if "/" not in source_ref:
        anchor = AnchorRef.parse(source_ref)
        if anchor.kind != "relationship":
            raise PrimitiveError("Relationship attribute requires relationship ref")
        if options.mode != "summary":
            raise PrimitiveError(
                "Relationship anchor attributes require mode='summary'"
            )
        source_id, target_id = relationship_participants(anchor)
        summary = relationship_graph.summary(scene, source_id, target_id)
        return summary, summary, {"source": "relationship", "mode": "summary"}
    ref = PrimitiveRef.parse(source_ref)
    if ref.anchor.kind != "relationship" or ref.kind != "meters":
        raise PrimitiveError("Relationship attribute requires relationship meter ref")
    source_id, target_id = relationship_participants(ref.anchor)
    value = relationship_graph.get(scene, source_id, target_id, ref.id)
    summary = relationship_graph.summary(scene, source_id, target_id)
    if options.mode == "summary":
        return summary, summary or None, {"source": "relationship", "mode": "summary"}
    return value, summary or None, {"source": "relationship", "dimension": ref.id}


def selection_result_field(
    result: SelectionResult, field: SelectionResultField | None
) -> pydantic.JsonValue | None:
    """Return the requested JSON-compatible field from a selection result.

    Args:
        result: Selection result produced by a deck or roll table.
        field: Optional field name to extract. ``None`` returns the full result.

    Returns:
        JSON-compatible selected field value.

    Raises:
        PrimitiveError: If a requested field is absent or unsupported.
    """
    payload = result.model_dump(mode="json", exclude_none=True)
    if field is None or field == "result":
        return payload
    if field == "text":
        if result.text is None:
            raise PrimitiveError("Selection result field 'text' is absent")
        return result.text
    if field == "label":
        if result.label is None:
            raise PrimitiveError("Selection result field 'label' is absent")
        return result.label
    if field == "variables":
        return payload.get("variables", {})
    if field == "result_id":
        if result.result_id is None:
            raise PrimitiveError("Selection result field 'result_id' is absent")
        return result.result_id
    raise PrimitiveError(f"Unsupported selection result field: {field}")


def selection_rendered_text(
    result: SelectionResult, field: SelectionResultField | None
) -> str | None:
    """Return prompt-safe text for a selection result when requested.

    Args:
        result: Selection result produced by a deck or roll table.
        field: Optional selected field name.

    Returns:
        Text or label when that field was requested, otherwise ``None``.
    """
    if field == "text":
        return result.text
    if field == "label":
        return result.label
    return None


def require_source_ref(source: Any) -> str:
    """Return a non-empty source reference from an attribute source.

    Args:
        source: Attribute source object with ``id`` and ``ref`` attributes.

    Returns:
        Non-empty source reference string.

    Raises:
        PrimitiveError: If the source reference is missing.
    """
    if not source.ref:
        raise PrimitiveError(f"Attribute source {source.id} requires ref")
    return source.ref
