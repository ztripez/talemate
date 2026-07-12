"""Anchor and primitive instance action response contracts."""

from typing import Literal

import pydantic

from talemate.game.primitives.draft_schema import DraftValidation, PrimitiveDraft

from .game_primitives_transport import GamePrimitivesTransportModel


class GamePrimitiveCandidateCounts(GamePrimitivesTransportModel):
    """Count definitions, anchors, and instances in a deletion candidate.

    Every count is a nonnegative strict integer.
    """

    definitions: pydantic.StrictInt = pydantic.Field(ge=0)
    anchors: pydantic.StrictInt = pydantic.Field(ge=0)
    primitives: pydantic.StrictInt = pydantic.Field(ge=0)


class GamePrimitiveCandidateSummary(GamePrimitivesTransportModel):
    """Compare root counts before and after a prospective deletion."""

    before: GamePrimitiveCandidateCounts
    after: GamePrimitiveCandidateCounts
    candidate_revision: str = pydantic.Field(min_length=1)


class GamePrimitiveDeletionTarget(GamePrimitivesTransportModel):
    """Identify the canonical anchor or primitive targeted for deletion."""

    kind: Literal["anchor", "primitive"]
    ref: str = pydantic.Field(min_length=1)


class GamePrimitiveDeletionPreviewResponse(GamePrimitivesTransportModel):
    """Return a validated, non-persisted deletion candidate and its impact."""

    type: Literal["world_state_manager"] = "world_state_manager"
    action: Literal["game_primitive_deletion_preview"] = (
        "game_primitive_deletion_preview"
    )
    request_id: str
    revision: str
    target: GamePrimitiveDeletionTarget
    draft: PrimitiveDraft
    validation: DraftValidation
    candidate: GamePrimitiveCandidateSummary
