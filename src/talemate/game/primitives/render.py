"""Prompt-safe rendering helpers for Game Primitives payloads."""

from __future__ import annotations

from typing import Any, Literal

RENDER_POLICIES = ("hidden", "prompt", "summary", "memory")
RenderPolicy = Literal[*RENDER_POLICIES]
"""Visibility policy controlling how primitive values appear in generated text.

Policy values:
    hidden: Suppresses the attribute value from all rendered output.
    prompt: Renders the attribute value directly for prompt-visible output.
    summary: Renders qualitative summary text instead of raw mechanical numbers.
    memory: Renders the attribute value only for memory-visible output.
"""

Audience = Literal["prompt", "memory"]
"""Target output channel used when deciding whether a primitive value is visible.

Audience values:
    prompt: Text being assembled for language-model prompt input.
    memory: Text being assembled for memory storage or retrieval context.
"""


def render_policy_visible(policy: RenderPolicy, audience: Audience) -> bool:
    """Return whether a render policy is visible to a render audience.

    Args:
        policy: Visibility policy attached to a primitive value.
        audience: Render audience requesting output.

    Returns:
        ``True`` when ``policy`` allows rendered text for ``audience``.

    Raises:
        ValueError: If ``policy`` or ``audience`` is unsupported.
    """
    if audience not in {"prompt", "memory"}:
        raise ValueError(f"Unsupported render audience: {audience}")
    if policy == "hidden":
        return False
    if policy == "memory":
        return audience == "memory"
    if policy in {"prompt", "summary"}:
        return audience == "prompt"
    raise ValueError(f"Unsupported render policy: {policy}")


def render_attribute_value(label: str, value: Any, render_policy: RenderPolicy) -> str:
    """Render one primitive attribute value according to a visibility policy.

    Args:
        label: Human-readable attribute label used in rendered prose.
        value: Resolved attribute value to render.
        render_policy: Visibility policy: ``hidden``, ``prompt``, ``summary``, or
            ``memory``.

    Returns:
        Prompt-safe text for visible policies, or an empty string for ``hidden``.

    Raises:
        ValueError: If ``render_policy`` is unsupported, or if ``render_policy`` is
            visible and ``value`` is ``None``.
    """
    if render_policy == "hidden":
        return ""
    if render_policy in {"prompt", "memory"}:
        return _render_direct(label, value)
    if render_policy == "summary":
        return _render_summary(label, value)
    raise ValueError(f"Unsupported render policy: {render_policy}")


def _render_direct(label: str, value: Any) -> str:
    """Render a value directly for prompt-visible or memory-visible output."""
    if value is None:
        raise ValueError("Visible primitive attribute value cannot be None")
    if isinstance(value, str):
        return f"{label}: {value}" if label else value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{label}: {value}" if label else str(value)
    return f"{label} is available." if label else "Attribute value is available."


def _render_summary(label: str, value: Any) -> str:
    """Render a value without dumping raw mechanical numbers into prompts."""
    if value is None:
        raise ValueError("Visible primitive attribute summary value cannot be None")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > 0:
            return f"{label} is elevated."
        if value < 0:
            return f"{label} is reduced."
        return f"{label} is steady."
    if isinstance(value, str):
        return f"{label}: {value}" if label else value
    return f"{label} has a resolved state." if label else "Attribute state is resolved."
