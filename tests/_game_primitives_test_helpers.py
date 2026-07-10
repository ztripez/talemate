"""Shared setup helpers for Game Primitives tests."""

from talemate.game.primitives.attributes import AttributeResolver
from talemate.tale_mate import Scene


def seed_prompt_attribute(scene: Scene, ref: str, value: str = "Rainy") -> None:
    """Store one literal prompt-visible attribute for a primitive test."""
    AttributeResolver().set(
        scene,
        ref,
        {"source": "literal", "render_policy": "prompt", "value": value},
    )
