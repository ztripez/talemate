import { computed, ref } from 'vue';

import { draftResponseSchema, draftsResponseSchema } from './gamePrimitiveDraftContracts.js';
import { authoritativeGamePrimitivesResponseSchema } from './gamePrimitiveResponseContracts.js';
import { useCorrelatedWebsocketRequest } from './useCorrelatedWebsocketRequest.js';

/** Manages strict, correlated, revision-guarded Game Primitive draft requests. */
export function useGamePrimitiveDraftLifecycle(options = {}) {
    const transport = useCorrelatedWebsocketRequest(options);
    const drafts = ref([]);
    const draft = ref(options.initialDraft ?? options.draft ?? null);
    const revision = ref(options.initialRevision ?? options.revision ?? '');
    const selectedDraftId = ref(options.initialDraftId ?? draft.value?.id ?? '');
    const orderedDrafts = computed(() => [...drafts.value].sort((a, b) => a.id.localeCompare(b.id)));

    function adoptDraft(response) {
        revision.value = response.revision;
        draft.value = response.data;
        selectedDraftId.value = response.data.id;
        const index = drafts.value.findIndex((item) => item.id === response.data.id);
        drafts.value = index === -1
            ? [...drafts.value, response.data]
            : drafts.value.map((item, itemIndex) => itemIndex === index ? response.data : item);
        options.onDraftAdopt?.(response.data, response.revision);
    }

    function adoptResponse(responseAction, response) {
        if (responseAction === 'game_primitive_draft') {
            adoptDraft(response);
        } else if (responseAction === 'game_primitive_drafts') {
            revision.value = response.revision;
            drafts.value = response.data;
            if (selectedDraftId.value && !response.data.some((item) => item.id === selectedDraftId.value)) {
                selectedDraftId.value = '';
                draft.value = null;
            }
        } else if (responseAction === 'game_primitives') {
            revision.value = response.data.revision;
        } else {
            revision.value = response.revision;
        }
    }

    async function send(action, fields = {}, responseAction = 'game_primitive_draft', schema = draftResponseSchema) {
        const response = await transport.request({
            action, responseAction, schema, fields,
            onResponse: (value) => adoptResponse(responseAction, value),
        });
        return response;
    }

    function expectedRevision() {
        if (!revision.value) throw new Error('Refresh drafts before making changes');
        return revision.value;
    }

    async function selectDraft(draftId) {
        selectedDraftId.value = draftId;
        if (!draftId) {
            draft.value = null;
            return null;
        }
        return (await send('get_game_primitive_draft', { draft_id: draftId })).data;
    }

    const listDrafts = async () => (await send('list_game_primitive_drafts', {}, 'game_primitive_drafts', draftsResponseSchema)).data;
    const refresh = () => selectedDraftId.value ? selectDraft(selectedDraftId.value) : listDrafts();
    const revisionFields = () => ({ expected_revision: expectedRevision() });
    const mutate = (action, fields = {}, responseAction = 'game_primitive_draft', schema = draftResponseSchema) =>
        send(action, { ...fields, ...revisionFields() }, responseAction, schema);
    async function commitDraft() {
        const response = await mutate('commit_game_primitive_draft', { draft_id: selectedDraftId.value }, 'game_primitives', authoritativeGamePrimitivesResponseSchema);
        revision.value = response.data.revision;
        draft.value = null;
        selectedDraftId.value = '';
        return response.data;
    }

    return {
        drafts: orderedDrafts, draft, revision, selectedDraftId,
        busy: transport.busy, error: transport.error, stale: transport.stale, indeterminate: transport.indeterminate,
        listDrafts, selectDraft, refresh,
        createDraft: async (draftId = null) => (await mutate('create_game_primitive_draft', { draft_id: draftId || null })).data,
        deleteDraft: async () => (await mutate('delete_game_primitive_draft', { draft_id: selectedDraftId.value })).data,
        upsertDefinition: async (kind, value) => (await mutate('upsert_game_primitive_definition', { draft_id: selectedDraftId.value, definition: { kind, id: value.id, value } })).data,
        deleteDefinition: async (kind, id) => (await mutate('delete_game_primitive_definition', { draft_id: selectedDraftId.value, kind, id })).data,
        validateDraft: async () => (await mutate('validate_game_primitive_draft', { draft_id: selectedDraftId.value })).data,
        commitDraft, mutate,
    };
}
