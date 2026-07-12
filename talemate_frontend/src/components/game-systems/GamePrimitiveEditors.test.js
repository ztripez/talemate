import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';
import { describe, expect, it } from 'vitest';

import { createWebsocketHarness } from '../../test/websocketHarness.js';
import { editorMetadata } from '../../test/gamePrimitiveFixtures.js';
import AnchorEditor from './GamePrimitiveAnchorMetadataEditor.vue';
import AttributeEditor from './GamePrimitiveAttributeSourceEditor.vue';
import DeckEditor from './GamePrimitiveDeckInstanceEditor.vue';
import MeterClockEditor from './GamePrimitiveMeterClockEditor.vue';
import RollTableEditor from './GamePrimitiveRollTableInstanceEditor.vue';
import { canonicalAnchorRef, canonicalPrimitiveRef, parseAnchorRef, parsePrimitiveRef } from './gamePrimitiveRefs.js';
import { useGamePrimitiveDraft } from './useGamePrimitiveDraft.js';
import { useGamePrimitiveDraftLifecycle } from '../gamePrimitives/useGamePrimitiveDraftLifecycle.js';

describe('canonical Game Primitive refs', () => {
    it('builds canonical anchor and primitive refs and rejects invalid segments', () => {
        expect(canonicalAnchorRef('character', ' Ada ')).toBe('character:Ada');
        expect(canonicalAnchorRef('relationship', 'Ada -> Bea')).toBe('relationship:Ada->Bea');
        expect(canonicalPrimitiveRef('character:Ada', 'meters', 'focus')).toBe('character:Ada/meters/focus');
        expect(canonicalAnchorRef('custom', 'Ada')).toBe('custom:Ada');
        expect(parseAnchorRef('relationship:Ada->Bea')).toEqual({ kind: 'relationship', id: 'Ada->Bea', ref: 'relationship:Ada->Bea' });
        expect(parsePrimitiveRef('character:Ada/meters/focus')).toEqual({ anchor: 'character:Ada', anchorKind: 'character', anchorId: 'Ada', kind: 'meters', id: 'focus', ref: 'character:Ada/meters/focus' });
        expect(() => canonicalPrimitiveRef('character:Ada', 'meters', 'bad/id')).toThrow('canonical path segment');
        expect(() => parsePrimitiveRef('character:Ada/meters/focus/extra')).toThrow('Primitive ref must use');
    });
});

describe('Game Primitive draft transport', () => {
    function draft(overrides = {}) {
        const targets = { definitions: [], anchors: [], primitives: [] };
        return {
            id: 'edit', status: 'draft', created_by: 'ui',
            definitions: { decks: {}, roll_tables: {}, meters: {}, clocks: {}, relationship_models: {}, modifiers: {}, attribute_sources: {}, adventures: {} },
            anchors: {}, replacements: targets, deletions: targets,
            validation: { ok: true, errors: [], warnings: [] }, ...overrides,
        };
    }
    function mountClient() {
        const websocket = createWebsocketHarness();
        const Host = defineComponent({
            setup() { return useGamePrimitiveDraft({ revision: 'revision-1' }); },
            template: '<div />',
        });
        const wrapper = mount(Host, { global: { provide: websocket.provide } });
        return { websocket, wrapper };
    }

    const flows = [
        ['definition', () => useGamePrimitiveDraftLifecycle({ initialRevision: 'revision-1', initialDraft: draft(), initialDraftId: 'edit' }), (client) => client.upsertDefinition('meters', { id: 'focus' })],
        ['anchor/instance', () => useGamePrimitiveDraft({ revision: 'revision-1', draft: draft() }), (client) => client.upsertAnchor('scene:main', { tags: [], meta: {} })],
        ['adventure', () => useGamePrimitiveDraftLifecycle({ initialRevision: 'revision-1', initialDraft: draft(), initialDraftId: 'edit' }), (client) => client.upsertDefinition('adventures', { id: 'journey' })],
    ];

    it.each(flows)('%s uses the canonical stale, revision, and commit lifecycle', async (_name, useFlow, mutate) => {
        const websocket = createWebsocketHarness();
        const Host = defineComponent({ setup: useFlow, template: '<div />' });
        const wrapper = mount(Host, { global: { provide: websocket.provide } });

        const rejected = mutate(wrapper.vm);
        const mutation = websocket.outgoing[0];
        expect(mutation.expected_revision).toBe('revision-1');
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives_failed', request_id: mutation.request_id, request_action: mutation.action, error: { message: 'Stale Game Primitives revision: expected revision-1' } });
        await expect(rejected).rejects.toThrow('Stale Game Primitives revision');
        expect(wrapper.vm.stale).toBe(true);
        expect(wrapper.vm.revision).toBe('revision-1');

        const validation = wrapper.vm.validateDraft?.() ?? wrapper.vm.validate();
        expect(websocket.outgoing[1]).toMatchObject({ action: 'validate_game_primitive_draft', draft_id: 'edit', expected_revision: 'revision-1' });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[1].request_id, revision: 'revision-2', data: draft() });
        await validation;
        expect(wrapper.vm.stale).toBe(false);
        expect(wrapper.vm.revision).toBe('revision-2');

        const committed = wrapper.vm.commitDraft?.() ?? wrapper.vm.commit();
        expect(websocket.outgoing[2]).toMatchObject({ action: 'commit_game_primitive_draft', draft_id: 'edit', expected_revision: 'revision-2' });
        const authoritative = {
            initialized: true, version: 1, revision: 'revision-3', editor_metadata: editorMetadata,
            definition_counts: {}, definitions: [], anchor_count: 0, primitive_count: 0, anchors: [],
            active_characters: [], relationships: [], drafts: [], current_adventure: null, recent_ledger: [],
        };
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives', request_id: websocket.outgoing[2].request_id, data: authoritative });
        await expect(committed).resolves.toEqual(authoritative);
        expect(wrapper.vm.revision).toBe('revision-3');
        expect(wrapper.vm.draft).toBeNull();
        expect(wrapper.vm.selectedDraftId).toBe('');
        wrapper.unmount();
    });

    it('correlates responses strictly and advances the revision', async () => {
        const { websocket, wrapper } = mountClient();
        const promise = wrapper.vm.createDraft('edit');
        const request = websocket.outgoing[0];
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: 'other', revision: 'wrong', data: { id: 'other' } });
        expect(wrapper.vm.busy).toBe(true);
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: request.request_id, revision: 'revision-2', data: draft() });
        await promise;
        expect(wrapper.vm.revision).toBe('revision-2');
        expect(wrapper.vm.draft.id).toBe('edit');
        wrapper.unmount();
    });

    it('marks matching stale failures and ignores the wrong request action', async () => {
        const { websocket, wrapper } = mountClient();
        const promise = wrapper.vm.createDraft('edit');
        const request = websocket.outgoing[0];
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives_failed', request_id: request.request_id, request_action: 'commit_game_primitive_draft', error: { message: 'wrong' } });
        expect(wrapper.vm.busy).toBe(true);
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives_failed', request_id: request.request_id, request_action: request.action, error: { message: 'Stale Game Primitives revision: expected old' } });
        await expect(promise).rejects.toThrow('Stale Game Primitives revision');
        expect(wrapper.vm.stale).toBe(true);
        wrapper.unmount();
    });

    it('previews deletion without mutation and tombstones only after explicit confirmation', async () => {
        const { websocket, wrapper } = mountClient();
        wrapper.vm.draft = { id: 'edit' };
        const promise = wrapper.vm.previewDeletePrimitive('scene:main/meters/focus');
        expect(websocket.outgoing[0]).toMatchObject({ action: 'preview_delete_game_primitive', expected_revision: 'revision-1' });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_deletion_preview', request_id: websocket.outgoing[0].request_id, revision: 'revision-1', target: { kind: 'primitive', ref: 'scene:main/meters/focus' }, draft: draft(), validation: { ok: false, errors: ['dangling ref'], warnings: [] }, candidate: { before: { definitions: 0, anchors: 1, primitives: 1 }, after: { definitions: 0, anchors: 1, primitives: 0 }, candidate_revision: 'candidate' } });
        await expect(promise).resolves.toMatchObject({ validation: { errors: ['dangling ref'] } });
        expect(websocket.outgoing).toHaveLength(1);
        const deletion = wrapper.vm.deletePrimitive('scene:main/meters/focus');
        expect(websocket.outgoing[1]).toMatchObject({ action: 'delete_game_primitive', draft_id: 'edit', expected_revision: 'revision-1' });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitive_draft', request_id: websocket.outgoing[1].request_id, revision: 'revision-2', data: draft() });
        await deletion;
        wrapper.unmount();
    });
});

describe('standalone Game Primitive editors', () => {
    it('submits anchor tags and metadata without primitive replacement data', async () => {
        const wrapper = mount(AnchorEditor, { props: { anchorRef: 'scene:main', anchorKinds: editorMetadata.anchor_kinds, value: { tags: ['old'], meta: { chapter: 2 } }, deletable: true } });
        await wrapper.get('input:not([disabled])').setValue('new, active');
        await wrapper.get('form').trigger('submit');
        expect(wrapper.emitted('submit')[0][0]).toEqual({ anchor: 'scene:main', value: { tags: ['new', 'active'], meta: { chapter: 2 } } });
        expect(wrapper.text()).toContain('Preview deletion');
    });

    it('keeps meter authored configuration distinct from effect adjustments', async () => {
        const value = { id: 'focus', label: 'Focus', min: 0, max: 5, value: 2, render_policy: 'summary' };
        const wrapper = mount(MeterClockEditor, { props: { kind: 'meters', value, renderPolicies: editorMetadata.render_policies } });
        expect(wrapper.get('[aria-label="Runtime state"]').text()).toContain('2 / 5');
        await wrapper.findAll('button').find((button) => button.text() === '+1').trigger('click');
        expect(wrapper.emitted('adjust')[0]).toEqual([1]);
        await wrapper.get('form').trigger('submit');
        expect(wrapper.emitted('submit')[0][0].value.value).toBe(2);
    });

    it('uses definition selectors and renders deck runtime read-only', async () => {
        const definitions = [{ id: 'omens', title: 'Omens' }];
        const runtime = { definition_id: 'omens', mode: 'draw', draw_pile: ['rain'] };
        const deck = mount(DeckEditor, { props: { definitions, value: { definition: 'omens', runtime } } });
        expect(deck.get('select').element.value).toBe('omens');
        expect(deck.get('[aria-label="Read-only deck runtime"] pre').text()).toContain('draw_pile');
        expect(deck.get('[aria-label="Read-only deck runtime"]').find('input').exists()).toBe(false);
        await deck.get('form').trigger('submit');
        expect(deck.emitted('submit')[0][0].value.runtime).toEqual(runtime);

        const table = mount(RollTableEditor, { props: { definitions: [{ id: 'weather', title: 'Weather' }], value: { definition: 'weather' } } });
        expect(table.get('select').element.value).toBe('weather');
    });

    it('submits render policy, conditions, and source-specific options', async () => {
        const wrapper = mount(AttributeEditor, { props: { value: { id: 'omen', source: 'deck', ref: 'scene:main/decks/omens', render_policy: 'prompt', options: { mode: 'peek' }, conditions: [{ operator: 'and', conditions: [{ kind: 'always' }] }] }, renderPolicies: editorMetadata.render_policies, conditionKinds: editorMetadata.condition_kinds } });
        expect(wrapper.findAll('select')[1].findAll('option').map((option) => option.text())).toEqual(editorMetadata.render_policies);
        await wrapper.get('form').trigger('submit');
        expect(wrapper.emitted('submit')[0][0]).toEqual({ kind: 'attributes', value: { id: 'omen', source: 'deck', ref: 'scene:main/decks/omens', render_policy: 'prompt', options: { mode: 'peek' }, conditions: [{ operator: 'and', conditions: [{ kind: 'always' }] }] } });
    });
});
