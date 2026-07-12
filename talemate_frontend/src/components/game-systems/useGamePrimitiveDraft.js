import { authoritativeGamePrimitivesResponseSchema, deletionPreviewResponseSchema } from '../gamePrimitives/gamePrimitiveResponseContracts.js';
import { useGamePrimitiveDraftLifecycle } from '../gamePrimitives/useGamePrimitiveDraftLifecycle.js';

/** Revision-guarded draft/runtime operations used by anchor instance editors. */
export function useGamePrimitiveDraft(options = {}) {
    const lifecycle = useGamePrimitiveDraftLifecycle(options);
    const { draft, mutate } = lifecycle;
    const draftData = async (promise) => (await promise).data;
    const authoritativeData = async (promise) => (await promise).data;

    const actions = {
        upsertAnchor: (anchor, value) => draftData(mutate('upsert_game_primitive_anchor', { draft_id: draft.value.id, anchor, value })),
        upsertPrimitive: (refValue, primitive) => draftData(mutate('upsert_game_primitive', { draft_id: draft.value.id, ref: refValue, primitive })),
        adjustPrimitive: (refValue, delta) => authoritativeData(mutate('adjust_game_primitive', { ref: refValue, delta }, 'game_primitives', authoritativeGamePrimitivesResponseSchema)),
        validate: lifecycle.validateDraft,
        commit: lifecycle.commitDraft,
    };

    const preview = (action, fields) => mutate(action, fields, 'game_primitive_deletion_preview', deletionPreviewResponseSchema);
    const previewDeletePrimitive = (refValue) => preview('preview_delete_game_primitive', { ref: refValue });
    const previewDeleteAnchor = (anchor) => preview('preview_delete_game_primitive_anchor', { anchor });
    const deletePrimitive = (refValue) => draftData(mutate('delete_game_primitive', { draft_id: draft.value.id, ref: refValue }));
    const deleteAnchor = (anchor) => draftData(mutate('delete_game_primitive_anchor', { draft_id: draft.value.id, anchor }));

    return {
        ...lifecycle, ...actions, previewDeletePrimitive, previewDeleteAnchor, deletePrimitive, deleteAnchor,
    };
}
