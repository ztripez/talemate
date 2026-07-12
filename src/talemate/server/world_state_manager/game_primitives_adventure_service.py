"""Focused AdventureEngine service for Game Primitives websocket actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

from talemate.game.primitives.adventure import (
    AdventureEngine,
    AdventureState,
    TransitionResult,
)
from talemate.game.primitives.exceptions import PrimitiveError

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


class AdventureActivationResult(pydantic.BaseModel):
    """Structured outcome of one AdventureEngine activation attempt."""

    model_config = pydantic.ConfigDict(extra="forbid")

    ok: bool
    adventure_id: str
    state: AdventureState | None = None
    error: str | None = None


class GamePrimitivesAdventureService:
    """Expose runtime adventure operations exclusively through AdventureEngine."""

    def __init__(self, engine: AdventureEngine | None = None) -> None:
        self.engine = engine or AdventureEngine()

    def activate(self, scene: "Scene", adventure_id: str) -> AdventureActivationResult:
        """Activate one adventure and model expected domain rejection."""
        try:
            state = self.engine.activate(scene, adventure_id)
        except PrimitiveError as exc:
            return AdventureActivationResult(
                ok=False, adventure_id=adventure_id, error=str(exc)
            )
        return AdventureActivationResult(
            ok=True, adventure_id=adventure_id, state=state
        )

    def take_transition(self, scene: "Scene", transition_id: str) -> TransitionResult:
        """Take one transition through the engine and preserve its rich result."""
        return self.engine.take_transition(scene, transition_id)


__all__ = ["AdventureActivationResult", "GamePrimitivesAdventureService"]
