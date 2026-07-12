<template>
    <section class="draft-panel">
        <div class="draft-toolbar">
            <v-select v-model="selectedDraftId" label="Draft" :items="draftItems" density="compact" :disabled="busy" @update:model-value="select" />
            <v-text-field v-model="newDraftId" label="New draft ID (optional)" density="compact" :disabled="busy" />
            <v-btn size="small" color="primary" :disabled="busy || !revision" @click="create">Create draft</v-btn>
            <v-btn size="small" variant="text" :disabled="busy" @click="run(refresh)">Refresh</v-btn>
            <v-btn v-if="draft" size="small" variant="text" color="error" :disabled="busy" @click="removeDraft">Delete draft</v-btn>
        </div>
        <v-progress-linear v-if="busy" indeterminate color="primary" />
        <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mt-2">{{ error }}</v-alert>
        <v-alert v-if="stale" type="warning" density="compact" variant="tonal" class="mt-2" data-testid="stale-draft">
            This draft is stale. Refresh before retrying; no changes were overwritten.
            <v-btn size="small" variant="text" @click="run(refresh)">Refresh now</v-btn>
        </v-alert>
        <GamePrimitiveDefinitionDraftEditor
            v-if="draft"
            class="mt-3"
            :draft="draft"
            :editor-metadata="editorMetadata"
            :committed-definitions="committedDefinitions"
            :primitive-refs="primitiveRefs"
            :anchor-refs="anchorRefs"
            @upsert="saveDefinition"
            @delete="removeDefinition"
            @validate="run(validateDraft)"
        />
        <div v-if="draft" class="acceptance-actions mt-3">
            <v-btn size="small" variant="text" :disabled="busy" @click="run(validateDraft)">Validate</v-btn>
            <v-btn size="small" color="primary" :disabled="busy || !draft.validation.ok" @click="commit">Commit</v-btn>
        </div>
        <v-alert v-else-if="!busy" color="muted" density="compact" variant="tonal" class="mt-3">Select or create a draft to edit definitions.</v-alert>
    </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import GamePrimitiveDefinitionDraftEditor from './GamePrimitiveDefinitionDraftEditor.vue';
import { useGamePrimitiveDraftLifecycle } from './useGamePrimitiveDraftLifecycle.js';

type DefinitionItem={kind:string;id:string;title:string;details:Record<string,unknown>};
const props=withDefaults(defineProps<{initialRevision:string;initialDraftId?:string;editorMetadata:any;committedDefinitions?:DefinitionItem[];primitiveRefs?:string[];anchorRefs?:string[]}>(),{initialDraftId:'',committedDefinitions:()=>[],primitiveRefs:()=>[],anchorRefs:()=>[]});
const emit=defineEmits<{ state:[value:{draft:any|null;revision:string}]; snapshot:[value:any] }>();
const editor=useGamePrimitiveDraftLifecycle({initialRevision:props.initialRevision,initialDraftId:props.initialDraftId});
const {drafts,draft,revision,selectedDraftId,busy,error,stale,refresh,createDraft,deleteDraft,selectDraft,upsertDefinition,deleteDefinition,validateDraft,commitDraft}=editor;
const newDraftId=ref('');
const draftItems=computed(()=>drafts.value.map((item:any)=>({title:item.id,value:item.id})));
watch([draft,revision],()=>emit('state',{draft:draft.value,revision:revision.value}),{deep:true});

async function run(operation:()=>Promise<unknown>):Promise<void>{await operation();}
function select(value:string):void{run(()=>selectDraft(value));}
async function create():Promise<void>{await run(()=>createDraft(newDraftId.value||null));if(!error.value)newDraftId.value='';}
async function removeDraft():Promise<void>{await run(deleteDraft);}
function saveDefinition(kind:string,value:any):void{run(()=>upsertDefinition(kind,value));}
function removeDefinition(kind:string,id:string):void{run(()=>deleteDefinition(kind,id));}
async function commit():Promise<void>{const snapshot=await commitDraft();emit('snapshot',snapshot);}
onMounted(()=>{run(refresh).catch((reason)=>{error.value=reason instanceof Error?reason.message:String(reason);});});
</script>

<style scoped>
.draft-panel{min-width:0}.draft-toolbar{display:grid;grid-template-columns:minmax(12rem,1fr) minmax(12rem,1fr) auto auto auto;gap:.5rem;align-items:start}.acceptance-actions{display:flex;justify-content:flex-end;gap:.5rem}@media(max-width:850px){.draft-toolbar{grid-template-columns:1fr 1fr}}@media(max-width:550px){.draft-toolbar{grid-template-columns:1fr}}
</style>
