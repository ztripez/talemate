"""Roll table definitions and resolution engine for Game Primitives."""

from __future__ import annotations

import copy
import itertools
import random
import re
from typing import TYPE_CHECKING, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.conditions import (
    PrimitiveConditionGroup,
    conditions_match,
)
from talemate.game.primitives.effects import Effect
from talemate.game.primitives.effects import apply_effects as apply_effect_batch
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.selection import SelectionResult
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.values import primitive_payload_value

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

_DICE_RE = re.compile(r"^(?P<count>[1-9][0-9]*)d(?P<sides>[1-9][0-9]*)$")
_RANGE_RE = re.compile(r"^(?P<start>-?[0-9]+)\s*-\s*(?P<end>-?[0-9]+)$")


class RollTableRow(pydantic.BaseModel):
    """Validated row selected from a dice or weighted roll table.

    Rows map either an inclusive dice total range or a weighted selection value
    to narrative output, variables, and optional primitive effects. Condition
    groups are evaluated before selection; failed rows are excluded.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    text: str | None = None
    range: str | int | None = None
    weight: pydantic.StrictInt | pydantic.StrictFloat | None = None
    tags: list[str] = pydantic.Field(default_factory=list)
    variables: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    effects: list[Effect] = pydantic.Field(default_factory=list)
    conditions: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)


class RollTableDefinition(pydantic.BaseModel):
    """Validated roll table definition for dice-total or weighted selection."""

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    id: str = pydantic.Field(min_length=1)
    name: str = pydantic.Field(min_length=1)
    mode: Literal["dice", "weighted"] = "dice"
    dice: str | None = None
    rows: list[RollTableRow]
    modifiers: list[str] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def validate_table_shape(self) -> "RollTableDefinition":
        """Validate mode-specific roll table requirements after model creation."""
        if not self.rows:
            raise ValueError("Roll table requires at least one row")
        if self.mode == "dice":
            if not self.dice:
                raise ValueError("Dice roll tables require dice")
            parse_dice(self.dice)
            _validate_dice_rows(self.rows)
        else:
            _validate_weighted_rows(self.rows)
        return self


class RollTableRollRequest(pydantic.BaseModel):
    """Validated graph/runtime request for executing one roll table roll.

    The ``context`` field is trace metadata copied into debug and ledger output;
    it does not influence row selection, conditions, modifiers, or effects.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    table: RollTableDefinition | dict[str, pydantic.JsonValue] | str
    anchor: str | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    apply_effects: pydantic.StrictBool = False


class RollTablePreviewRequest(pydantic.BaseModel):
    """Validated graph/runtime request for previewing roll table odds."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    table: RollTableDefinition | dict[str, pydantic.JsonValue] | str
    anchor: str | None = None


class RollModifierDebugEntry(pydantic.BaseModel):
    """Debug trace row for one active or inactive roll modifier."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str
    label: str | None = None
    value: pydantic.StrictInt | pydantic.StrictFloat
    active: bool
    reason: str


class RollTableLedgerInput(pydantic.BaseModel):
    """Validated roll-table ledger input payload."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    table: str
    dice: str | None = None
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class RollTableLedgerOutput(pydantic.BaseModel):
    """Validated roll-table ledger output payload."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    raw: pydantic.StrictInt | pydantic.StrictFloat | None = None
    rolls: list[int] = pydantic.Field(default_factory=list)
    modifiers: list[RollModifierDebugEntry] = pydantic.Field(default_factory=list)
    final: pydantic.StrictInt | pydantic.StrictFloat | None = None
    result_id: str | None = None


class RollTableDiceDebug(pydantic.BaseModel):
    """Validated debug trace for a dice roll table resolution."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["dice"] = "dice"
    dice: str
    rolls: list[int]
    raw: int
    modifiers: list[RollModifierDebugEntry] = pydantic.Field(default_factory=list)
    final: pydantic.StrictInt | pydantic.StrictFloat
    gaps: list[list[int]] = pydantic.Field(default_factory=list)
    inactive_rows: list[str] = pydantic.Field(default_factory=list)
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    applied_effects: dict[str, pydantic.JsonValue] | None = None


class RollTableWeightedDebug(pydantic.BaseModel):
    """Validated debug trace for a weighted roll table resolution."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["weighted"] = "weighted"
    total_weight: float
    threshold: float
    inactive_rows: list[str] = pydantic.Field(default_factory=list)
    context: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    applied_effects: dict[str, pydantic.JsonValue] | None = None


class OddsPreviewRow(pydantic.BaseModel):
    """Validated probability row for odds preview output."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str
    label: str
    probability: float
    weight: pydantic.StrictInt | pydantic.StrictFloat | None = None
    range: str | int | None = None
    outcomes: int | None = None


class OddsPreview(pydantic.BaseModel):
    """Validated odds preview output for dice and weighted roll tables."""

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    source_type: Literal["roll_table"] = "roll_table"
    source_id: str
    mode: Literal["dice", "weighted"]
    dice: str | None = None
    total_weight: float | None = None
    gaps: list[list[int]] = pydantic.Field(default_factory=list)
    rows: list[OddsPreviewRow] = pydantic.Field(default_factory=list)
    inactive_rows: list[str] = pydantic.Field(default_factory=list)


class WeightedPool(pydantic.BaseModel):
    """Internal weighted-row pool shared by rolling and odds preview."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    inactive_rows: list[RollTableRow]
    weighted_rows: list[RollTableRow]
    total_weight: float


def parse_dice(expression: str) -> tuple[int, int]:
    """Parse an ``NdM`` dice expression into dice count and side count."""
    if not isinstance(expression, str):
        raise ValueError("Dice expression must be a string")
    match = _DICE_RE.match(expression.strip())
    if match is None:
        raise ValueError("Dice expression must use NdM with positive integers")
    return int(match.group("count")), int(match.group("sides"))


def parse_range(value: str | int) -> tuple[int, int]:
    """Parse an inclusive roll table range from an integer or ``a-b`` string."""
    if isinstance(value, bool):
        raise ValueError("Range cannot be boolean")
    if isinstance(value, int):
        return value, value
    if not isinstance(value, str):
        raise ValueError("Range must be an integer or 'a-b' string")
    text = value.strip()
    if text.lstrip("-").isdigit():
        number = int(text)
        return number, number
    match = _RANGE_RE.match(text)
    if match is None:
        raise ValueError("Range string must be an integer or 'a-b'")
    start = int(match.group("start"))
    end = int(match.group("end"))
    if start > end:
        raise ValueError("Range start cannot exceed range end")
    return start, end


class RollTableEngine:
    """Resolve roll table selections against a Talemate scene."""

    def __init__(self, rng: random.Random | None = None):
        """Create a roll table engine with an optional random number source."""
        self.rng = rng if rng is not None else random.Random()

    def roll(
        self,
        scene: "Scene",
        table: RollTableDefinition | dict | str,
        *,
        anchor: AnchorRef | str | None = None,
        context: dict[str, pydantic.JsonValue] | None = None,
        apply_effects: bool = False,
    ) -> SelectionResult:
        """Select one row from a roll table and record the roll in the ledger.

        ``context`` is trace metadata copied into debug and ledger output; it
        does not influence row selection, conditions, modifiers, or effects.
        """
        if type(apply_effects) is not bool:
            raise TypeError("apply_effects must be a boolean")
        context_payload = _validate_context(context)
        store = PrimitiveStore.for_scene(scene)
        definition, source_id, resolved_anchor = self._resolve_table(
            store, table, anchor
        )
        if definition.mode == "dice":
            result = self._roll_dice_table(
                scene, store, definition, source_id, resolved_anchor, context_payload
            )
        else:
            result = self._roll_weighted_table(
                scene, definition, source_id, resolved_anchor, context_payload
            )

        store.append_ledger(
            LedgerEntry(
                op="roll_table.roll",
                ref=source_id if "/" in source_id else None,
                anchor=resolved_anchor,
                input=RollTableLedgerInput(
                    table=source_id, dice=definition.dice, context=context_payload
                ).model_dump(mode="json", exclude_none=True),
                output=RollTableLedgerOutput(
                    raw=result.debug.get("raw"),
                    rolls=result.debug.get("rolls", []),
                    modifiers=result.debug.get("modifiers", []),
                    final=result.debug.get("final"),
                    result_id=result.result_id,
                ).model_dump(mode="json", exclude_none=True),
            )
        )

        if apply_effects and result.effects:
            effect_result = apply_effect_batch(
                store, result.effects, reason=f"roll_table:{source_id}"
            )
            result.debug["applied_effects"] = effect_result.model_dump(
                mode="json", exclude_none=True
            )
            result_payload = result.model_dump(mode="python")
            result_payload["debug"] = _validate_debug_payload(result.debug)
            result = SelectionResult.model_validate(result_payload)
            if not effect_result.ok:
                raise PrimitiveError(
                    f"Roll table effects failed: {effect_result.results}"
                )
        return result

    def preview_odds(
        self,
        scene: "Scene",
        table: RollTableDefinition | dict | str,
        *,
        anchor: AnchorRef | str | None = None,
    ) -> dict[str, pydantic.JsonValue]:
        """Compute JSON-compatible odds without mutating primitive state."""
        store = PrimitiveStore.for_scene(scene)
        definition, source_id, _ = self._resolve_table(store, table, anchor)
        if definition.mode == "weighted":
            pool = _weighted_pool(scene, definition.rows)
            return OddsPreview(
                source_id=source_id,
                mode="weighted",
                total_weight=pool.total_weight,
                rows=[
                    OddsPreviewRow(
                        id=row.id,
                        label=row.label,
                        weight=row.weight,
                        probability=(
                            float(row.weight) / pool.total_weight
                            if pool.total_weight
                            else 0
                        ),
                    )
                    for row in pool.weighted_rows
                ],
                inactive_rows=[row.id for row in pool.inactive_rows],
            ).model_dump(mode="json", exclude_none=True)
        count, sides = parse_dice(definition.dice)
        active_rows, inactive_rows = _condition_filter(scene, definition.rows)
        distribution = _dice_distribution(count, sides)
        total_outcomes = sum(distribution.values())
        return OddsPreview(
            source_id=source_id,
            mode="dice",
            dice=definition.dice,
            gaps=_range_gaps(definition.rows, count, sides),
            rows=[
                OddsPreviewRow(
                    id=row.id,
                    label=row.label,
                    range=row.range,
                    outcomes=_row_outcome_count(row, distribution),
                    probability=_row_outcome_count(row, distribution) / total_outcomes,
                )
                for row in active_rows
            ],
            inactive_rows=[row.id for row in inactive_rows],
        ).model_dump(mode="json", exclude_none=True)

    def _roll_dice_table(
        self,
        scene: "Scene",
        store: PrimitiveStore,
        definition: RollTableDefinition,
        source_id: str,
        anchor: str | None,
        context: dict[str, pydantic.JsonValue],
    ) -> SelectionResult:
        count, sides = parse_dice(definition.dice)
        rolls = [
            _roll_die(self.rng, sides, source_id, definition.dice, index)
            for index in range(count)
        ]
        raw = sum(rolls)
        modifier_debug = self._resolve_modifiers(scene, store, definition, source_id)
        final = raw + sum(item.value for item in modifier_debug if item.active)
        active_rows, inactive_rows = _condition_filter(scene, definition.rows)
        selected = _match_dice_row(active_rows, final)
        if selected is None:
            raise PrimitiveError(f"Roll table {source_id} produced no matching row")
        debug = RollTableDiceDebug(
            dice=definition.dice,
            rolls=rolls,
            raw=raw,
            modifiers=modifier_debug,
            final=final,
            gaps=_range_gaps(definition.rows, count, sides),
            inactive_rows=[row.id for row in inactive_rows],
            context=context,
        ).model_dump(mode="json", exclude_none=True)
        return _selection_from_row(source_id, anchor, selected, debug)

    def _roll_weighted_table(
        self,
        scene: "Scene",
        definition: RollTableDefinition,
        source_id: str,
        anchor: str | None,
        context: dict[str, pydantic.JsonValue],
    ) -> SelectionResult:
        pool = _weighted_pool(scene, definition.rows)
        if pool.total_weight <= 0:
            raise PrimitiveError(
                f"Roll table {source_id} has no selectable weighted rows"
            )
        random_value = _weighted_random(self.rng, source_id)
        threshold = random_value * pool.total_weight
        cumulative = 0.0
        selected: RollTableRow | None = None
        for row in pool.weighted_rows:
            cumulative += float(row.weight)
            if threshold < cumulative:
                selected = row
                break
        if selected is None:
            raise PrimitiveError(f"Roll table {source_id} failed weighted selection")
        debug = RollTableWeightedDebug(
            total_weight=pool.total_weight,
            threshold=threshold,
            inactive_rows=[row.id for row in pool.inactive_rows],
            context=context,
        ).model_dump(mode="json", exclude_none=True)
        return _selection_from_row(source_id, anchor, selected, debug)

    def _resolve_table(
        self,
        store: PrimitiveStore,
        table: RollTableDefinition | dict | str,
        anchor: AnchorRef | str | None,
    ) -> tuple[RollTableDefinition, str, str | None]:
        if isinstance(table, (RollTableDefinition, dict)):
            definition = RollTableDefinition.model_validate(table)
            return definition, definition.id, _anchor_key(anchor)

        if not isinstance(table, str) or not table.strip():
            raise PrimitiveError("Roll table must be a definition, dict, or string")

        table_text = table.strip()
        if anchor is not None and "/" not in table_text:
            anchored_ref = PrimitiveRef(
                anchor=AnchorRef.model_validate(anchor),
                kind="roll_tables",
                id=table_text,
            )
            payload = store.get_primitive(anchored_ref)
            if payload is not None:
                definition = RollTableDefinition.model_validate(
                    primitive_payload_value(payload)
                )
                return definition, anchored_ref.key(), anchored_ref.anchor.key()

        if "/" in table_text:
            ref = PrimitiveRef.parse(table_text)
            payload = store.get_primitive(ref)
            if payload is None:
                raise PrimitiveError(f"Roll table primitive not found: {ref.key()}")
            definition = RollTableDefinition.model_validate(
                primitive_payload_value(payload)
            )
            return definition, ref.key(), ref.anchor.key()

        payload = store.get_definition("roll_tables", table_text)
        if payload is None:
            raise PrimitiveError(f"Roll table definition not found: {table_text}")
        definition = RollTableDefinition.model_validate(payload)
        return definition, definition.id, _anchor_key(anchor)

    def _resolve_modifiers(
        self,
        scene: "Scene",
        store: PrimitiveStore,
        definition: RollTableDefinition,
        source_id: str,
    ) -> list[RollModifierDebugEntry]:
        debug: list[RollModifierDebugEntry] = []
        for modifier_ref in definition.modifiers:
            modifier = _lookup_modifier(store, modifier_ref)
            applies = modifier.applies_to in {definition.id, source_id}
            active = applies and conditions_match(scene, modifier.when)
            debug.append(
                RollModifierDebugEntry(
                    id=modifier.id,
                    label=modifier.label,
                    value=modifier.add if active else 0,
                    active=active,
                    reason="active" if active else "inactive",
                )
            )
        return debug


def _validate_dice_rows(rows: list[RollTableRow]) -> None:
    ranges: list[tuple[str, int, int]] = []
    for row in rows:
        if row.range is None:
            raise ValueError(f"Dice row {row.id} requires range")
        start, end = parse_range(row.range)
        ranges.append((row.id, start, end))
    for index, (row_id, start, end) in enumerate(ranges):
        for other_id, other_start, other_end in ranges[index + 1 :]:
            if start <= other_end and other_start <= end:
                raise ValueError(f"Roll table ranges overlap: {row_id} and {other_id}")


def _validate_weighted_rows(rows: list[RollTableRow]) -> None:
    for row in rows:
        if row.weight is None or row.weight <= 0:
            raise ValueError(f"Weighted row {row.id} requires weight > 0")


def _condition_filter(
    scene: "Scene", rows: list[RollTableRow]
) -> tuple[list[RollTableRow], list[RollTableRow]]:
    active: list[RollTableRow] = []
    inactive: list[RollTableRow] = []
    for row in rows:
        if conditions_match(scene, row.conditions):
            active.append(row)
        else:
            inactive.append(row)
    return active, inactive


def _weighted_pool(scene: "Scene", rows: list[RollTableRow]) -> WeightedPool:
    """Return active weighted rows and their total after condition filtering."""
    active_rows, inactive_rows = _condition_filter(scene, rows)
    weighted_rows = [row for row in active_rows if row.weight and row.weight > 0]
    return WeightedPool(
        inactive_rows=inactive_rows,
        weighted_rows=weighted_rows,
        total_weight=sum(float(row.weight) for row in weighted_rows),
    )


def _match_dice_row(
    rows: list[RollTableRow], value: int | float
) -> RollTableRow | None:
    for row in rows:
        start, end = parse_range(row.range)
        if start <= value <= end:
            return row
    return None


def _range_gaps(rows: list[RollTableRow], count: int, sides: int) -> list[list[int]]:
    covered: set[int] = set()
    for row in rows:
        if row.range is None:
            continue
        start, end = parse_range(row.range)
        covered.update(range(start, end + 1))
    gaps: list[list[int]] = []
    gap_start: int | None = None
    for value in range(count, count * sides + 1):
        if value not in covered and gap_start is None:
            gap_start = value
        elif value in covered and gap_start is not None:
            gaps.append([gap_start, value - 1])
            gap_start = None
    if gap_start is not None:
        gaps.append([gap_start, count * sides])
    return gaps


def _dice_distribution(count: int, sides: int) -> dict[int, int]:
    distribution: dict[int, int] = {}
    for rolls in itertools.product(range(1, sides + 1), repeat=count):
        total = sum(rolls)
        distribution[total] = distribution.get(total, 0) + 1
    return distribution


def _roll_die(
    rng: random.Random, sides: int, source_id: str, dice: str, index: int
) -> int:
    """Roll one die and validate the injected random source output."""
    value = rng.randint(1, sides)
    if type(value) is not int or not 1 <= value <= sides:
        raise PrimitiveError(
            f"Roll table {source_id} dice {dice} produced invalid roll "
            f"at index {index}: {value}"
        )
    return value


def _weighted_random(rng: random.Random, source_id: str) -> float:
    """Return a validated weighted-roll random value from the RNG."""
    value = rng.random()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PrimitiveError(
            f"Roll table {source_id} weighted RNG produced non-numeric value: {value}"
        )
    if not 0 <= value < 1:
        raise PrimitiveError(
            f"Roll table {source_id} weighted RNG value must be >= 0 and < 1: {value}"
        )
    return float(value)


def _row_outcome_count(row: RollTableRow, distribution: dict[int, int]) -> int:
    start, end = parse_range(row.range)
    return sum(count for value, count in distribution.items() if start <= value <= end)


def _selection_from_row(
    source_id: str,
    anchor: str | None,
    row: RollTableRow,
    debug: dict[str, pydantic.JsonValue],
) -> SelectionResult:
    return SelectionResult(
        source_type="roll_table",
        source_id=source_id,
        anchor=anchor,
        result_id=row.id,
        label=row.label,
        text=row.text,
        effects=copy.deepcopy(row.effects),
        variables=copy.deepcopy(row.variables),
        debug=debug,
    )


def _validate_debug_payload(
    debug: dict[str, pydantic.JsonValue],
) -> dict[str, pydantic.JsonValue]:
    """Validate a debug payload through its mode-specific schema."""
    if debug.get("mode") == "dice":
        return RollTableDiceDebug.model_validate(debug).model_dump(
            mode="json", exclude_none=True
        )
    if debug.get("mode") == "weighted":
        return RollTableWeightedDebug.model_validate(debug).model_dump(
            mode="json", exclude_none=True
        )
    raise PrimitiveError(f"Unknown roll table debug mode: {debug.get('mode')}")


def _lookup_modifier(store: PrimitiveStore, modifier_ref: str) -> RollModifier:
    if "/" in modifier_ref:
        ref = PrimitiveRef.parse(modifier_ref)
        payload = store.get_primitive(ref)
        if payload is None:
            raise PrimitiveError(f"Roll modifier primitive not found: {ref.key()}")
        return RollModifier.model_validate(primitive_payload_value(payload))
    payload = store.get_definition("modifiers", modifier_ref)
    if payload is None:
        raise PrimitiveError(f"Roll modifier definition not found: {modifier_ref}")
    return RollModifier.model_validate(payload)


def _anchor_key(anchor: AnchorRef | str | None) -> str | None:
    if anchor is None:
        return None
    return AnchorRef.model_validate(anchor).key()


def _validate_context(
    context: dict[str, pydantic.JsonValue] | None,
) -> dict[str, pydantic.JsonValue]:
    """Validate roll context as a JSON-compatible dictionary."""
    if context is None:
        return {}
    return pydantic.TypeAdapter(dict[str, pydantic.JsonValue]).validate_python(context)
