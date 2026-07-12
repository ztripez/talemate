import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { describe, expect, it } from 'vitest';

import AdventureEditor from './GamePrimitivesAdventureEditor.vue';
import AdventureList from './GamePrimitivesAdventureList.vue';
import AdventureRuntime from './GamePrimitivesAdventureRuntime.vue';
import { moveOrderedRecord, validateAdventureDefinition } from './gamePrimitivesAdventure.js';
import { createVuetifyStubs, createWebsocketHarness } from '../test/websocketHarness.js';
import { editorMetadata } from '../test/gamePrimitiveFixtures.js';

const stubs = createVuetifyStubs([
    'VAlert', 'VBtn', 'VCard', 'VCardText', 'VCardTitle', 'VChip', 'VCombobox',
    'VList', 'VListItem', 'VSelect', 'VTextField', 'VTextarea',
]);

function adventure() {
    return {
        id: 'journey', title: 'Journey', description: null, start_scene: 'start',
        scenes: {
            start: { id: 'start', title: 'Start', description: null, location: null, intro: null, goals: ['Leave'], local_anchors: ['location:Camp'], entry_effects: [], exit_effects: [], render_policy: 'prompt' },
            finish: { id: 'finish', title: 'Finish', description: null, location: null, intro: null, goals: [], local_anchors: [], entry_effects: [], exit_effects: [], render_policy: 'summary' },
        },
        transitions: {
            continue: { id: 'continue', from_scene: 'start', to_scene: 'finish', label: 'Continue', description: null, conditions: [], carry_anchors: ['character:Hero'], exit_effects: [], entry_effects: [], intro: null },
        },
    };
}

function snapshot(currentAdventure = null) {
    const current = currentAdventure ? {
        title: 'Journey', description: null,
        ...currentAdventure,
        current_story_scene: { description: null, location: null, intro: null, goals: [], local_anchors: [], render_policy: 'prompt', ...currentAdventure.current_story_scene },
    } : null;
    return {
        initialized: true, version: 1, revision: 'revision-runtime', editor_metadata: editorMetadata, definition_counts: {}, definitions: [],
        anchor_count: 0, primitive_count: 0, anchors: [], active_characters: [], relationships: [], drafts: [],
        current_adventure: current, recent_ledger: [],
    };
}

function draft(overrides = {}) {
    const targets = { definitions: [], anchors: [], primitives: [] };
    return {
        id: 'adventure-edit', status: 'draft', created_by: 'ui',
        definitions: { decks: {}, roll_tables: {}, meters: {}, clocks: {}, relationship_models: {}, modifiers: {}, attribute_sources: {}, adventures: {} },
        anchors: {}, replacements: targets, deletions: targets, validation: { ok: true, errors: [], warnings: [] }, ...overrides,
    };
}

describe('adventure authoring helpers', () => {
    it('reorders records without sorting or changing values', () => {
        const scenes = adventure().scenes;
        const reordered = moveOrderedRecord(scenes, 'finish', -1);
        expect(Object.keys(reordered)).toEqual(['finish', 'start']);
        expect(reordered.finish).toEqual(scenes.finish);
    });

    it('leaves graph and reference validation to the backend draft validator', () => {
        const value = adventure();
        value.transitions.continue.to_scene = 'missing';
        value.transitions.continue.entry_effects.push({ op: 'set', target: 'scene:main/meters/missing', value: 1, data: {} });
        expect(validateAdventureDefinition(value, ['location:Camp'], ['scene:main/meters/focus'])).toEqual([]);
    });
});

describe('GamePrimitivesAdventureEditor', () => {
    it('sends the exact ordered graph to the selected draft and accepts only its correlated response', async () => {
        const websocket = createWebsocketHarness();
        const wrapper = mount(AdventureEditor, {
            props: { modelValue: adventure(), draft: draft(), editorMetadata, draftId: 'adventure-edit', revision: 'revision-7', anchorRefs: ['location:Camp', 'character:Hero'] },
            global: { provide: websocket.provide, stubs },
        });

        wrapper.vm.moveScene('finish', -1);
        await nextTick();
        const save = wrapper.findAll('test-vbtn').find((button) => button.text() === 'Save to draft');
        await save.trigger('click');
        expect(websocket.outgoing).toHaveLength(1);
        expect(websocket.outgoing[0]).toMatchObject({
            type: 'world_state_manager', action: 'upsert_game_primitive_definition',
            draft_id: 'adventure-edit', expected_revision: 'revision-7',
            definition: { kind: 'adventures', id: 'journey' },
        });
        expect(Object.keys(websocket.outgoing[0].definition.value.scenes)).toEqual(['finish', 'start']);

        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: 'stale', data: {}, revision: 'wrong' });
        expect(wrapper.vm.busy).toBe(true);
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[0].request_id, data: draft(), revision: 'revision-8' });
        await nextTick();
        expect(wrapper.emitted('saved')[0][0]).toEqual({ draft: draft(), revision: 'revision-8' });
        expect(wrapper.vm.busy).toBe(false);
        wrapper.unmount();
        expect(websocket.handlerCount).toBe(0);
    });

    it('submits transient dangling graph input for authoritative backend validation', async () => {
        const websocket = createWebsocketHarness();
        const value = adventure(); value.transitions.continue.to_scene = 'missing';
        const wrapper = mount(AdventureEditor, { props: { modelValue: value, draft: draft({ id: 'edit' }), editorMetadata, draftId: 'edit', revision: 'r1' }, global: { provide: websocket.provide, stubs } });
        const save = wrapper.findAll('test-vbtn').find((button) => button.text() === 'Save to draft');
        await save.trigger('click');
        expect(websocket.outgoing[0]).toMatchObject({ action: 'upsert_game_primitive_definition', expected_revision: 'r1' });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[0].request_id, data: draft({ id: 'edit', validation: { ok: false, errors: ['Transition destination scene does not exist: missing'], warnings: [] } }), revision: 'r2' });
        await nextTick();
        expect(wrapper.text()).toContain('Transition destination scene does not exist: missing');
        wrapper.unmount();
    });
});

describe('standalone adventure list and runtime', () => {
    it('sorts the adventure catalog by id without mutating input', () => {
        const input = [{ ...adventure(), id: 'zeta' }, { ...adventure(), id: 'alpha' }];
        const wrapper = mount(AdventureList, { props: { adventures: input }, global: { stubs } });
        expect(wrapper.vm.ordered.map((item) => item.id)).toEqual(['alpha', 'zeta']);
        expect(input.map((item) => item.id)).toEqual(['zeta', 'alpha']);
    });

    it('activates through the correlated action and emits the authoritative refreshed snapshot', async () => {
        const websocket = createWebsocketHarness();
        const wrapper = mount(AdventureRuntime, { props: { snapshot: snapshot(), adventures: [adventure()] }, global: { provide: websocket.provide, stubs } });
        const activate = wrapper.findAll('test-vbtn').find((button) => button.text() === 'Activate');
        await activate.trigger('click');
        expect(websocket.outgoing[0]).toMatchObject({ action: 'activate_game_primitive_adventure', adventure_id: 'journey' });
        const refreshed = snapshot({
            id: 'journey', title: 'Journey', description: null,
            current_story_scene: { id: 'start', title: 'Start' },
            state: { visited: ['start'], completed: [], transition_log: [] }, transitions: [],
        });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_adventure_activation', request_id: websocket.outgoing[0].request_id, result: { ok: true, adventure_id: 'journey', state: null, error: null }, data: refreshed });
        await nextTick();
        expect(wrapper.emitted('snapshot')[0][0]).toStrictEqual(refreshed);
        expect(wrapper.vm.busy).toBe(false);
        wrapper.unmount();
    });

    it('shows availability reasons and sends no request for unavailable transitions', async () => {
        const websocket = createWebsocketHarness();
        const active = {
            id: 'journey', title: 'Journey', current_story_scene: { id: 'start', title: 'Start' },
            state: { visited: ['start'], completed: [], transition_log: [] },
            transitions: [{ id: 'continue', label: 'Continue', to_scene: 'finish', available: false, reasons: ['Transition conditions are not met'] }],
        };
        const wrapper = mount(AdventureRuntime, { props: { snapshot: snapshot(active), adventures: [adventure()] }, global: { provide: websocket.provide, stubs } });
        expect(wrapper.text()).toContain('Transition conditions are not met');
        const take = wrapper.findAll('test-vbtn').find((button) => button.text() === 'Take');
        expect(take.attributes()).toHaveProperty('disabled');
        await take.trigger('click');
        expect(websocket.outgoing).toEqual([]);
        wrapper.unmount();
    });

    it('renders actual visited/completed IDs and transition history', () => {
        const active = {
            id: 'journey', title: 'Journey', current_story_scene: { id: 'finish', title: 'Finish' },
            state: { visited: ['start', 'finish'], completed: ['start'], transition_log: [{ transition_id: 'continue', from_scene: 'start', to_scene: 'finish', carry_anchors: ['character:Hero'] }] },
            transitions: [],
        };
        const wrapper = mount(AdventureRuntime, { props: { snapshot: snapshot(active), adventures: [adventure()] }, global: { provide: createWebsocketHarness().provide, stubs } });
        expect(wrapper.text()).toContain('Visited scene IDsstartfinish');
        expect(wrapper.text()).toContain('Completed scene IDsstart');
        expect(wrapper.text()).toContain('continuestart -> finish · carried character:Hero');
        wrapper.unmount();
    });

    it('displays a structured transition rejection while refreshing state and ledger data', async () => {
        const websocket = createWebsocketHarness();
        const active = {
            id: 'journey', title: 'Journey', current_story_scene: { id: 'start', title: 'Start' },
            state: { visited: ['start'], completed: [], transition_log: [] },
            transitions: [{ id: 'continue', label: 'Continue', to_scene: 'finish', available: true, reasons: [] }],
        };
        const current = snapshot(active);
        const wrapper = mount(AdventureRuntime, { props: { snapshot: current, adventures: [adventure()] }, global: { provide: websocket.provide, stubs } });
        await wrapper.findAll('test-vbtn').find((button) => button.text() === 'Take').trigger('click');
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitive_adventure_transition', request_id: websocket.outgoing[0].request_id,
            result: { ok: false, transition_id: 'continue', from_scene: null, to_scene: null, intro: null, error: 'Transition conditions are not met', effects: [] }, data: current,
        });
        await nextTick();
        expect(wrapper.text()).toContain('Transition conditions are not met');
        expect(wrapper.emitted('snapshot')).toHaveLength(1);
        wrapper.unmount();
    });
});
