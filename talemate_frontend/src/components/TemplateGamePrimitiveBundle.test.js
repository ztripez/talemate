import { flushPromises, mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { describe, expect, it } from 'vitest';

import { createVuetifyStubs, createWebsocketHarness } from '../test/websocketHarness.js';
import { editorMetadata } from '../test/gamePrimitiveFixtures.js';
import TemplateGamePrimitiveBundle from './TemplateGamePrimitiveBundle.vue';
import {
    bundleApplicationResponseSchema,
    bundleCaptureResponseSchema,
    gamePrimitiveBundleSchema,
} from './gamePrimitives/gamePrimitiveBundleContracts.js';

const emptyDefinitions = () => ({ decks:{}, roll_tables:{}, meters:{}, clocks:{}, relationship_models:{}, modifiers:{}, attribute_sources:{}, adventures:{} });
const bundle = (uid = 'bundle-1') => ({
    name:'Core', template_type:'game_primitive_bundle', instructions:null, group:'group-1', favorite:false,
    uid, priority:1, bundle_schema_version:1, definitions:emptyDefinitions(), anchors:{},
});

function mountEditor(value = bundle(), metadata = editorMetadata) {
    const websocket = createWebsocketHarness();
    const wrapper = mount(TemplateGamePrimitiveBundle, {
        props:{ immutableTemplate:value, sceneActive:false },
        global:{ provide:websocket.provide, stubs:createVuetifyStubs(['VAlert','VBtn','VCard','VCardText','VChip','VSelect','VTextField']) },
    });
    if (metadata) {
        const request = websocket.outgoing.shift();
        websocket.dispatch({
            type:'world_state_manager', action:'game_primitive_editor_metadata',
            request_id:request.request_id, data:metadata,
        });
    }
    return { wrapper, websocket };
}

const snapshot = (revision = 'revision-1', overrides = {}) => ({
    initialized:true, version:1, revision, editor_metadata:editorMetadata,
    definition_counts:{}, definitions:[], anchor_count:0, primitive_count:0, anchors:[],
    active_characters:[], relationships:[], drafts:[], current_adventure:null, recent_ledger:[],
    ...overrides,
});

async function answer(websocket, request, message) {
    websocket.dispatch({ type:'world_state_manager', request_id:request.request_id, ...message });
    await flushPromises();
}

describe('Game Primitive bundle contracts', () => {
    it('accepts the complete bundle and rejects extras and malformed typed instances', () => {
        expect(gamePrimitiveBundleSchema.parse(bundle())).toEqual(bundle());
        expect(() => gamePrimitiveBundleSchema.parse({ ...bundle(), runtime:{} })).toThrow();
        const malformed = bundle();
        malformed.anchors['character:Ada'] = { tags:[], meta:{}, primitives:{ ...Object.fromEntries(['meters','clocks','decks','roll_tables','attributes','modifiers'].map((kind) => [kind, {}])), meters:{ health:{ id:'health', label:null, min:0, max:10, value:'bad', render_policy:'hidden' } } } };
        expect(() => gamePrimitiveBundleSchema.parse(malformed)).toThrow();
    });

    it('requires exact capture and application envelopes', () => {
        expect(() => bundleCaptureResponseSchema.parse({ type:'world_state_manager', action:'game_primitive_bundle_captured', request_id:'r', revision:'v', data:{ ...bundle(), drafts:{} } })).toThrow();
        const response={ type:'world_state_manager', action:'game_primitive_bundle_application', request_id:'r', data:{ applied:false, draft_id:null, revision:'v', definition_count:1, anchor_count:0, collisions:[] } };
        expect(bundleApplicationResponseSchema.parse(response)).toEqual(response);
        expect(() => bundleApplicationResponseSchema.parse({ ...response, unexpected:true })).toThrow();
    });
});

describe('TemplateGamePrimitiveBundle', () => {
    it('requests metadata without a scene and keeps editors unavailable until it arrives', async () => {
        const {wrapper,websocket}=mountEditor(bundle(), null);
        const request=websocket.outgoing[0];
        expect(request).toMatchObject({type:'world_state_manager',action:'get_game_primitive_editor_metadata'});
        expect(wrapper.get('[data-testid="editor-metadata-unavailable"]').text()).toContain('unavailable');
        expect(wrapper.findComponent({name:'GamePrimitiveDefinitionsEditor'}).exists()).toBe(false);
        await answer(websocket,request,{action:'game_primitive_editor_metadata',data:editorMetadata});
        expect(wrapper.find('[data-testid="editor-metadata-unavailable"]').exists()).toBe(false);
        expect(wrapper.findComponent({name:'GamePrimitiveDefinitionsEditor'}).exists()).toBe(true);
        wrapper.unmount();
    });

    it('detaches edits and resets working state when template selection changes', async () => {
        const first=bundle('first'); first.definitions.relationship_models={zeta:{b:2,a:1}};
        const second={ ...bundle('second'), name:'Second' };
        const { wrapper }=mountEditor(first);
        wrapper.vm.working.name='Detached';
        expect(first.name).toBe('Core');
        await wrapper.setProps({ immutableTemplate:second });
        await nextTick();
        expect(wrapper.vm.working.uid).toBe('second');
        expect(wrapper.vm.working.name).toBe('Second');
        expect(wrapper.vm.application).toBeNull();
        expect(wrapper.vm.selectedAdventureId).toBe('');
        expect(first.definitions.relationship_models.zeta).toEqual({b:2,a:1});
        wrapper.unmount();
    });

    it('selects, adds, edits, and deletes multiple adventures without first-item behavior', async () => {
        const value=bundle();
        const adventure=(id,title)=>({id,title,description:null,start_scene:'start',scenes:{start:{id:'start',title:'Start',description:null,location:null,intro:null,goals:[],local_anchors:[],entry_effects:[],exit_effects:[],render_policy:'prompt'}},transitions:{}});
        value.definitions.adventures={first:adventure('first','First'),second:adventure('second','Second')};
        const {wrapper}=mountEditor(value);await flushPromises();
        expect(wrapper.vm.selectedAdventure).toBeNull();
        wrapper.vm.selectedAdventureId='second';await nextTick();
        expect(wrapper.vm.selectedAdventure.title).toBe('Second');
        wrapper.vm.updateAdventure({...wrapper.vm.selectedAdventure,id:'renamed',title:'Edited'});await nextTick();
        expect(Object.keys(wrapper.vm.working.definitions.adventures).sort()).toEqual(['first','renamed']);
        wrapper.vm.addAdventure();await nextTick();
        expect(wrapper.vm.selectedAdventureId).toBe('adventure');
        wrapper.vm.deleteAdventure();await nextTick();
        expect(Object.keys(wrapper.vm.working.definitions.adventures).sort()).toEqual(['first','renamed']);
        expect(value.definitions.adventures.second.title).toBe('Second');wrapper.unmount();
    });

    it('shows every generic collection and preserves capture-only definitions on save', async () => {
        const value=bundle();
        value.definitions.relationship_models={trust:{dimensions:['trust'],label:'Trust'}};
        value.definitions.attribute_sources={mood:{value:'calm',source:'literal'}};
        const {wrapper}=mountEditor(value);await flushPromises();
        for(const kind of ['decks','roll_tables','meters','clocks','relationship_models','modifiers','attribute_sources']) expect(wrapper.find(`[data-testid="definition-collection-${kind}"]`).exists()).toBe(true);
        expect(wrapper.text()).toContain('Capture-only, read-only definitions');
        expect(wrapper.text()).toContain('relationship_models/trust');
        expect(wrapper.text()).toContain('attribute_sources/mood');
        expect(wrapper.text()).toContain('"dimensions": [');
        wrapper.vm.save();
        expect(wrapper.emitted('update')[0][0].definitions.relationship_models).toEqual(value.definitions.relationship_models);
        expect(wrapper.emitted('update')[0][0].definitions.attribute_sources).toEqual(value.definitions.attribute_sources);
        expect(value.definitions.attribute_sources.mood.value).toBe('calm');wrapper.unmount();
    });

    it('blocks apply when preview reports collisions', async () => {
        const { wrapper }=mountEditor();
        wrapper.vm.application={ applied:false, draft_id:null, revision:'v', definition_count:1, anchor_count:0, collisions:[{resource:'definition',ref:'meters/focus',location:'committed'}] };
        await nextTick();
        expect(wrapper.vm.collisionCount).toBe(1);
        const apply=wrapper.findAllComponents({ name:'VBtnTestStub' }).find((button) => button.text().includes('Apply to draft'));
        expect(apply.attributes('disabled')).toBe('true');
        wrapper.unmount();
    });

    it('sends exact committed and draft capture payloads and saves detached results', async () => {
        const original=bundle(); const { wrapper, websocket }=mountEditor(original);
        wrapper.vm.snapshot=snapshot();wrapper.vm.revision='revision-1';
        wrapper.vm.definitionSelection=['meters/focus'];wrapper.vm.anchorSelection=['scene:main'];
        const committedPromise=wrapper.vm.capture();await nextTick();
        const committed=websocket.outgoing[0];
        expect(committed).toEqual({type:'world_state_manager',action:'capture_game_primitive_bundle',request_id:committed.request_id,name:'Core',source:'committed',expected_revision:'revision-1',draft_id:null,selection:{definitions:['meters/focus'],anchors:['scene:main']}});
        const captured={...bundle(),name:'Captured'};
        await answer(websocket,committed,{action:'game_primitive_bundle_captured',revision:'revision-1',data:captured});await committedPromise;
        expect(wrapper.emitted('update')[0][0]).toEqual(captured);
        expect(original.name).toBe('Core');

        wrapper.vm.captureSource='draft';wrapper.vm.draftId='source';await nextTick();
        const draftPromise=wrapper.vm.capture();await nextTick();const draft=websocket.outgoing[1];
        expect(draft).toMatchObject({action:'capture_game_primitive_bundle',source:'draft',draft_id:'source',expected_revision:'revision-1'});
        await answer(websocket,draft,{action:'game_primitive_bundle_captured',revision:'revision-2',data:captured});await draftPromise;
        expect(wrapper.vm.revision).toBe('revision-2');wrapper.unmount();
    });

    it('reports malformed capture and stale/send failures without mutating the template', async () => {
        const original=bundle();const {wrapper,websocket}=mountEditor(original);
        wrapper.vm.snapshot=snapshot();wrapper.vm.revision='revision-1';
        const malformedPromise=wrapper.vm.capture();const malformedAssertion=expect(malformedPromise).rejects.toThrow('Malformed capture_game_primitive_bundle response');await nextTick();const malformed=websocket.outgoing[0];
        await answer(websocket,malformed,{action:'game_primitive_bundle_captured',revision:'revision-1',data:{...bundle(),bundle_schema_version:2}});
        await malformedAssertion;
        expect(wrapper.vm.working).toEqual(original);

        const stalePromise=wrapper.vm.preview();const staleAssertion=expect(stalePromise).rejects.toThrow('Stale');await nextTick();const stale=websocket.outgoing[1];
        await answer(websocket,stale,{action:'game_primitives_failed',request_action:'preview_game_primitive_bundle',error:{message:'Stale Game Primitives revision'}});
        await staleAssertion;expect(wrapper.vm.error).toContain('Stale');
        websocket.websocket.send.mockImplementationOnce(()=>{throw new Error('send failed')});
        await expect(wrapper.vm.preview()).rejects.toThrow('send failed');
        expect(wrapper.vm.working).toEqual(original);wrapper.unmount();
    });

    it('previews collision details, blocks apply, then applies and refreshes revision/draft', async () => {
        const {wrapper,websocket}=mountEditor();
        wrapper.vm.snapshot=snapshot();wrapper.vm.revision='revision-1';
        const previewPromise=wrapper.vm.preview();await nextTick();const preview=websocket.outgoing[0];
        const collision={resource:'anchor',ref:'scene:main',location:'draft'};
        await answer(websocket,preview,{action:'game_primitive_bundle_application',data:{applied:false,draft_id:null,revision:'revision-1',definition_count:0,anchor_count:1,collisions:[collision]}});await previewPromise;
        expect(wrapper.text()).toContain('draft anchor: scene:main');
        expect(wrapper.findAllComponents({name:'VBtnTestStub'}).find((button)=>button.text().includes('Apply to draft')).attributes('disabled')).toBe('true');

        await wrapper.setProps({sceneActive:true});wrapper.vm.application=null;const applyPromise=wrapper.vm.apply();await nextTick();const apply=websocket.outgoing[1];
        expect(apply).toMatchObject({action:'apply_game_primitive_bundle',group_uid:'group-1',template_uid:'bundle-1',expected_revision:'revision-1',draft_id:null});
        await answer(websocket,apply,{action:'game_primitive_bundle_application',data:{applied:true,draft_id:'draft-new',revision:'revision-2',definition_count:1,anchor_count:0,collisions:[]}});await flushPromises();
        const reload=websocket.outgoing[2];await answer(websocket,reload,{action:'game_primitives',data:snapshot('revision-2',{drafts:[{id:'draft-new',status:'draft',created_by:'template',definition_counts:{},anchor_count:0,primitive_count:0,validation:{ok:true,errors:[],warnings:[]}}]})});await applyPromise;
        expect(wrapper.vm.draftId).toBe('draft-new');expect(wrapper.vm.revision).toBe('revision-2');expect(wrapper.text()).toContain('Applied to draft-new');wrapper.unmount();
    });
});
