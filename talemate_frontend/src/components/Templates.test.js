import { shallowMount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import Templates from './Templates.vue';
import TemplateGamePrimitiveBundle from './TemplateGamePrimitiveBundle.vue';

const bundle=(uid='one')=>({name:uid,template_type:'game_primitive_bundle',instructions:null,group:'group',favorite:false,uid,priority:1,bundle_schema_version:1,definitions:{decks:{},roll_tables:{},meters:{},clocks:{},relationship_models:{},modifiers:{},attribute_sources:{},adventures:{}},anchors:{}});
const managed=(templates={one:bundle()})=>({managed:{groups:[{uid:'group',name:'Group',author:'QA',description:'',templates}]}});

function mountTemplates(templates=managed()){
    const sent=[];const requestTemplates=vi.fn();
    const wrapper=shallowMount(Templates,{props:{immutableTemplates:templates,sceneActive:true},global:{provide:{getWebsocket:()=>({send:(value)=>sent.push(JSON.parse(value))}),registerMessageHandler:vi.fn(),unregisterMessageHandler:vi.fn(),requestTemplates,toLabel:(value)=>value},stubs:{VForm:{template:'<form><slot /></form>',methods:{validate(){}}}}}});
    return {wrapper,sent,requestTemplates};
}

describe('Templates Game Primitive bundle integration',()=>{
    it('creates, selects, switches, edits, saves, and deletes through shared template forms',async()=>{
        const second=bundle('two');const {wrapper,sent}=mountTemplates(managed({one:bundle(),two:second}));
        wrapper.vm.selectTemplate('group__$CREATE');
        await nextTick();
        expect(wrapper.vm.template).toMatchObject({group:'group',template_type:null,name:''});
        wrapper.vm.template.name='New';wrapper.vm.template.template_type='game_primitive_bundle';wrapper.vm.formValid=true;wrapper.vm.saveTemplate(true);
        expect(sent[0]).toMatchObject({type:'world_state_manager',action:'save_template',template:{name:'New',template_type:'game_primitive_bundle',group:'group'}});

        wrapper.vm.selectTemplate('group__one');await wrapper.vm.$nextTick();
        let editor=wrapper.findComponent(TemplateGamePrimitiveBundle);
        expect(editor.exists()).toBe(true);expect(editor.props()).toMatchObject({immutableTemplate:wrapper.vm.template,sceneActive:true});
        wrapper.vm.selectTemplate('group__two');await wrapper.vm.$nextTick();
        expect(wrapper.vm.template.uid).toBe('two');expect(wrapper.emitted('selection-changed').at(-1)[0].selected).toEqual(['group__two']);
        const edited={...second,name:'Edited'};wrapper.vm.formValid=true;wrapper.vm.applyAndSaveTemplate(edited);
        expect(sent[1]).toEqual({type:'world_state_manager',action:'save_template',template:edited});
        wrapper.vm.removeTemplate();expect(sent[2]).toEqual({type:'world_state_manager',action:'delete_template',template:edited});
        wrapper.vm.handleMessage({type:'world_state_manager',action:'template_deleted',data:{template:edited}});
        expect(wrapper.vm.template).toBeNull();expect(wrapper.vm.selected).toBeNull();wrapper.unmount();
    });

    it('does not mutate immutable global templates while selecting or handling child edits',async()=>{
        const source=managed();const before=structuredClone(source);const {wrapper}=mountTemplates(source);
        wrapper.vm.selectTemplate('group__one');await nextTick();const edited={...wrapper.vm.template,name:'Detached'};
        wrapper.vm.formValid=false;wrapper.vm.applyAndSaveTemplate(edited);
        expect(source).toEqual(before);expect(wrapper.vm.template.name).toBe('Detached');wrapper.unmount();
    });
});
