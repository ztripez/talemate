import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { describe, expect, it } from 'vitest';

import CharacterRelationships from './WorldStateManagerCharacterRelationships.vue';
import RelationshipDetail from './WorldStateManagerRelationshipDetail.vue';
import { canonicalAnchorRef } from './game-systems/gamePrimitiveRefs.js';
import { createVuetifyStubs, createWebsocketHarness } from '../test/websocketHarness.js';
import { editorMetadata } from '../test/gamePrimitiveFixtures.js';

const vuetifyStubs = createVuetifyStubs([
    'VAlert', 'VBtn', 'VCard', 'VCardActions', 'VCardText', 'VCardTitle', 'VCol', 'VDivider',
    'VIcon', 'VNumberInput', 'VProgressLinear', 'VRow', 'VSelect', 'VTextField',
]);

function snapshot(overrides = {}) {
    return {
        initialized: true, version: 1, revision: 'revision-1', editor_metadata: editorMetadata, definition_counts: {}, definitions: [],
        anchor_count: 0, primitive_count: 0, anchors: [], active_characters: ['Alice', 'Bob', 'Carol'],
        relationships: [], drafts: [], current_adventure: null, recent_ledger: [], ...overrides,
    };
}

function relationship(source, target, value) {
    return {
        anchor: canonicalAnchorRef('relationship', `${source}->${target}`), source, target,
        summary: `${source} relationship summary.`,
        dimensions: [{ id: 'trust', label: 'Trust', min: -5, max: 5, value, render_policy: 'summary' }],
    };
}

describe('WorldStateManagerCharacterRelationships', () => {
    it('separates directions deterministically and offers only other active characters', async () => {
        const websocket = createWebsocketHarness();
        const wrapper = mount(CharacterRelationships, {
            props: { characterName: 'Alice' },
            global: {
                provide: websocket.provide,
                stubs: { ...vuetifyStubs, WorldStateManagerRelationshipDetail: true },
            },
        });
        const requestId = websocket.outgoing[0].request_id;
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives', request_id: requestId,
            data: snapshot({ relationships: [
                relationship('Carol', 'Alice', 0), relationship('Alice', 'Carol', 1),
                relationship('Bob', 'Alice', -1), relationship('Alice', 'Bob', 2),
            ] }),
        });
        await flushPromises();

        expect(wrapper.vm.outgoing.map((item) => item.anchor)).toEqual([
            'relationship:Alice->Bob', 'relationship:Alice->Carol',
        ]);
        expect(wrapper.vm.incoming.map((item) => item.anchor)).toEqual([
            'relationship:Bob->Alice', 'relationship:Carol->Alice',
        ]);
        expect(wrapper.vm.availableCharacters).toEqual(['Bob', 'Carol']);
        expect(wrapper.get('[data-testid="outgoing-relationships"]').text()).toContain('Alice → Other');
        expect(wrapper.get('[data-testid="incoming-relationships"]').text()).toContain('Other → Alice');
        wrapper.unmount();
        expect(websocket.handlerCount).toBe(0);
        expect(websocket.websocket.removeEventListener).toHaveBeenCalledTimes(2);
    });

    it('creates an explicitly selected incoming edge and rejects malformed snapshots', async () => {
        const websocket = createWebsocketHarness();
        const wrapper = mount(CharacterRelationships, {
            props: { characterName: 'Alice' },
            global: { provide: websocket.provide, stubs: { ...vuetifyStubs, WorldStateManagerRelationshipDetail: true } },
        });
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives', request_id: websocket.outgoing[0].request_id,
            data: snapshot(),
        });
        await flushPromises();
        wrapper.vm.createDirection = 'incoming';
        wrapper.vm.otherCharacter = 'Bob';
        wrapper.vm.beginCreate();
        expect(wrapper.vm.newRelationship).toMatchObject({
            anchor: 'relationship:Bob->Alice', source: 'Bob', target: 'Alice', dimensions: [],
        });

        expect(() => wrapper.vm.applySnapshot({ ...snapshot(), unexpected: true })).toThrow();
        expect(wrapper.vm.error).toContain('Malformed relationship snapshot');
        wrapper.unmount();
    });
});

describe('WorldStateManagerRelationshipDetail', () => {
    function mountEditor() {
        const websocket = createWebsocketHarness();
        const edge = relationship('Alice', 'Bob', 1);
        const wrapper = mount(RelationshipDetail, {
            props: { relationship: edge, revision: 'revision-1', renderPolicies: editorMetadata.render_policies },
            global: { provide: websocket.provide, stubs: vuetifyStubs },
        });
        return { edge, websocket, wrapper };
    }

    function deletionPreview(request, target, validation = { ok: true, errors: [], warnings: [] }) {
        return {
            type: 'world_state_manager', action: 'game_primitive_deletion_preview', request_id: request.request_id,
            revision: 'revision-1', target,
            draft: { id: 'preview', status: 'draft', created_by: 'ui', definitions: {}, anchors: {}, replacements: { definitions: [], anchors: [], primitives: [] }, deletions: { definitions: [], anchors: [], primitives: [] }, validation },
            validation, candidate: { before: { definitions: 0, anchors: 2, primitives: 2 }, after: { definitions: 0, anchors: 2, primitives: 1 }, candidate_revision: 'candidate' },
        };
    }

    it('authors a dimension through one atomic relationship mutation', async () => {
        const { edge, websocket, wrapper } = mountEditor();
        const promise = wrapper.vm.saveDimension({ ...edge.dimensions[0], label: 'Earned trust' });
        expect(websocket.outgoing[0]).toMatchObject({
            action: 'author_game_primitive_relationship', expected_revision: 'revision-1',
            source: 'Alice', target: 'Bob',
            change: { operation: 'upsert_dimension', dimension: { id: 'trust', label: 'Earned trust' } },
        });
        const committed = snapshot({ revision: 'revision-5', relationships: [edge] });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives', request_id: websocket.outgoing[0].request_id, data: committed });
        await promise;
        expect(websocket.outgoing).toHaveLength(1);
        expect(wrapper.emitted('changed')[0][0]).toEqual(committed);
        expect(wrapper.vm.busy).toBe(false);
        wrapper.unmount();
    });

    it('uses the canonical effect action and previews directional deletion', async () => {
        const { edge, websocket, wrapper } = mountEditor();
        wrapper.vm.adjustments.trust = -2;
        const promise = wrapper.vm.adjust(edge.dimensions[0]);
        expect(websocket.outgoing[0]).toMatchObject({
            action: 'adjust_game_primitive', expected_revision: 'revision-1',
            ref: 'relationship:Alice->Bob/meters/trust', delta: -2,
        });
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives', request_id: websocket.outgoing[0].request_id,
            data: snapshot({ relationships: [edge] }),
        });
        await promise;

        const preview = wrapper.vm.previewDeleteAnchor();
        expect(websocket.outgoing[1]).toMatchObject({
            action: 'preview_delete_game_primitive_anchor', expected_revision: 'revision-1', anchor: edge.anchor,
        });
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitive_deletion_preview', request_id: websocket.outgoing[1].request_id,
            revision: 'revision-1', target: { kind: 'anchor', ref: edge.anchor },
            draft: { id: 'preview', status: 'draft', created_by: 'ui', definitions: {}, anchors: {}, replacements: { definitions: [], anchors: [], primitives: [] }, deletions: { definitions: [], anchors: [edge.anchor], primitives: [] }, validation: { ok: true, errors: [], warnings: ['reverse preserved'] } },
            validation: { ok: true, errors: [], warnings: ['reverse preserved'] },
            candidate: { before: { definitions: 0, anchors: 2, primitives: 2 }, after: { definitions: 0, anchors: 1, primitives: 1 }, candidate_revision: 'candidate' },
        });
        await preview;
        await nextTick();
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('Alice → Bob');
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('reverse edge remains unchanged');
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('Anchors 2 -> 1');
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('reverse preserved');
        wrapper.unmount();
    });

    it('previews dimension deletion, cancels without mutation, and confirms atomically', async () => {
        const { edge, websocket, wrapper } = mountEditor();
        const previewPromise = wrapper.vm.previewDeleteDimension(edge.dimensions[0]);
        const previewRequest = websocket.outgoing[0];
        expect(previewRequest).toMatchObject({ action: 'preview_delete_game_primitive', ref: 'relationship:Alice->Bob/meters/trust' });
        websocket.dispatch(deletionPreview(previewRequest, { kind: 'primitive', ref: previewRequest.ref }, { ok: true, errors: [], warnings: ['Reverse edge preserved'] }));
        await previewPromise;
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('Reverse edge preserved');

        wrapper.vm.deletePreview = null;
        await nextTick();
        expect(websocket.outgoing).toHaveLength(1);

        const secondPreview = wrapper.vm.previewDeleteDimension(edge.dimensions[0]);
        websocket.dispatch(deletionPreview(websocket.outgoing[1], { kind: 'primitive', ref: websocket.outgoing[1].ref }));
        await secondPreview;
        const confirmation = wrapper.vm.confirmDelete();
        expect(websocket.outgoing[2]).toMatchObject({
            action: 'author_game_primitive_relationship', source: 'Alice', target: 'Bob',
            change: { operation: 'delete_dimension', dimension_id: 'trust' },
        });
        const reverse = relationship('Bob', 'Alice', 4);
        const committed = snapshot({ revision: 'revision-2', relationships: [reverse] });
        websocket.dispatch({ type: 'world_state_manager', action: 'game_primitives', request_id: websocket.outgoing[2].request_id, data: committed });
        await confirmation;
        expect(wrapper.emitted('changed')[0][0].relationships).toEqual([reverse]);
        expect(wrapper.vm.deletePreview).toBeNull();
        wrapper.unmount();
    });

    it('keeps preview failures and validation errors visible without mutation', async () => {
        const { edge, websocket, wrapper } = mountEditor();
        const failedPreview = wrapper.vm.previewDeleteDimension(edge.dimensions[0]);
        websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives_failed', request_id: websocket.outgoing[0].request_id,
            request_action: 'preview_delete_game_primitive', error: { message: 'Preview unavailable' },
        });
        await expect(failedPreview).rejects.toThrow('Preview unavailable');
        expect(wrapper.get('[data-testid="relationship-error"]').text()).toContain('Preview unavailable');
        expect(wrapper.vm.deletePreview).toBeNull();

        const warningPreview = wrapper.vm.previewDeleteDimension(edge.dimensions[0]);
        const request = websocket.outgoing[1];
        websocket.dispatch(deletionPreview(request, { kind: 'primitive', ref: request.ref }, { ok: false, errors: ['Dangling reference'], warnings: ['Reverse edge preserved'] }));
        await warningPreview;
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('Dangling reference');
        expect(wrapper.get('[data-testid="delete-preview"]').text()).toContain('Reverse edge preserved');
        expect(websocket.outgoing).toHaveLength(2);
        wrapper.unmount();
    });

    it.each([
        {
            name: 'stale authored mutation',
            begin: (wrapper, edge) => wrapper.vm.saveDimension({ ...edge.dimensions[0], label: 'Changed' }),
            fail: (websocket, request) => websocket.dispatch({
                type: 'world_state_manager', action: 'game_primitives_failed', request_id: request.request_id,
                request_action: request.action, error: { message: 'Stale Game Primitives revision: expected revision-2' },
            }),
            error: 'Stale Game Primitives revision',
        },
        {
            name: 'closed socket during runtime mutation',
            begin: (wrapper, edge) => wrapper.vm.adjust(edge.dimensions[0], 2),
            fail: (websocket) => websocket.dispatchSocketEvent('close'),
            error: 'websocket closed',
        },
        {
            name: 'socket error during delete preview',
            begin: (wrapper, edge) => wrapper.vm.previewDeleteDimension(edge.dimensions[0]),
            fail: (websocket) => websocket.dispatchSocketEvent('error'),
            error: 'websocket encountered an error',
        },
    ])('preserves relationship state and cleans up after $name', async ({ begin, fail, error }) => {
        const { edge, websocket, wrapper } = mountEditor();
        const initialDrafts = structuredClone(wrapper.vm.drafts);
        const operation = begin(wrapper, edge);
        const request = websocket.outgoing[0];

        fail(websocket, request);
        await expect(operation).rejects.toThrow(error);
        await nextTick();

        expect(wrapper.get('[data-testid="relationship-error"]').text()).toContain(error);
        expect(wrapper.props('relationship')).toEqual(edge);
        expect(wrapper.vm.drafts).toEqual(initialDrafts);
        expect(wrapper.vm.deletePreview).toBeNull();
        expect(wrapper.vm.busy).toBe(false);
        expect(wrapper.emitted('changed')).toBeUndefined();

        wrapper.unmount();
        expect(websocket.handlerCount).toBe(0);
        expect(websocket.websocket.removeEventListener).toHaveBeenCalledTimes(2);
    });
});
