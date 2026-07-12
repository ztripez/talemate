"""Relationship authoring action handlers."""

from talemate.game.primitives.authoring.relationships import RelationshipAuthoringService

from .game_primitives_relationship_requests import (
    AuthorGamePrimitiveRelationshipPayload,
)


class GamePrimitivesRelationshipHandlers:
    """Handle revision-guarded directional relationship authoring."""

    async def handle_author_game_primitive_relationship(
        self, payload: AuthorGamePrimitiveRelationshipPayload
    ) -> None:
        """Apply a relationship change and queue the resulting snapshot.

        ``payload`` identifies the directional source, target, and change and carries
        the expected scene revision, action, and correlation ID. A matching revision
        persists the relationship and queues the authoritative snapshot. Rejection or
        pre-commit failure restores the primitive root; post-commit transport failure
        preserves the change and attempts to report an indeterminate result.
        """
        service = RelationshipAuthoringService()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.author(
                self.scene,
                payload.source,
                payload.target,
                payload.change,
                expected_revision=payload.expected_revision,
            ),
            self._queue_snapshot,
        )
