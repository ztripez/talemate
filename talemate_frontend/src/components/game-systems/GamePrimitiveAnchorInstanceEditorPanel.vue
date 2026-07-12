<template>
    <section class="anchor-panel" data-testid="anchor-instance-editor">
        <div class="panel-heading">
            <div><h3 class="text-h6">Anchor and instance editor</h3><div class="text-caption text-medium-emphasis">Authored changes are staged in the selected draft. Runtime state is changed only by explicit controls.</div></div>
            <v-chip v-if="draft" size="small" color="secondary">Draft {{ draft.id }}</v-chip>
        </div>
        <v-alert v-if="!draft" type="info" density="compact" variant="tonal">Select or create a draft in Definitions before editing anchors.</v-alert>
        <v-alert v-if="error" type="error" density="compact" variant="tonal">{{ error }}</v-alert>
        <v-alert v-if="selectionError" type="error" density="compact" variant="tonal" data-testid="selection-error">{{ selectionError }}</v-alert>
        <v-alert v-if="stale" type="warning" density="compact" variant="tonal">This draft is stale. Refresh the canonical snapshot before retrying.</v-alert>
        <v-progress-linear v-if="busy" indeterminate color="primary" />
        <v-card v-if="deletionPreview" variant="tonal" data-testid="deletion-preview">
            <v-card-title>Confirm deletion</v-card-title>
            <v-card-text>
                <code>{{ deletionPreview.target.ref }}</code>
                <div class="preview-summary mt-2">Anchors {{ deletionPreview.candidate.before.anchors }} -> {{ deletionPreview.candidate.after.anchors }} · Primitives {{ deletionPreview.candidate.before.primitives }} -> {{ deletionPreview.candidate.after.primitives }}</div>
                <v-alert v-for="finding in deletionPreview.validation.errors" :key="finding" type="error" density="compact" variant="tonal" class="mt-2">{{ finding }}</v-alert>
                <v-alert v-for="finding in deletionPreview.validation.warnings" :key="finding" type="warning" density="compact" variant="tonal" class="mt-2">{{ finding }}</v-alert>
                <div v-if="deletionPreview.validation.errors.length === 0 && deletionPreview.validation.warnings.length === 0" class="mt-2">No validation findings.</div>
            </v-card-text>
            <v-card-actions><v-spacer /><v-btn variant="text" @click="deletionPreview = null">Cancel</v-btn><v-btn color="error" :disabled="busy" @click="confirmDelete">Confirm tombstone</v-btn></v-card-actions>
        </v-card>

        <div class="selector-grid">
            <v-select v-model="selectedAnchorRef" label="Anchor" :items="anchorItems" clearable :disabled="!draft || busy" />
            <v-btn :disabled="!draft || busy" variant="text" prepend-icon="mdi-plus" @click="startNewAnchor">New anchor</v-btn>
        </div>
        <GamePrimitiveAnchorMetadataEditor v-if="draft && !selectedAnchorRef" anchor-ref="" :value="{tags:[],meta:{},primitives:{}}" :anchor-kinds="editorMetadata.anchor_kinds" @submit="saveAnchor" />
        <GamePrimitiveAuthoredAnchorEditor v-if="draft && selectedAnchorRef && activeAnchor" :key="selectedAnchorRef" :anchor-ref="selectedAnchorRef" :value="activeAnchor" :definitions="definitionRecords" :editor-metadata="editorMetadata" :anchor-refs="anchorItems.map(item => item.value)" @update="saveAuthoredAnchor" />
        <div v-if="draft" class="acceptance-actions">
            <v-btn variant="text" :disabled="busy || Boolean(selectionError)" @click="validateDraft">Validate</v-btn>
            <v-btn color="primary" :disabled="busy || Boolean(selectionError) || !draft.validation?.ok" @click="commitDraft">Commit</v-btn>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import GamePrimitiveAuthoredAnchorEditor from './GamePrimitiveAuthoredAnchorEditor.vue';
import GamePrimitiveAnchorMetadataEditor from './GamePrimitiveAnchorMetadataEditor.vue';
import GamePrimitiveAttributeSourceEditor from './GamePrimitiveAttributeSourceEditor.vue';
import GamePrimitiveDeckInstanceEditor from './GamePrimitiveDeckInstanceEditor.vue';
import GamePrimitiveMeterClockEditor from './GamePrimitiveMeterClockEditor.vue';
import GamePrimitiveRollTableInstanceEditor from './GamePrimitiveRollTableInstanceEditor.vue';
import { canonicalPrimitiveRef, parseAnchorRef, parsePrimitiveRef } from './gamePrimitiveRefs.js';
import { useGamePrimitiveDraft } from './useGamePrimitiveDraft.js';

type Definition = { kind:string; id:string; title:string; details:Record<string,any> };
type Anchor = { ref:string; tags:string[]; meta:Record<string,unknown>; primitives:Record<string,Record<string,any>> };
type Draft = { id:string; anchors:Record<string,any>; deletions?:{anchors?:string[];primitives?:string[]} };
const props=defineProps<{revision:string;draft:Draft|null;anchors:Anchor[];definitions:Definition[];editorMetadata:any}>();
const emit=defineEmits<{ state:[value:{draft:Draft;revision:string}]; snapshot:[value:any] }>();
const transport=useGamePrimitiveDraft({revision:props.revision,draft:props.draft});
const {revision,draft,busy,error,stale}=transport;
watch(()=>props.revision,(value)=>{revision.value=value;});
watch(()=>props.draft,(value)=>{draft.value=value;},{deep:true});

const selectedAnchorRef=ref('');
const selectedPrimitiveRef=ref('');
const newKind=ref('meters');
const newId=ref('');
const pendingEditing=ref<any|null>(null);
const deletionPreview=ref<any|null>(null);
const editorComponents:Record<string,any>={meters:GamePrimitiveMeterClockEditor,clocks:GamePrimitiveMeterClockEditor,decks:GamePrimitiveDeckInstanceEditor,roll_tables:GamePrimitiveRollTableInstanceEditor,attributes:GamePrimitiveAttributeSourceEditor};
const kindItems=computed(()=>props.editorMetadata.primitive_editor_kinds.filter((kind:string)=>kind in editorComponents).map((kind:string)=>({title:kind.replaceAll('_',' '),value:kind})));
const committedByRef=computed(()=>new Map(props.anchors.map((item)=>[item.ref,item])));
const effectiveAnchors=computed(()=>{
    const deletedAnchors=new Set(draft.value?.deletions?.anchors??[]);const deletedPrimitives=new Set(draft.value?.deletions?.primitives??[]);
    const values=new Map<string,Anchor>();
    for(const item of props.anchors)if(!deletedAnchors.has(item.ref))values.set(item.ref,JSON.parse(JSON.stringify(item)));
    for(const [anchorRef,value] of Object.entries(draft.value?.anchors??{}))if(!deletedAnchors.has(anchorRef))values.set(anchorRef,{ref:anchorRef,...JSON.parse(JSON.stringify(value))} as Anchor);
    for(const anchor of values.values())for(const [kind,primitives] of Object.entries(anchor.primitives??{}))for(const id of Object.keys(primitives))if(deletedPrimitives.has(canonicalPrimitiveRef(anchor.ref,kind,id)))delete primitives[id];
    return [...values.values()].sort((a,b)=>a.ref.localeCompare(b.ref));
});
const anchorItems=computed(()=>effectiveAnchors.value.map((item)=>({title:item.ref,value:item.ref})));
const activeAnchor=computed(()=>effectiveAnchors.value.find((item)=>item.ref===selectedAnchorRef.value)??null);
const primitiveItems=computed(()=>activeAnchor.value?Object.entries(activeAnchor.value.primitives??{}).flatMap(([kind,values])=>Object.keys(values).map((id)=>canonicalPrimitiveRef(selectedAnchorRef.value,kind,id))).sort():[]);
const selectionError=computed(()=>{
    if(!selectedAnchorRef.value)return null;
    try{parseAnchorRef(selectedAnchorRef.value);}catch(reason){return reason instanceof Error?`Invalid selected anchor: ${reason.message}`:'Invalid selected anchor';}
    if(!activeAnchor.value)return `Selected anchor no longer exists: ${selectedAnchorRef.value}`;
    if(!selectedPrimitiveRef.value)return null;
    try{const parsed=parsePrimitiveRef(selectedPrimitiveRef.value);if(parsed.anchor!==selectedAnchorRef.value)return `Selected primitive does not belong to ${selectedAnchorRef.value}`;}
    catch(reason){return reason instanceof Error?`Invalid selected primitive: ${reason.message}`:'Invalid selected primitive';}
    if(!primitiveItems.value.includes(selectedPrimitiveRef.value)&&pendingEditing.value?.ref!==selectedPrimitiveRef.value)return `Selected primitive no longer exists: ${selectedPrimitiveRef.value}`;
    return null;
});
const definitionsByKind=(kind:string)=>props.definitions.filter((item)=>item.kind===kind);
const definitionRecords=computed(()=>{const result:Record<string,Record<string,any>>={};for(const item of props.definitions)(result[item.kind]??={})[item.id]=item.details;return result;});
const editing=computed(()=>{
    if(pendingEditing.value?.ref===selectedPrimitiveRef.value)return pendingEditing.value;
    if(!selectedPrimitiveRef.value)return null;
    const {kind,id}=parsePrimitiveRef(selectedPrimitiveRef.value);
    const value=activeAnchor.value?.primitives?.[kind]?.[id];if(!value)return null;
    return {ref:selectedPrimitiveRef.value,kind,value,committed:Boolean(committedByRef.value.get(selectedAnchorRef.value)?.primitives?.[kind]?.[id]),staged:Boolean(draft.value?.anchors?.[selectedAnchorRef.value]?.primitives?.[kind]?.[id])};
});
const activeEditor=computed(()=>editorComponents[editing.value?.kind??'']);
const activeEditorProps=computed(()=>({kind:editing.value?.kind,definitions:definitionsByKind(editing.value?.kind==='decks'?'decks':'roll_tables'),primitiveRefs:primitiveItems.value,anchorRefs:anchorItems.value.map((item)=>item.value),conditionKinds:props.editorMetadata.condition_kinds,renderPolicies:props.editorMetadata.render_policies}));

async function run(operation:()=>Promise<any>):Promise<any>{
    const result=await operation();if(draft.value)emit('state',{draft:draft.value,revision:revision.value!});return result;
}
function requireValidSelection():void{if(selectionError.value)throw new Error(selectionError.value);}
function startNewAnchor():void{selectedAnchorRef.value='';selectedPrimitiveRef.value='';pendingEditing.value=null;}
async function saveAnchor(change:{anchor:string;value:any}):Promise<void>{requireValidSelection();await run(()=>transport.upsertAnchor(change.anchor,change.value));selectedAnchorRef.value=change.anchor;}
async function saveAuthoredAnchor(anchor:string,value:any):Promise<void>{await saveAnchor({anchor,value});}
async function deleteAnchor(anchor:string):Promise<void>{requireValidSelection();deletionPreview.value=await transport.previewDeleteAnchor(anchor);}
function startAdd():void{
    requireValidSelection();
    const id=newId.value.trim();if(!id)return;const refValue=canonicalPrimitiveRef(selectedAnchorRef.value,newKind.value,id);
    const definition=definitionsByKind(newKind.value)[0];
    const defaults:any={meters:{id,label:null,min:0,max:10,value:0,render_policy:'summary'},clocks:{id,label:null,max:4,value:0,render_policy:'summary'},roll_tables:{definition:definition?.id??''},attributes:{id,label:null,source:'literal',value:null,render_policy:'summary',options:{},conditions:[]}};
    if(newKind.value==='decks') defaults.decks=deckValue(definition,refValue);
    if(!defaults[newKind.value] || (['decks','roll_tables'].includes(newKind.value)&&!definition)){error.value=`Create a ${newKind.value.replace('_',' ')} definition first`;return;}
    pendingEditing.value={ref:refValue,kind:newKind.value,value:defaults[newKind.value],committed:false,staged:false};
    selectedPrimitiveRef.value=refValue;newId.value='';
}
function deckValue(definition:Definition|undefined,refValue:string):any{
    if(!definition)return null;const mode=definition.details.mode??'sample';const cards=(definition.details.cards??[]).map((card:any)=>card.id);
    return {definition:definition.id,runtime:{definition_id:definition.id,mode,draw_pile:['draw','physical'].includes(mode)?cards:[],discard:[],recent:[],cooldowns:{},exhausted:[],draw_count:0,seed:refValue}};
}
async function savePrimitive(change:{kind:string;value:any}):Promise<void>{
    requireValidSelection();if(!editing.value)throw new Error('Selected primitive is unavailable');let value=change.value;
    if(change.kind==='decks'&&value.definition!==value.runtime?.definition_id)value=deckValue(definitionsByKind('decks').find((item)=>item.id===value.definition),editing.value.ref);
    await run(()=>transport.upsertPrimitive(editing.value!.ref,{kind:change.kind,value}));pendingEditing.value=null;
}
async function adjustPrimitive(delta:number):Promise<void>{requireValidSelection();if(!editing.value)throw new Error('Selected primitive is unavailable');const snapshot=await run(()=>transport.adjustPrimitive(editing.value.ref,delta));if(snapshot)emit('snapshot',snapshot);}
async function deletePrimitive():Promise<void>{requireValidSelection();if(!editing.value)throw new Error('Selected primitive is unavailable');deletionPreview.value=await transport.previewDeletePrimitive(editing.value.ref);}
async function confirmDelete():Promise<void>{
    if(!deletionPreview.value)return;
    const target=deletionPreview.value.target;
    await run(()=>target.kind==='anchor'?transport.deleteAnchor(target.ref):transport.deletePrimitive(target.ref));
    if(target.kind==='anchor')selectedAnchorRef.value='';else selectedPrimitiveRef.value='';
    deletionPreview.value=null;
}
async function validateDraft():Promise<void>{await run(transport.validate);}
async function commitDraft():Promise<void>{const snapshot=await transport.commit();emit('snapshot',snapshot);}
</script>

<style scoped>
.anchor-panel{display:grid;gap:1rem;min-width:0}.panel-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem}.selector-grid{display:grid;grid-template-columns:minmax(12rem,1fr) auto;gap:.75rem;align-items:start}.add-controls{display:grid;grid-template-columns:10rem 12rem auto;gap:.5rem;align-items:start}.acceptance-actions{display:flex;justify-content:flex-end;gap:.5rem}.preview-summary{overflow-wrap:anywhere}@media(max-width:760px){.panel-heading,.selector-grid{grid-template-columns:1fr;flex-direction:column}.add-controls{grid-template-columns:1fr;width:100%}}
</style>
