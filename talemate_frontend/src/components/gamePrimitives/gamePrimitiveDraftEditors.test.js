import { mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';
import { describe, expect, it } from 'vitest';

import GamePrimitiveDeckForm from './GamePrimitiveDeckForm.vue';
import GamePrimitiveDefinitionDraftEditor from './GamePrimitiveDefinitionsEditor.vue';
import GamePrimitiveRollTableForm from './GamePrimitiveRollTableForm.vue';
import {
    canonicalDefinition,
    definitionFieldErrors,
    emptyDefinition,
} from './gamePrimitiveDraftContracts.js';
import { useGamePrimitiveDraftLifecycle } from './useGamePrimitiveDraftLifecycle.js';
import { createVuetifyStubs, createWebsocketHarness } from '../../test/websocketHarness.js';
import { editorMetadata } from '../../test/gamePrimitiveFixtures.js';

const stubs = createVuetifyStubs([
    'VAlert', 'VBtn', 'VCard', 'VCardActions', 'VCardText', 'VCardTitle', 'VCheckbox',
    'VChip', 'VCombobox', 'VNumberInput', 'VProgressLinear', 'VSelect', 'VSpacer',
    'VTextField', 'VTextarea',
]);

function definitions() {
    return {
        decks: {}, roll_tables: {}, meters: {}, clocks: {}, relationship_models: {},
        modifiers: {}, attribute_sources: {}, adventures: {},
    };
}

function draft(overrides = {}) {
    return {
        id: 'working', status: 'draft', created_by: 'ui', definitions: definitions(),
        anchors: {},
        replacements: { definitions: [], anchors: [], primitives: [] },
        deletions: { definitions: [], anchors: [], primitives: [] },
        validation: { ok: false, errors: [], warnings: [] },
        ...overrides,
    };
}

const validDefinitions = {
    meters: { id: 'focus', label: 'Focus', min: 0, max: 10, value: 4, render_policy: 'hidden' },
    clocks: { id: 'alarm', label: null, max: 4, value: 1, render_policy: 'summary' },
    modifiers: { id: 'storm', label: 'Storm', explanation: null, applies_to: 'weather', when: [], add: 1 },
    decks: {
        id: 'weather', name: 'Weather', mode: 'bag', shuffle: 'seeded', reshuffle: 'when_empty', tags: ['outdoor'], variables: { season: 'winter' },
        cards: [{ id: 'rain', label: 'Rain', text: 'It rains.', weight: 1, tags: [], variables: {}, effects: [], conditions: [], cooldown_turns: null, unique: false }],
    },
    roll_tables: {
        id: 'weather', name: 'Weather', mode: 'dice', dice: '1d6', modifiers: ['storm'],
        rows: [{ id: 'rain', label: 'Rain', text: null, range: '1-6', weight: null, tags: [], variables: {}, effects: [], conditions: [] }],
    },
};

describe('Game Primitive definition contracts', () => {
    it.each(Object.entries(validDefinitions))('round-trips canonical %s definitions without field loss', (kind, value) => {
        expect(canonicalDefinition(kind, structuredClone(value))).toEqual(value);
    });

    it.each([
        ['meters', { ...validDefinitions.meters, value: 11 }],
        ['clocks', { ...validDefinitions.clocks, max: 0 }],
        ['decks', { ...validDefinitions.decks, cards: [...validDefinitions.decks.cards, structuredClone(validDefinitions.decks.cards[0])] }],
        ['roll_tables', { ...validDefinitions.roll_tables, dice: 'd20' }],
    ])('does not duplicate backend domain validation for %s', (kind, value) => {
        expect(definitionFieldErrors(kind, value)).toEqual({});
    });

    it('accepts backend-owned effect kinds while retaining nested structural validation', () => {
        const deck = structuredClone(validDefinitions.decks);
        deck.cards[0].effects = [{ op: 'unknown', target: null, value: null, by: null, data: {} }];
        deck.cards[0].conditions = [{ operator: 'xor', conditions: [] }];
        const errors = definitionFieldErrors('decks', deck);
        expect(errors).not.toHaveProperty('cards.0.effects.0.op');
        expect(errors).toHaveProperty('cards.0.conditions.0.operator');
    });
});

describe('Game Primitive structured forms', () => {
    it.each(Object.entries(validDefinitions))('selects and submits the structured %s form', async (kind, value) => {
        const staged = definitions();
        staged[kind] = { [value.id]: value };
        const wrapper = mount(GamePrimitiveDefinitionDraftEditor, {
            props: { definitions: staged, editorMetadata }, global: { stubs },
        });
        const item = wrapper.vm.items.find((entry) => entry.kind === kind);
        wrapper.vm.startEdit(item);
        await nextTick();
        expect(wrapper.vm.activeForm).toBeTruthy();
        wrapper.vm.save(wrapper.vm.editing.value);
        expect(wrapper.emitted('upsert')[0]).toEqual([kind, value]);
    });

    it('duplicates and reorders cards deterministically without mutating the input', () => {
        const source = structuredClone(validDefinitions.decks);
        const wrapper = mount(GamePrimitiveDeckForm, { props: { value: source }, global: { stubs } });
        wrapper.vm.duplicateCard(0);
        expect(wrapper.vm.form.cards.map((card) => card.id)).toEqual(['rain', 'rain-copy']);
        wrapper.vm.move(1, -1);
        expect(wrapper.vm.form.cards.map((card) => card.id)).toEqual(['rain-copy', 'rain']);
        expect(source.cards).toHaveLength(1);
    });

    it('duplicates and reorders rows deterministically without mutating the input', () => {
        const source = structuredClone(validDefinitions.roll_tables);
        const wrapper = mount(GamePrimitiveRollTableForm, { props: { value: source }, global: { stubs } });
        wrapper.vm.duplicateRow(0);
        expect(wrapper.vm.form.rows.map((row) => row.id)).toEqual(['rain', 'rain-copy']);
        wrapper.vm.move(1, -1);
        expect(wrapper.vm.form.rows.map((row) => row.id)).toEqual(['rain-copy', 'rain']);
        expect(source.rows).toHaveLength(1);
    });

    it('provides add/edit/duplicate/delete flows and keeps unsupported definitions read-only', async () => {
        const committed = [
            { kind: 'meters', id: 'focus', title: 'Focus', details: validDefinitions.meters },
            { kind: 'relationship_models', id: 'social', title: 'Social', details: { dimensions: ['trust'] } },
        ];
        const wrapper = mount(GamePrimitiveDefinitionDraftEditor, {
            props: { definitions: { ...definitions(), meters: { focus: validDefinitions.meters }, relationship_models: { social: { dimensions: ['trust'] } } }, editorMetadata, validation: { errors: ['Missing modifier target: absent'], warnings: ['Review this draft'] } }, global: { stubs },
        });
        expect(wrapper.vm.items.map((item) => `${item.kind}/${item.id}`)).toEqual(['meters/focus']);
        expect(wrapper.text()).toContain('Missing modifier target: absent');
        expect(wrapper.text()).toContain('Review this draft');

        wrapper.vm.startDuplicate(wrapper.vm.items[0]);
        expect(wrapper.vm.editing.value.id).toBe('focus-copy');
        wrapper.vm.save(wrapper.vm.editing.value);
        expect(wrapper.emitted('upsert')[0]).toEqual(['meters', { ...validDefinitions.meters, id: 'focus-copy' }]);

        await wrapper.setProps({ definitions: { ...definitions(), meters: { focus: validDefinitions.meters } } });
        wrapper.vm.startEdit(wrapper.vm.items[0]);
        wrapper.vm.editing.value.value = 9;
        wrapper.vm.cancel();
        expect(committed[0].details.value).toBe(4);
        wrapper.vm.startAdd();
        expect(wrapper.vm.editing.value).toEqual(emptyDefinition('meters'));
        wrapper.vm.startEdit(wrapper.vm.items[0]);
        wrapper.vm.$emit('delete', 'meters', 'focus');
        expect(wrapper.emitted('delete').at(-1)).toEqual(['meters', 'focus']);
    });
});

describe('useGamePrimitiveDraftLifecycle', () => {
    function mountComposable() {
        const websocket = createWebsocketHarness();
        const Host = defineComponent({
            setup() { return useGamePrimitiveDraftLifecycle(); },
            template: '<div />',
        });
        const wrapper = mount(Host, { global: { provide: websocket.provide } });
        return { websocket, wrapper };
    }

    it('correlates list/select/upsert requests and advances the returned revision', async () => {
        const { websocket, wrapper } = mountComposable();
        const listPromise = wrapper.vm.listDrafts();
        expect(websocket.outgoing[0]).toMatchObject({ type: 'world_state_manager', action: 'list_game_primitive_drafts' });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_drafts', request_id: websocket.outgoing[0].request_id, data: [draft({ id: 'z' }), draft({ id: 'a' })], revision: 'r1' });
        await listPromise;
        expect(wrapper.vm.drafts.map((item) => item.id)).toEqual(['a', 'z']);

        const selectPromise = wrapper.vm.selectDraft('a');
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[1].request_id, data: draft({ id: 'a' }), revision: 'r2' });
        await selectPromise;
        const savePromise = wrapper.vm.upsertDefinition('meters', validDefinitions.meters);
        expect(websocket.outgoing[2]).toEqual(expect.objectContaining({
            action: 'upsert_game_primitive_definition', draft_id: 'a', expected_revision: 'r2',
            definition: { kind: 'meters', id: 'focus', value: validDefinitions.meters },
        }));
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[2].request_id, data: draft({ id: 'a', definitions: { ...definitions(), meters: { focus: validDefinitions.meters } } }), revision: 'r3' });
        await savePromise;
        expect(wrapper.vm.revision).toBe('r3');
        wrapper.unmount();
        expect(websocket.handlerCount).toBe(0);
    });

    it('surfaces stale failures and refreshes instead of retrying the mutation', async () => {
        const { websocket, wrapper } = mountComposable();
        const listPromise = wrapper.vm.listDrafts();
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_drafts', request_id: websocket.outgoing[0].request_id, data: [], revision: 'r1' });
        await listPromise;
        wrapper.vm.selectedDraftId = 'working';
        const savePromise = wrapper.vm.upsertDefinition('clocks', validDefinitions.clocks);
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives_failed', request_id: websocket.outgoing[1].request_id, request_action: 'upsert_game_primitive_definition', error: { message: 'Stale Game Primitives revision: expected r1' } });
        await expect(savePromise).rejects.toThrow('Stale Game Primitives revision');
        expect(wrapper.vm.stale).toBe(true);
        const refreshPromise = wrapper.vm.refresh();
        expect(websocket.outgoing[2]).toMatchObject({ action: 'get_game_primitive_draft', draft_id: 'working' });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[2].request_id, data: draft(), revision: 'r2' });
        await refreshPromise;
        expect(wrapper.vm.stale).toBe(false);
        wrapper.unmount();
    });

    it('rejects malformed correlated responses without accepting partial state', async () => {
        const { websocket, wrapper } = mountComposable();
        const promise = wrapper.vm.listDrafts();
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_drafts', request_id: websocket.outgoing[0].request_id, data: [{ id: 'partial' }], revision: 'r1' });
        await expect(promise).rejects.toThrow('Malformed list_game_primitive_drafts response');
        await nextTick();
        expect(wrapper.vm.drafts).toEqual([]);
        expect(wrapper.vm.busy).toBe(false);
        wrapper.unmount();
    });
});
