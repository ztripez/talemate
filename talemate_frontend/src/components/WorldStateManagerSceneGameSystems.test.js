import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';

import WorldStateManagerScene from './WorldStateManagerScene.vue';
import WorldStateManagerSceneGameSystems from './WorldStateManagerSceneGameSystems.vue';
import GamePrimitiveAnchorInstanceEditorPanel from './game-systems/GamePrimitiveAnchorInstanceEditorPanel.vue';
import {
    createVuetifyStubs,
    createWebsocketHarness,
} from '../test/websocketHarness.js';
import { editorMetadata } from '../test/gamePrimitiveFixtures.js';

const vuetifyStubs = createVuetifyStubs([
    'VAlert', 'VBtn', 'VCard', 'VCardActions', 'VCardText', 'VCardTitle', 'VChip', 'VCol', 'VDivider',
    'VIcon', 'VList', 'VListItem', 'VNumberInput', 'VProgressLinear', 'VRow', 'VSelect', 'VSpacer',
    'VTab', 'VTabs', 'VTextField', 'VWindow', 'VWindowItem',
]);

function emptySnapshot(overrides = {}) {
    const snapshot = {
        initialized: true,
        version: 1,
        revision: 'revision-1',
        editor_metadata: editorMetadata,
        definition_counts: {},
        definitions: [],
        anchor_count: 0,
        primitive_count: 0,
        anchors: [],
        active_characters: [],
        relationships: [],
        drafts: [],
        current_adventure: null,
        recent_ledger: [],
        ...overrides,
    };
    snapshot.anchors = snapshot.anchors.map((anchor) => ({ meta: {}, primitives: {}, ...anchor }));
    return snapshot;
}

function pendingRequestId(websocket) {
    return websocket.outgoing.at(-1).request_id;
}

function dispatchSnapshot(websocket, data = emptySnapshot(), requestId = pendingRequestId(websocket)) {
    websocket.dispatch({
        type: 'world_state_manager',
        action: 'game_primitives',
        request_id: requestId,
        data,
    });
}

function draft(overrides = {}) {
    const targets = { definitions: [], anchors: [], primitives: [] };
    return {
        id: 'working', status: 'draft', created_by: 'ui',
        definitions: { decks: {}, roll_tables: {}, meters: {}, clocks: {}, relationship_models: {}, modifiers: {}, attribute_sources: {}, adventures: {} },
        anchors: {}, replacements: structuredClone(targets), deletions: structuredClone(targets),
        validation: { ok: false, errors: [], warnings: [] }, ...overrides,
    };
}

function dispatchDraft(websocket, data, revision, requestId = pendingRequestId(websocket)) {
    websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: requestId, data, revision });
}

function relationship(value = 1) {
    return {
        anchor: 'relationship:Alice->Bob', source: 'Alice', target: 'Bob', summary: 'Alice trusts Bob.',
        dimensions: [{ id: 'trust', label: 'Trust', min: -5, max: 5, value, render_policy: 'summary' }],
    };
}

function adventureDefinition() {
    return {
        id: 'journey', title: 'Journey', description: null, start_scene: 'start',
        scenes: { start: { id: 'start', title: 'Start', description: null, location: null, intro: null, goals: [], local_anchors: [], entry_effects: [], exit_effects: [], render_policy: 'prompt' } },
        transitions: {},
    };
}

function mountPanel(props = { isVisible: true }) {
    const websocket = createWebsocketHarness();
    const wrapper = mount(WorldStateManagerSceneGameSystems, {
        props,
        global: {
            provide: websocket.provide,
            stubs: vuetifyStubs,
        },
    });
    return { websocket, wrapper };
}

describe('WorldStateManagerSceneGameSystems', () => {
    it('blocks mutations when selected anchors or primitives disappear', async () => {
        const websocket = createWebsocketHarness();
        const anchor = { ref: 'scene:main', tags: [], meta: {}, primitives: { meters: { focus: { id: 'focus' } } } };
        const wrapper = mount(GamePrimitiveAnchorInstanceEditorPanel, {
            props: { revision: 'revision-1', draft: draft(), anchors: [anchor], definitions: [], editorMetadata },
            global: { provide: websocket.provide, stubs: { ...vuetifyStubs, GamePrimitiveAnchorMetadataEditor: true, GamePrimitiveMeterClockEditor: true } },
        });
        wrapper.vm.selectedAnchorRef = 'scene:main';
        wrapper.vm.selectedPrimitiveRef = 'scene:main/meters/focus';
        await wrapper.setProps({ anchors: [] });
        expect(wrapper.get('[data-testid="selection-error"]').text()).toContain('Selected anchor no longer exists');
        await expect(wrapper.vm.adjustPrimitive(1)).rejects.toThrow('Selected anchor no longer exists');
        expect(websocket.outgoing).toHaveLength(0);

        wrapper.vm.selectedAnchorRef = 'malformed';
        await nextTick();
        expect(wrapper.get('[data-testid="selection-error"]').text()).toContain('Invalid selected anchor');
        await expect(wrapper.vm.deleteAnchor('malformed')).rejects.toThrow('Invalid selected anchor');
        expect(websocket.outgoing).toHaveLength(0);
        wrapper.unmount();
    });
    afterEach(() => vi.useRealTimers());

    it('requests the read-only snapshot when activated and on refresh', async () => {
        const { websocket, wrapper } = mountPanel({ isVisible: false });
        expect(websocket.outgoing).toEqual([]);

        await wrapper.setProps({ isVisible: true });
        expect(websocket.outgoing[0]).toMatchObject({ type: 'world_state_manager', action: 'get_game_primitives' });
        expect(websocket.outgoing[0].request_id).toEqual(expect.any(String));
        expect(wrapper.vm.busy).toBe(true);

        dispatchSnapshot(websocket);
        await nextTick();
        await wrapper.get('test-vbtn').trigger('click');
        expect(websocket.outgoing).toHaveLength(2);
        expect(new Set(websocket.outgoing.map((message) => message.request_id)).size).toBe(2);
        dispatchSnapshot(websocket);
        await nextTick();
        wrapper.unmount();
    });

    it('settles only the matching pending request and ignores stale responses', async () => {
        const { websocket, wrapper } = mountPanel();
        const staleRequestId = pendingRequestId(websocket);
        wrapper.vm.refresh();
        const currentRequestId = pendingRequestId(websocket);

        dispatchSnapshot(websocket, emptySnapshot({ revision: 'stale' }), staleRequestId);
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives_failed', request_id: staleRequestId, error: 'stale failure',
        });
        await nextTick();
        expect(wrapper.vm.busy).toBe(true);
        expect(wrapper.vm.snapshot).toBeNull();
        expect(wrapper.vm.error).toBeNull();

        dispatchSnapshot(websocket, emptySnapshot({ revision: 'current' }), currentRequestId);
        await nextTick();
        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.vm.snapshot.revision).toBe('current');
        wrapper.unmount();
    });

    it('renders deterministic catalogs and canonical anchor and primitive refs', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({
                definition_counts: { meters: 1, clocks: 1 },
                definitions: [
                    { kind: 'meters', id: 'resolve', title: 'Resolve', details: { max: 10 } },
                    { kind: 'clocks', id: 'alarm', title: 'Alarm', details: { segments: 4 } },
                ],
                anchor_count: 2,
                primitive_count: 2,
                anchors: [
                    { ref: 'scene:main', kind: 'scene', id: 'main', tags: [], primitive_counts: { meters: 1 }, primitive_count: 1, primitive_refs: ['scene:main/meters/resolve'] },
                    { ref: 'character:Ada', kind: 'character', id: 'Ada', tags: ['hero'], primitive_counts: { clocks: 1 }, primitive_count: 1, primitive_refs: ['character:Ada/clocks/alarm'] },
                ],
                recent_ledger: [{
                    id: 'ledger-1', op: 'primitive.set', ref: 'character:Ada/clocks/alarm',
                    anchor: 'character:Ada', input: { value: 1 }, output: {}, message: null,
                }],
            }));
        await nextTick();

        expect(wrapper.vm.busy).toBe(false);
        wrapper.vm.section = 'definitions';
        await nextTick();
        expect(wrapper.findComponent({ name: 'GameSystemsDefinitionsSection' }).vm.definitions.map((item) => `${item.kind}/${item.id}`)).toEqual(['clocks/alarm', 'meters/resolve']);
        wrapper.vm.section = 'anchors';
        await nextTick();
        expect(wrapper.findComponent({ name: 'GameSystemsAnchorsSection' }).vm.anchors.map((item) => item.ref)).toEqual(['character:Ada', 'scene:main']);
        expect(wrapper.text()).toContain('character:Ada/clocks/alarm');
        expect(wrapper.text()).toContain('character:Ada');
        expect(wrapper.text()).toContain('clocks/alarm');
        wrapper.unmount();
    });

    it('distinguishes uninitialized and initialized-empty snapshots', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({ initialized: false, version: null }));
        await nextTick();
        expect(wrapper.get('[data-testid="uninitialized-state"]').text()).toContain('did not initialize or modify');
        expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false);

        wrapper.vm.refresh();
        dispatchSnapshot(websocket);
        await nextTick();
        expect(wrapper.get('[data-testid="empty-state"]').text()).toContain('initialized');
        wrapper.unmount();
    });

    it('rejects malformed nested snapshot state and always clears loading', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({
            anchors: [{
                ref: 'scene:main', kind: 'scene', id: 'main', tags: [], primitive_counts: {},
                primitive_count: 0, primitive_refs: [], unexpected: true,
            }],
        }));
        await nextTick();

        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.get('[data-testid="game-systems-error"]').text()).toContain('Malformed get_game_primitives response');
        expect(wrapper.vm.snapshot).toBeNull();
        wrapper.unmount();
    });

    it('surfaces matching action-specific failures and clears loading', async () => {
        const { websocket, wrapper } = mountPanel();
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives_failed', request_id: pendingRequestId(websocket),
            request_action: 'get_game_primitives', error: { message: 'Invalid primitive state' },
        });
        await nextTick();

        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.text()).toContain('Invalid primitive state');
        wrapper.unmount();
    });

    it('ignores unrelated errors from the same router', async () => {
        const { websocket, wrapper } = mountPanel();
        websocket.dispatch({ type: 'world_state_manager', action: 'operation_done', error: { message: 'another action failed' } });
        websocket.dispatch({ type: 'error', plugin: 'world_state_manager', error: 'router error' });
        await nextTick();

        expect(wrapper.vm.busy).toBe(true);
        expect(wrapper.vm.error).toBeNull();
        dispatchSnapshot(websocket);
        wrapper.unmount();
    });

    it('times out visibly and clears loading', async () => {
        vi.useFakeTimers();
        const { wrapper } = mountPanel();
        await vi.advanceTimersByTimeAsync(10_000);

        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.get('[data-testid="game-systems-error"]').text()).toContain('timed out after 10 seconds');
        wrapper.unmount();
    });

    it.each([
        ['close', 'websocket closed'],
        ['error', 'websocket encountered an error'],
    ])('handles socket %s events and clears loading', async (event, expected) => {
        const { websocket, wrapper } = mountPanel();
        websocket.dispatchSocketEvent(event);
        await nextTick();

        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.text()).toContain(expected);
        wrapper.unmount();
    });

    it('refreshes when a new scene loads and reports send failures', async () => {
        const { websocket, wrapper } = mountPanel();
        websocket.dispatch({ type: 'system', id: 'scene.loaded' });
        expect(websocket.outgoing).toHaveLength(2);
        expect(wrapper.vm.snapshot).toBeNull();

        websocket.websocket.send.mockImplementationOnce(() => { throw new Error('socket closed'); });
        await expect(wrapper.vm.refresh()).rejects.toThrow('socket closed');
        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.vm.error).toBe('socket closed');
        wrapper.unmount();
    });

    it('displays anchor primitive refs without ledger records', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({
            anchor_count: 1,
            primitive_count: 1,
            anchors: [{
                ref: 'character:Ada', kind: 'character', id: 'Ada', tags: [], primitive_counts: { meters: 1 },
                primitive_count: 1, primitive_refs: ['character:Ada/meters/resolve'],
            }],
        }));
        await nextTick();

        wrapper.vm.section = 'anchors';
        await nextTick();
        expect(wrapper.text()).toContain('character:Ada/meters/resolve');
        expect(wrapper.findComponent({ name: 'GameSystemsLedgerSection' }).props('snapshot').recent_ledger).toEqual([]);
        wrapper.unmount();
    });

    it('renders draft findings, active adventure details, and ledger content through section navigation', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({
            drafts: [{
                id: 'review', status: 'draft', created_by: 'ui', definition_counts: { decks: 1 },
                anchor_count: 1, primitive_count: 2,
                validation: { ok: false, errors: ['Missing deck definition'], warnings: ['Prompt source mutates state'] },
            }],
            current_adventure: {
                id: 'journey', title: 'The Long Road', description: 'Reach the observatory.',
                current_story_scene: {
                    id: 'crossroads', title: 'At the Crossroads', description: 'Three paths diverge.',
                    location: 'Old road', intro: 'Choose carefully.', goals: ['Pick a path'],
                    local_anchors: ['location:Crossroads'], render_policy: 'prompt',
                },
                state: { visited: ['crossroads'], completed: [], transition_log: [] },
                transitions: [{ id: 'north', label: 'Go north', to_scene: 'ridge', available: true, reasons: [] }],
            },
            recent_ledger: [{
                id: 'ledger-7', op: 'deck.draw', ref: 'scene:main/decks/weather', anchor: 'scene:main',
                input: { include_tags: ['storm'] }, output: { card_id: 'rain' }, message: 'Drew rain',
            }],
        }));
        await nextTick();

        const tabs = wrapper.findComponent({ name: 'VTabsTestStub' });
        expect(tabs.exists()).toBe(true);
        expect(tabs.attributes()).toHaveProperty('show-arrows');
        await tabs.vm.$emit('update:modelValue', 'drafts');
        await nextTick();
        expect(wrapper.vm.section).toBe('drafts');
        expect(wrapper.text()).toContain('drafts/review');
        expect(wrapper.text()).toContain('Missing deck definition');
        expect(wrapper.text()).toContain('Prompt source mutates state');

        await tabs.vm.$emit('update:modelValue', 'adventure');
        await nextTick();
        expect(wrapper.vm.section).toBe('adventure');
        expect(wrapper.text()).toContain('The Long Road');
        expect(wrapper.text()).toContain('story_scenes/crossroads');
        expect(wrapper.text()).toContain('location:Crossroads');

        await tabs.vm.$emit('update:modelValue', 'ledger');
        await nextTick();
        expect(wrapper.vm.section).toBe('ledger');
        expect(wrapper.text()).toContain('deck.draw');
        expect(wrapper.text()).toContain('scene:main/decks/weather');
        expect(wrapper.text()).toContain('Drew rain');
        expect(wrapper.text()).toContain('card_id');
        expect(wrapper.get('.metric-grid').classes()).toContain('metric-grid');
        wrapper.unmount();
    });

    it.each(['game_primitive_draft', 'game_primitive_drafts'])('does not duplicate the child-owned %s lifecycle', async (action) => {
        const { websocket, wrapper } = mountPanel();
        websocket.dispatch({ type: 'world_state_manager', action, data: {} });
        expect(websocket.outgoing).toHaveLength(1);

        dispatchSnapshot(websocket);
        await nextTick();
        expect(websocket.outgoing).toHaveLength(1);
        expect(wrapper.vm.busy).toBe(false);
        wrapper.unmount();
    });

    it('leaves foreign correlated snapshots to the child lifecycle owner', () => {
        const { websocket, wrapper } = mountPanel();
        const initialRequest = pendingRequestId(websocket);
        dispatchSnapshot(websocket, emptySnapshot(), initialRequest);
        const beforeCommit = websocket.outgoing.length;

        websocket.dispatch({
            type: 'world_state_manager',
            action: 'game_primitives',
            request_id: 'another-editor-commit',
            data: emptySnapshot({ revision: 'committed-revision' }),
        });

        expect(websocket.outgoing).toHaveLength(beforeCommit);
        expect(wrapper.vm.snapshot.revision).toBe('revision-1');
        wrapper.unmount();
    });

    it('exposes definition and anchor editors with canonical refs and advances child draft state', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({
            revision: 'revision-7',
            definitions: [{ kind: 'meters', id: 'focus', title: 'Focus', details: { id: 'focus', min: 0, max: 5, value: 2, label: null, render_policy: 'summary' } }],
            anchors: [{ ref: 'scene:main', kind: 'scene', id: 'main', tags: [], meta: { chapter: 1 }, primitives: { meters: { focus: { id: 'focus', min: 0, max: 5, value: 2, label: null, render_policy: 'summary' } } }, primitive_counts: { meters: 1 }, primitive_count: 1, primitive_refs: ['scene:main/meters/focus'] }],
        }));
        await nextTick();

        wrapper.vm.section = 'definitions';
        await nextTick();
        const definitionEditor = wrapper.findComponent({ name: 'GamePrimitiveDraftEditorPanel' });
        expect(definitionEditor.exists()).toBe(true);
        expect(definitionEditor.props('initialRevision')).toBe('revision-7');
        expect(definitionEditor.props('anchorRefs')).toEqual(['scene:main']);
        expect(definitionEditor.props('primitiveRefs')).toEqual(['scene:main/meters/focus']);
        definitionEditor.vm.$emit('state', { draft: { id: 'edit', anchors: {}, definitions: {} }, revision: 'revision-8' });
        await nextTick();
        expect(wrapper.vm.editorRevision).toBe('revision-8');
        expect(wrapper.vm.snapshot.revision).toBe('revision-8');

        wrapper.vm.section = 'anchors';
        await nextTick();
        const anchorEditor = wrapper.findComponent({ name: 'GamePrimitiveAnchorInstanceEditorPanel' });
        expect(anchorEditor.exists()).toBe(true);
        expect(anchorEditor.props('revision')).toBe('revision-8');
        expect(anchorEditor.props('draft').id).toBe('edit');
        expect(anchorEditor.props('anchors')[0].meta).toEqual({ chapter: 1 });
        wrapper.unmount();
    });

    it('exposes deterministic adventure authoring/runtime and accepts authoritative child snapshots', async () => {
        const { websocket, wrapper } = mountPanel();
        const authored = {
            id: 'journey', title: 'Journey', description: null, start_scene: 'start',
            scenes: { start: { id: 'start', title: 'Start', description: null, location: null, intro: null, goals: [], local_anchors: [], entry_effects: [], exit_effects: [], render_policy: 'prompt' } },
            transitions: {},
        };
        dispatchSnapshot(websocket, emptySnapshot({ revision: 'revision-3', definitions: [{ kind: 'adventures', id: 'journey', title: 'Journey', details: authored }] }));
        await nextTick();
        wrapper.vm.editorDraft = { id: 'adventure-edit', anchors: {}, definitions: {} };
        wrapper.vm.section = 'adventure';
        await nextTick();
        expect(wrapper.findComponent({ name: 'GamePrimitivesAdventureList' }).props('adventures').map((item) => item.id)).toEqual(['journey']);
        expect(wrapper.findComponent({ name: 'GamePrimitivesAdventureRuntime' }).props('snapshot').revision).toBe('revision-3');

        wrapper.findComponent({ name: 'GameSystemsAdventureSection' }).vm.selectAdventure('journey');
        await nextTick();
        const editor = wrapper.findComponent({ name: 'GamePrimitivesAdventureEditor' });
        expect(editor.props('draftId')).toBe('adventure-edit');
        expect(editor.props('revision')).toBe('revision-3');

        const refreshed = emptySnapshot({ revision: 'revision-4', current_adventure: null });
        wrapper.findComponent({ name: 'GamePrimitivesAdventureRuntime' }).vm.$emit('snapshot', refreshed);
        await nextTick();
        expect(wrapper.vm.snapshot.revision).toBe('revision-4');
        expect(wrapper.vm.editorRevision).toBe('revision-4');
        wrapper.unmount();
    });

    it('integrates create, edit, validate, and commit into the authoritative snapshot', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({ revision: 'revision-1' }));
        await nextTick();
        wrapper.vm.section = 'definitions';
        await nextTick();

        const panel = wrapper.findComponent({ name: 'GamePrimitiveDraftEditorPanel' });
        expect(websocket.outgoing.at(-1)).toMatchObject({ action: 'list_game_primitive_drafts' });
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitive_drafts', request_id: pendingRequestId(websocket), data: [], revision: 'revision-1',
        });
        await flushPromises();

        panel.vm.newDraftId = 'working';
        const create = panel.vm.create();
        expect(websocket.outgoing.at(-1)).toMatchObject({ action: 'create_game_primitive_draft', draft_id: 'working', expected_revision: 'revision-1' });
        dispatchDraft(websocket, draft(), 'revision-2');
        await create;
        await nextTick();
        expect(wrapper.vm.editorDraft.id).toBe('working');

        const meter = { id: 'focus', label: 'Focus', min: 0, max: 10, value: 3, render_policy: 'summary' };
        panel.findComponent({ name: 'GamePrimitiveDefinitionDraftEditor' }).vm.$emit('upsert', 'meters', meter);
        expect(websocket.outgoing.at(-1)).toMatchObject({
            action: 'upsert_game_primitive_definition', draft_id: 'working', expected_revision: 'revision-2',
            definition: { kind: 'meters', id: 'focus', value: meter },
        });
        const edited = draft({ definitions: { ...draft().definitions, meters: { focus: meter } } });
        dispatchDraft(websocket, edited, 'revision-3');
        await flushPromises();
        expect(wrapper.vm.editorDraft.definitions.meters.focus.value).toBe(3);

        const validate = panel.findAll('test-vbtn').find((button) => button.text() === 'Validate');
        await validate.trigger('click');
        expect(websocket.outgoing.at(-1)).toMatchObject({ action: 'validate_game_primitive_draft', expected_revision: 'revision-3' });
        const validated = draft({ ...edited, status: 'validated', validation: { ok: true, errors: [], warnings: [] } });
        dispatchDraft(websocket, validated, 'revision-4');
        await flushPromises();

        const committed = emptySnapshot({
            revision: 'revision-5', definition_counts: { meters: 1 },
            definitions: [{ kind: 'meters', id: 'focus', title: 'Focus', details: meter }],
        });
        const commit = panel.vm.commit();
        expect(websocket.outgoing.at(-1)).toMatchObject({ action: 'commit_game_primitive_draft', draft_id: 'working', expected_revision: 'revision-4' });
        dispatchSnapshot(websocket, committed);
        await commit;
        await nextTick();
        expect(wrapper.vm.snapshot).toEqual(committed);
        expect(wrapper.vm.editorRevision).toBe('revision-5');
        expect(wrapper.vm.editorDraft).toBeNull();
        wrapper.unmount();
    });

    it('keeps a stale commit visible in the integrated definitions section', async () => {
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket);
        await nextTick();
        const validDraft = draft({ validation: { ok: true, errors: [], warnings: [] } });
        wrapper.vm.applyDraftState({ draft: validDraft, revision: 'revision-1' });
        wrapper.vm.section = 'definitions';
        await nextTick();
        dispatchDraft(websocket, validDraft, 'revision-1');
        await flushPromises();

        const panel = wrapper.findComponent({ name: 'GamePrimitiveDraftEditorPanel' });
        const commit = panel.vm.commit();
        const request = websocket.outgoing.at(-1);
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives_failed', request_id: request.request_id,
            request_action: 'commit_game_primitive_draft', error: { message: 'Stale Game Primitives revision: expected revision-2' },
        });
        await expect(commit).rejects.toThrow('Stale Game Primitives revision');
        await nextTick();
        expect(panel.get('[data-testid="stale-draft"]').text()).toContain('no changes were overwritten');
        expect(wrapper.vm.snapshot.revision).toBe('revision-1');
        wrapper.unmount();
    });

    it('integrates deletion preview cancellation and explicit confirmation', async () => {
        const anchor = {
            ref: 'scene:main', kind: 'scene', id: 'main', tags: [], meta: {},
            primitives: { meters: { focus: { id: 'focus', label: null, min: 0, max: 5, value: 2, render_policy: 'summary' } } },
            primitive_counts: { meters: 1 }, primitive_count: 1, primitive_refs: ['scene:main/meters/focus'],
        };
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, emptySnapshot({ anchor_count: 1, primitive_count: 1, anchors: [anchor] }));
        await nextTick();
        wrapper.vm.applyDraftState({ draft: draft(), revision: 'revision-1' });
        wrapper.vm.section = 'anchors';
        await nextTick();
        const panel = wrapper.findComponent({ name: 'GamePrimitiveAnchorInstanceEditorPanel' });

        const previewResponse = () => ({
            type: 'world_state_manager', action: 'game_primitive_deletion_preview', request_id: pendingRequestId(websocket), revision: 'revision-1',
            target: { kind: 'anchor', ref: 'scene:main' }, draft: draft(), validation: { ok: true, errors: [], warnings: [] },
            candidate: { before: { definitions: 0, anchors: 1, primitives: 1 }, after: { definitions: 0, anchors: 0, primitives: 0 }, candidate_revision: 'candidate-1' },
        });
        const firstPreview = panel.vm.deleteAnchor('scene:main');
        websocket.dispatch(previewResponse());
        await firstPreview;
        await nextTick();
        expect(panel.get('[data-testid="deletion-preview"]').text()).toContain('Anchors 1 -> 0');
        await panel.findAll('test-vbtn').find((button) => button.text() === 'Cancel').trigger('click');
        expect(panel.find('[data-testid="deletion-preview"]').exists()).toBe(false);
        expect(websocket.outgoing.filter((message) => message.action === 'delete_game_primitive_anchor')).toHaveLength(0);

        const secondPreview = panel.vm.deleteAnchor('scene:main');
        websocket.dispatch(previewResponse());
        await secondPreview;
        const confirm = panel.vm.confirmDelete();
        expect(websocket.outgoing.at(-1)).toMatchObject({ action: 'delete_game_primitive_anchor', draft_id: 'working', anchor: 'scene:main', expected_revision: 'revision-1' });
        dispatchDraft(websocket, draft({ deletions: { definitions: [], anchors: ['scene:main'], primitives: [] } }), 'revision-2');
        await confirm;
        await nextTick();
        expect(panel.find('[data-testid="deletion-preview"]').exists()).toBe(false);
        expect(wrapper.vm.editorRevision).toBe('revision-2');
        wrapper.unmount();
    });

    it('accepts authoritative relationship and adventure snapshots from section children', async () => {
        const authoredAdventure = adventureDefinition();
        const initial = emptySnapshot({
            relationships: [relationship()],
            definitions: [{ kind: 'adventures', id: 'journey', title: 'Journey', details: authoredAdventure }],
        });
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, initial);
        await nextTick();
        wrapper.vm.section = 'relationships';
        await nextTick();

        const detail = wrapper.findComponent({ name: 'WorldStateManagerRelationshipDetail' });
        const relationshipUpdate = detail.vm.saveDimension({ ...relationship().dimensions[0], value: 4 });
        const relationshipSnapshot = emptySnapshot({ revision: 'revision-2', relationships: [relationship(4)], definitions: initial.definitions });
        dispatchSnapshot(websocket, relationshipSnapshot);
        await relationshipUpdate;
        await nextTick();
        expect(wrapper.vm.snapshot.relationships[0].dimensions[0].value).toBe(4);

        wrapper.vm.section = 'adventure';
        await nextTick();
        const runtime = wrapper.findComponent({ name: 'GamePrimitivesAdventureRuntime' });
        const activation = runtime.vm.activate('journey');
        const adventureSnapshot = emptySnapshot({
            revision: 'revision-3', relationships: [relationship(4)], definitions: initial.definitions,
            current_adventure: {
                id: 'journey', title: 'Journey', description: null,
                current_story_scene: { id: 'start', title: 'Start', description: null, location: null, intro: null, goals: [], local_anchors: [], render_policy: 'prompt' },
                state: { visited: ['start'], completed: [], transition_log: [] }, transitions: [],
            },
        });
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitive_adventure_activation', request_id: pendingRequestId(websocket),
            result: { ok: true, adventure_id: 'journey', state: null, error: null }, data: adventureSnapshot,
        });
        await activation;
        await nextTick();
        expect(wrapper.vm.snapshot.revision).toBe('revision-3');
        expect(wrapper.vm.snapshot.current_adventure.current_story_scene.id).toBe('start');
        wrapper.unmount();
    });

    it('adopts the authoritative snapshot after an exactly correlated adventure transition', async () => {
        const authoredAdventure = adventureDefinition();
        authoredAdventure.scenes.finish = { ...authoredAdventure.scenes.start, id: 'finish', title: 'Finish' };
        authoredAdventure.transitions.continue = { id: 'continue', label: 'Continue', from_scene: 'start', to_scene: 'finish', conditions: [], effects: [], carry_anchors: ['character:Hero'] };
        const runtimeScene = (scene) => ({
            id: scene.id, title: scene.title, description: scene.description, location: scene.location,
            intro: scene.intro, goals: scene.goals, local_anchors: scene.local_anchors, render_policy: scene.render_policy,
        });
        const currentAdventure = {
            id: 'journey', title: 'Journey', description: null,
            current_story_scene: runtimeScene(authoredAdventure.scenes.start),
            state: { visited: ['start'], completed: [], transition_log: [] },
            transitions: [{ id: 'continue', label: 'Continue', to_scene: 'finish', available: true, reasons: [] }],
        };
        const initial = emptySnapshot({
            revision: 'revision-7',
            definitions: [{ kind: 'adventures', id: 'journey', title: 'Journey', details: authoredAdventure }],
            current_adventure: currentAdventure,
        });
        const { websocket, wrapper } = mountPanel();
        dispatchSnapshot(websocket, initial);
        await nextTick();
        wrapper.vm.section = 'adventure';
        await nextTick();

        const runtime = wrapper.findComponent({ name: 'GamePrimitivesAdventureRuntime' });
        const transition = runtime.vm.takeTransition('continue');
        const request = websocket.outgoing.at(-1);
        expect(request).toEqual({
            type: 'world_state_manager', action: 'take_game_primitive_adventure_transition',
            request_id: expect.any(String), transition_id: 'continue',
        });
        expect(runtime.vm.busy).toBe(true);

        const authoritative = emptySnapshot({
            revision: 'revision-8',
            definitions: initial.definitions,
            current_adventure: {
                ...currentAdventure,
                current_story_scene: runtimeScene(authoredAdventure.scenes.finish),
                state: {
                    visited: ['start', 'finish'], completed: ['start'],
                    transition_log: [{ transition_id: 'continue', from_scene: 'start', to_scene: 'finish', carry_anchors: ['character:Hero'] }],
                },
                transitions: [],
            },
            recent_ledger: [{
                id: 'ledger-transition', op: 'adventure.transition', ref: 'adventures/journey', anchor: null,
                input: { transition_id: 'continue' }, output: { from_scene: 'start', to_scene: 'finish' }, message: 'Continued to Finish',
            }],
        });
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitive_adventure_transition', request_id: 'unrelated-request',
            result: { ok: true, transition_id: 'continue', from_scene: 'start', to_scene: 'finish', intro: null, error: null, effects: [] },
            data: authoritative,
        });
        expect(runtime.vm.busy).toBe(true);
        expect(wrapper.vm.snapshot).toEqual(initial);

        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitive_adventure_transition', request_id: request.request_id,
            result: { ok: true, transition_id: 'continue', from_scene: 'start', to_scene: 'finish', intro: null, error: null, effects: [] },
            data: authoritative,
        });
        await transition;
        await nextTick();

        expect(wrapper.vm.snapshot).toEqual(authoritative);
        expect(wrapper.vm.snapshot.current_adventure.current_story_scene.id).toBe('finish');
        expect(wrapper.vm.snapshot.current_adventure.state.visited).toEqual(['start', 'finish']);
        expect(wrapper.vm.snapshot.current_adventure.state.transition_log).toEqual(authoritative.current_adventure.state.transition_log);
        expect(wrapper.vm.snapshot.recent_ledger).toEqual(authoritative.recent_ledger);
        expect(runtime.vm.busy).toBe(false);
        expect(runtime.vm.error).toBeNull();
        wrapper.unmount();
    });

    it('unregisters the exact handler on unmount', async () => {
        const { websocket, wrapper } = mountPanel();
        const handlers = websocket.registerMessageHandler.mock.calls.map(([handler]) => handler);
        expect(websocket.handlerCount).toBe(2);

        dispatchSnapshot(websocket);
        await nextTick();
        wrapper.unmount();
        for (const handler of handlers) expect(websocket.unregisterMessageHandler).toHaveBeenCalledWith(handler);
        expect(websocket.handlerCount).toBe(0);
        expect(websocket.websocket.removeEventListener).toHaveBeenCalledTimes(2);
    });
});

describe('WorldStateManagerScene Game Systems navigation', () => {
    it('deep-links scene to primitives and delegates active refresh', async () => {
        const websocket = createWebsocketHarness();
        const wrapper = mount(WorldStateManagerScene, {
            props: {
                scene: { title: 'Test Scene', data: { context: 'Test context' } },
                appConfig: {}, templates: {}, generationOptions: {},
            },
            global: {
                provide: {
                    ...websocket.provide,
                    setWaitingForInput: () => {},
                    requestSceneAssets: () => {},
                },
                stubs: {
                    ...vuetifyStubs,
                    WorldStateManagerSceneOutline: true,
                    WorldStateManagerSceneSettings: true,
                    WorldStateManagerSceneExport: true,
                    WorldStateManagerSceneDirection: true,
                    GameState: true,
                    WorldStateManagerSceneSharedWorld: true,
                },
            },
        });

        const navigation = wrapper.get('.scene-navigation');
        expect(navigation.attributes()).toHaveProperty('show-arrows');
        expect(wrapper.get('.scene-content').classes()).toContain('scene-content');
        const primitivesTab = wrapper.findAll('test-vtab').find((tab) => tab.attributes('value') === 'primitives');
        await primitivesTab.trigger('click');
        await nextTick();
        expect(wrapper.vm.page).toBe('primitives');
        expect(websocket.outgoing[0]).toMatchObject({ type: 'world_state_manager', action: 'get_game_primitives' });
        expect(websocket.outgoing[0].request_id).toEqual(expect.any(String));

        const anchor = 'relationship:Alice->Bob';
        wrapper.vm.navigate('primitives', anchor);
        dispatchSnapshot(websocket, emptySnapshot({ relationships: [relationship()] }));
        await nextTick();
        const gameSystems = wrapper.findComponent(WorldStateManagerSceneGameSystems);
        expect(gameSystems.vm.section).toBe('relationships');
        expect(gameSystems.vm.focusedAnchor).toBe(anchor);
        expect(gameSystems.findComponent({ name: 'WorldStateManagerRelationshipDetail' }).classes()).toContain('focused-anchor');
        await wrapper.findComponent(WorldStateManagerSceneGameSystems).get('test-vbtn').trigger('click');
        expect(websocket.outgoing).toHaveLength(2);
        dispatchSnapshot(websocket);
        await nextTick();
        wrapper.unmount();
        expect(websocket.handlerCount).toBe(0);
    });
});
