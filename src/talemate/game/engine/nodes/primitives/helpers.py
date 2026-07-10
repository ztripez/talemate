"""Shared helpers for Game Primitives graph node wrappers."""

from talemate.game.engine.nodes.core import UNRESOLVED, Node


def optional_input(node: Node, name: str, default):
    """Return an optional node input while preserving explicit ``None``.

    Args:
        node: Graph node whose input socket should be read.
        name: Input socket name to read.
        default: Value returned only when the socket is unresolved.

    Returns:
        The resolved input value, including explicit ``None``, or ``default`` when
        the input socket has no value.
    """
    value = node.get_input_value(name)
    return default if value is UNRESOLVED else value
