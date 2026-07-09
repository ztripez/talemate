"""Game-state condition models and comparison helpers."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

import pydantic

from talemate.util.path import get_path_parent, split_state_path

__all__ = [
    "Condition",
    "ConditionGroup",
    "CONDITION_OPERATORS",
    "ConditionOperator",
    "compare_condition_values",
    "condition_groups_match",
    "read_condition_path",
]

#: Comparison operators accepted by game-state and primitive-aware conditions.
ConditionOperator: TypeAlias = Literal[
    "==",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "in",
    "not_in",
    "is_true",
    "is_false",
    "is_null",
    "is not null",
    "is_not_null",
]
CONDITION_OPERATORS = frozenset(ConditionOperator.__args__)


def try_parse_condition_number(value: Any) -> float | int | None:
    """Parse an integer or float condition operand while excluding booleans."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
            return float(text)
        except Exception:
            return None
    return None


def compare_condition_values(actual: Any, operator: str, expected: Any = None) -> bool:
    """Compare two values using Talemate condition operator semantics.

    Invalid membership containers and unsupported operators raise an exception;
    documented non-matches such as missing binary operands return ``False``.
    """
    if operator not in CONDITION_OPERATORS:
        raise ValueError(f"Unsupported condition operator: {operator}")
    if operator == "is_true":
        return actual is True
    if operator == "is_false":
        return actual is False
    if operator == "is_null":
        return actual is None
    if operator in ("is not null", "is_not_null"):
        return actual is not None
    if expected is None:
        return False

    numeric_only = operator in (">", "<", ">=", "<=")
    mixed = operator in ("==", "!=", "in", "not_in")
    if numeric_only:
        left = try_parse_condition_number(actual)
        right = try_parse_condition_number(expected)
        if left is None or right is None:
            return False
    elif mixed:
        actual_number = try_parse_condition_number(actual)
        expected_number = try_parse_condition_number(expected)
        if actual_number is not None and expected_number is not None:
            left, right = actual_number, expected_number
        else:
            left = actual
            right = expected_number if expected_number is not None else str(expected)
    else:
        left, right = actual, expected

    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">":
        return left > right
    if operator == "<":
        return left < right
    if operator == ">=":
        return left >= right
    if operator == "<=":
        return left <= right
    if operator == "in":
        return right in left
    if operator == "not_in":
        return right not in left
    raise ValueError(f"Unsupported condition operator: {operator}")


def read_condition_path(game_state: Any, path: str) -> tuple[bool, Any]:
    """Read a slash-delimited condition path from a game-state container."""
    parent, leaf_key = get_path_parent(game_state, split_state_path(path), create=False)
    if parent is None:
        return False, None
    if hasattr(parent, "has_var") and hasattr(parent, "get_var"):
        if not parent.has_var(leaf_key):
            return False, None
        return True, parent.get_var(leaf_key)
    if hasattr(parent, "get"):
        value = parent.get(leaf_key)
        return value is not None or leaf_key in parent, value
    try:
        return True, parent[leaf_key]
    except (KeyError, IndexError):
        return False, None


class Condition(pydantic.BaseModel):
    """Predicate that compares one game-state path against an expected value."""

    path: str
    value: Any | None = None
    operator: ConditionOperator

    def evaluate(self, game_state: Any) -> bool:
        """
        Evaluate this condition against a game_state-like container.

        Path semantics follow existing state path conventions:
        - Slash-delimited (e.g. "foo/bar")
        - Root is the provided game_state (typically `scene.game_state`)

        Missing path always evaluates to False.
        """

        found, state_value = read_condition_path(game_state, self.path)
        if not found:
            return False
        return compare_condition_values(state_value, self.operator, self.value)


class ConditionGroup(pydantic.BaseModel):
    """Boolean group of game-state conditions."""

    conditions: list[Condition] = pydantic.Field(default_factory=list)
    operator: Literal["and", "or"] = "and"

    def evaluate(self, game_state: Any) -> bool:
        """
        Evaluate this group against the provided game_state.

        Empty groups evaluate to False (so a newly-added group with no conditions
        does not accidentally match).
        """

        if not self.conditions:
            return False

        if self.operator == "and":
            return all(cond.evaluate(game_state) for cond in self.conditions)

        # operator == "or"
        return any(cond.evaluate(game_state) for cond in self.conditions)


def condition_groups_match(condition_groups: Any, game_state: Any) -> bool:
    """
    Evaluate a list of ConditionGroup-like objects/dicts against the provided game_state.

    Expected shape (wire format):
      [
        {"operator": "and"|"or", "conditions": [{"path": "...", "operator": "...", "value": ...}, ...]},
        ...
      ]

    Notes:
    - If the list is missing or empty, returns False.
    - Malformed non-list inputs and invalid group items raise errors.
    - Groups combine with OR (any group matching is sufficient).
    """

    if condition_groups is None:
        return False

    if not isinstance(condition_groups, list):
        raise TypeError("condition_groups must be a list")

    if not condition_groups:
        return False

    groups: list[ConditionGroup] = []
    for group in condition_groups:
        if isinstance(group, ConditionGroup):
            groups.append(group)
        elif isinstance(group, dict):
            groups.append(ConditionGroup.model_validate(group))
        else:
            raise TypeError(
                "condition groups must contain dictionaries or ConditionGroup models"
            )

    return any(group.evaluate(game_state) for group in groups)
