"""Draft lifecycle and definition action handlers."""

from talemate.game.primitives.draft_schema import PrimitiveDraft

from .game_primitives_draft_definition_requests import (
    CommitGamePrimitiveDraftPayload,
    CreateGamePrimitiveDraftPayload,
    DeleteGamePrimitiveDefinitionPayload,
    DeleteGamePrimitiveDraftPayload,
    GetGamePrimitiveDraftPayload,
    ListGamePrimitiveDraftsPayload,
    UpsertGamePrimitiveDefinitionPayload,
    ValidateGamePrimitiveDraftPayload,
)


class GamePrimitivesDraftDefinitionHandlers:
    """Handle draft lifecycle and reusable-definition websocket actions."""

    async def handle_list_game_primitive_drafts(
        self, payload: ListGamePrimitiveDraftsPayload
    ) -> None:
        """Queue all persisted drafts with their current revision.

        Args:
            payload: Validated request carrying the response correlation ID.

        Notes:
            Draft reads do not mutate scene state. Read and websocket transport
            failures propagate without queuing a successful response.

        """
        self._queue_drafts(
            self._primitive_authoring().list_drafts(self.scene), payload.request_id
        )

    async def handle_get_game_primitive_draft(
        self, payload: GetGamePrimitiveDraftPayload
    ) -> None:
        """Queue a selected persisted draft with the current revision.

        Args:
            payload: Validated draft ID and response correlation ID.

        Notes:
            Draft reads do not mutate scene state. Lookup and websocket transport
            failures propagate without queuing a successful response.

        """
        self._queue_draft(
            self._primitive_authoring().get_draft(self.scene, payload.draft_id),
            payload.request_id,
        )

    async def handle_create_game_primitive_draft(
        self, payload: CreateGamePrimitiveDraftPayload
    ) -> None:
        """Create, persist, and return one revision-guarded draft.

        ``payload`` supplies the draft ID, expected scene revision, action, and
        response correlation ID. A matching revision creates and persists the draft,
        then queues it with the authoritative revision. Validation or pre-commit
        failure restores the primitive root; post-commit transport failure leaves the
        commit intact and attempts to report an indeterminate result.
        """
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.create_draft(
                self.scene,
                payload.draft_id,
                created_by="ui",
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_delete_game_primitive_draft(
        self, payload: DeleteGamePrimitiveDraftPayload
    ) -> None:
        """Delete a draft and return the remaining persisted drafts.

        ``payload`` identifies the draft, expected scene revision, action, and
        response correlation ID. A matching revision persists the deletion and
        queues the remaining drafts at the authoritative revision. Rejection or
        pre-commit failure restores the primitive root; post-commit transport failure
        leaves the deletion intact and attempts to report an indeterminate result.
        """
        service = self._primitive_authoring()

        def mutate() -> list[PrimitiveDraft]:
            service.delete_draft(
                self.scene,
                payload.draft_id,
                expected_revision=payload.expected_revision,
            )
            return service.list_drafts(self.scene)

        await self._run_primitive_mutation(
            payload.request_id, payload.action, mutate, self._queue_drafts
        )

    async def handle_upsert_game_primitive_definition(
        self, payload: UpsertGamePrimitiveDefinitionPayload
    ) -> None:
        """Stage and return a typed definition replacement.

        ``payload`` identifies the draft and typed definition and carries the
        expected scene revision, action, and correlation ID. A matching revision
        persists the replacement and queues the updated draft. Rejection or
        pre-commit failure restores the primitive root; post-commit transport failure
        preserves the commit and attempts to report an indeterminate result.
        """
        service = self._primitive_authoring()
        change = payload.definition
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.upsert_definition(
                self.scene,
                payload.draft_id,
                change.kind,
                change.id,
                change.value.model_dump(mode="json"),
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_delete_game_primitive_definition(
        self, payload: DeleteGamePrimitiveDefinitionPayload
    ) -> None:
        """Stage and return a reusable-definition deletion.

        ``payload`` identifies the draft, definition kind and ID, expected scene
        revision, action, and correlation ID. A matching revision persists the staged
        deletion and queues the updated draft. Rejection or pre-commit failure
        restores the primitive root; post-commit transport failure preserves the
        commit and attempts to report an indeterminate result.
        """
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.delete_definition(
                self.scene,
                payload.draft_id,
                payload.kind,
                payload.id,
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_validate_game_primitive_draft(
        self, payload: ValidateGamePrimitiveDraftPayload
    ) -> None:
        """Validate a draft, persist its status, and return the draft.

        ``payload`` identifies the draft and carries the expected scene revision,
        action, and correlation ID. A matching revision persists the validation
        result and queues the updated draft. Rejection or pre-commit failure restores
        the primitive root; post-commit transport failure preserves the result and
        attempts to report an indeterminate outcome.
        """
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.validate_draft(
                self.scene,
                payload.draft_id,
                expected_revision=payload.expected_revision,
            ),
            self._queue_draft,
        )

    async def handle_commit_game_primitive_draft(
        self, payload: CommitGamePrimitiveDraftPayload
    ) -> None:
        """Commit a validated draft and return the authoritative snapshot.

        ``payload`` identifies the validated draft and carries the expected scene
        revision, action, and correlation ID. A matching revision installs and
        persists its changes, then queues the authoritative snapshot. Rejection or
        pre-commit failure restores the primitive root; post-commit transport failure
        preserves the commit and attempts to report an indeterminate result.
        """
        service = self._primitive_authoring()
        await self._run_primitive_mutation(
            payload.request_id,
            payload.action,
            lambda: service.commit_draft(
                self.scene,
                payload.draft_id,
                expected_revision=payload.expected_revision,
            ),
            self._queue_snapshot,
        )
