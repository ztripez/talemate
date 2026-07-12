<template>
    <section class="bundle-editor">
        <div class="field-grid">
            <v-text-field v-model.number="working.bundle_schema_version" label="Bundle schema version" type="number" disabled />
            <v-select v-model="captureSource" label="Capture source" :items="['committed', 'draft']" :disabled="!sceneActive" />
            <v-select v-if="captureSource === 'draft'" v-model="draftId" label="Source / target draft" :items="draftItems" :disabled="!sceneActive" />
        </div>
        <v-alert color="muted" variant="tonal" density="compact">Bundles contain authored definitions and exact anchors only. Runtime, ledger, drafts, and active adventure progress are never stored.</v-alert>
        <v-alert v-if="!editorMetadata" type="info" variant="tonal" density="compact" data-testid="editor-metadata-unavailable">Game Primitive editing is unavailable until canonical editor metadata is received.</v-alert>
        <GamePrimitiveDefinitionsEditor
            v-if="editorMetadata"
            :definitions="working.definitions"
            :editor-metadata="editorMetadata"
            @upsert="upsertDefinition"
            @delete="deleteDefinition"
        />
        <div class="heading"><h3 class="text-h6">Exact authored anchors</h3></div><v-select v-model="selectedAnchorRef" label="Bundle anchor" :items="Object.keys(working.anchors)" clearable />
        <GamePrimitiveAuthoredAnchorEditor v-if="editorMetadata && selectedAnchorRef" :key="selectedAnchorRef" :anchor-ref="selectedAnchorRef" :value="working.anchors[selectedAnchorRef]" :definitions="working.definitions" :editor-metadata="editorMetadata" :anchor-refs="Object.keys(working.anchors)" @update="updateAnchor" />
        <v-btn v-if="selectedAnchorRef" size="small" variant="text" color="error" @click="removeAnchor(selectedAnchorRef)">Remove anchor</v-btn>
        <section class="adventure-definitions" data-testid="adventure-definitions">
            <div class="heading"><div><h3 class="text-h6">Adventures</h3><div class="text-caption text-medium-emphasis">Structured adventure definitions using the shared graph editor.</div></div><v-btn size="small" color="primary" @click="addAdventure">Add adventure</v-btn></div>
            <v-select v-model="selectedAdventureId" label="Adventure definition" :items="adventureItems" clearable />
            <v-alert v-if="adventureItems.length === 0" color="muted" density="compact">No adventures.</v-alert>
            <template v-if="editorMetadata && selectedAdventure">
                <GamePrimitivesAdventureGraphEditor :key="selectedAdventureId" :model-value="selectedAdventure" :editor-metadata="editorMetadata" :anchor-refs="Object.keys(working.anchors)" @update="updateAdventure" />
                <v-btn size="small" variant="text" color="error" @click="deleteAdventure">Delete adventure</v-btn>
            </template>
        </section>
        <v-select v-model="definitionSelection" label="Capture definitions" :items="definitionItems" multiple chips :disabled="!sceneActive" />
        <v-select v-model="anchorSelection" label="Capture anchors" :items="anchorItems" multiple chips :disabled="!sceneActive" />
        <div class="actions">
            <v-btn variant="text" :disabled="busy || !sceneActive" @click="capture">Capture authored content</v-btn>
            <v-btn variant="text" :disabled="busy || !sceneActive || !revision" @click="preview">Preview collisions</v-btn>
            <v-btn color="primary" :disabled="busy || !sceneActive || !revision || collisionCount > 0" @click="apply">Apply to draft</v-btn>
            <v-btn color="secondary" :disabled="busy" @click="save">Save template</v-btn>
        </div>
        <v-alert v-if="error" type="error" density="compact">{{ error }}</v-alert>
        <v-alert v-if="application" :type="collisionCount ? 'warning' : 'success'" density="compact">
            {{ collisionCount ? `${collisionCount} collision(s) block application.` : application.applied ? `Applied to ${application.draft_id}.` : 'No collisions.' }}
            <div v-for="collision in application.collisions" :key="`${collision.location}-${collision.ref}`">{{ collision.location }} {{ collision.resource }}: {{ collision.ref }}</div>
        </v-alert>
    </section>
</template>

<script setup>
import { computed, onMounted, ref, toRaw, watch } from 'vue';
import GamePrimitiveDefinitionsEditor from './gamePrimitives/GamePrimitiveDefinitionsEditor.vue';
import GamePrimitiveAuthoredAnchorEditor from './game-systems/GamePrimitiveAuthoredAnchorEditor.vue';
import GamePrimitivesAdventureGraphEditor from './GamePrimitivesAdventureGraphEditor.vue';
import { cloneAdventure } from './gamePrimitivesAdventure.js';
import { useCorrelatedWebsocketRequest } from './gamePrimitives/useCorrelatedWebsocketRequest.js';
import { authoritativeGamePrimitivesResponseSchema, gamePrimitiveEditorMetadataResponseSchema } from './gamePrimitives/gamePrimitiveResponseContracts.js';
import { bundleApplicationResponseSchema, bundleCaptureResponseSchema, gamePrimitiveBundleSchema } from './gamePrimitives/gamePrimitiveBundleContracts.js';

const props = defineProps({ immutableTemplate: { type: Object, required: true }, sceneActive: Boolean });
const emit = defineEmits(['update']);
const working = ref(structuredClone(toRaw(props.immutableTemplate)));
working.value.bundle_schema_version ??= 1;
working.value.definitions ??= {};
working.value.anchors ??= {};
const captureSource = ref('committed');
const draftId = ref('');
const revision = ref('');
const definitionSelection = ref([]);
const anchorSelection = ref([]);
const selectedAnchorRef = ref('');
const selectedAdventureId = ref('');
const application = ref(null);
const snapshot = ref(null);
const editorMetadata = ref(null);
const transport = useCorrelatedWebsocketRequest();
const { busy, error } = transport;
const adventureItems = computed(() => Object.entries(working.value.definitions.adventures ?? {}).sort(([a], [b]) => a.localeCompare(b)).map(([id, value]) => ({ title:value.title || id, value:id })));
const selectedAdventure = computed(() => working.value.definitions.adventures?.[selectedAdventureId.value] ?? null);
const definitionItems = computed(() => snapshot.value?.definitions.map((item) => ({ title:`${item.kind}/${item.id}`, value:`${item.kind}/${item.id}` })) ?? []);
const anchorItems = computed(() => snapshot.value?.anchors.map((item) => item.ref) ?? []);
const draftItems = computed(() => snapshot.value?.drafts.map((item) => item.id) ?? []);
const collisionCount = computed(() => application.value?.collisions?.length ?? 0);
function upsertDefinition(kind, value) { working.value.definitions[kind] ??= {}; working.value.definitions[kind][value.id] = structuredClone(toRaw(value)); }
function deleteDefinition(kind, id) { delete working.value.definitions[kind]?.[id]; }
function removeAnchor(ref) { delete working.value.anchors[ref]; }
function updateAnchor(ref, value) { working.value = { ...working.value, anchors:{ ...working.value.anchors, [ref]:value } }; }
function addAdventure() { let suffix=1;let id='adventure';while(working.value.definitions.adventures?.[id])id=`adventure-${++suffix}`;working.value.definitions.adventures ??={};working.value.definitions.adventures[id]={id,title:'New adventure',description:null,start_scene:'start',scenes:{start:{id:'start',title:'Start',description:null,location:null,intro:null,goals:[],local_anchors:[],entry_effects:[],exit_effects:[],render_policy:'prompt'}},transitions:{}};selectedAdventureId.value=id; }
function updateAdventure(value) { const previous=selectedAdventureId.value;const adventures={ ...working.value.definitions.adventures };if(value.id!==previous)delete adventures[previous];adventures[value.id]=cloneAdventure(value);working.value={...working.value,definitions:{...working.value.definitions,adventures}};selectedAdventureId.value=value.id; }
function deleteAdventure() { if(!selectedAdventureId.value)return;const adventures={...working.value.definitions.adventures};delete adventures[selectedAdventureId.value];working.value={...working.value,definitions:{...working.value.definitions,adventures}};selectedAdventureId.value=''; }
function save() { emit('update', gamePrimitiveBundleSchema.parse(structuredClone(toRaw(working.value)))); }
async function capture() {
    if (!revision.value) throw new Error('A current Game Primitives revision is required before capture');
    const response = await transport.request({ action:'capture_game_primitive_bundle', responseAction:'game_primitive_bundle_captured', schema:bundleCaptureResponseSchema, fields:{ name:working.value.name, source:captureSource.value, expected_revision:revision.value, draft_id:captureSource.value==='draft'?draftId.value:null, selection:{definitions:definitionSelection.value,anchors:anchorSelection.value} } });
    working.value = {
        ...working.value,
        name: response.data.name,
        bundle_schema_version: response.data.bundle_schema_version,
        definitions: structuredClone(response.data.definitions),
        anchors: structuredClone(response.data.anchors),
    };
    revision.value=response.revision; save();
}
function templateRefPayload() { return { group_uid:working.value.group, template_uid:working.value.uid, expected_revision:revision.value, draft_id:draftId.value||null }; }
async function preview() { application.value = (await transport.request({action:'preview_game_primitive_bundle',responseAction:'game_primitive_bundle_application',schema:bundleApplicationResponseSchema,fields:templateRefPayload()})).data; }
async function apply() { application.value = (await transport.request({action:'apply_game_primitive_bundle',responseAction:'game_primitive_bundle_application',schema:bundleApplicationResponseSchema,fields:templateRefPayload()})).data; revision.value=application.value.revision;draftId.value=application.value.draft_id??'';await loadSnapshot(); }
async function loadSnapshot(){if(!props.sceneActive)return;const response=await transport.request({action:'get_game_primitives',responseAction:'game_primitives',schema:authoritativeGamePrimitivesResponseSchema});snapshot.value=response.data;revision.value=response.data.revision;}
async function loadEditorMetadata(){const response=await transport.request({action:'get_game_primitive_editor_metadata',responseAction:'game_primitive_editor_metadata',schema:gamePrimitiveEditorMetadataResponseSchema});editorMetadata.value=response.data;}
watch(()=>props.immutableTemplate,(value)=>{working.value=structuredClone(toRaw(value));application.value=null;definitionSelection.value=[];anchorSelection.value=[];selectedAnchorRef.value='';selectedAdventureId.value='';},{deep:false});
watch(captureSource,(source)=>{if(source==='committed')draftId.value='';});
onMounted(async()=>{await loadEditorMetadata();await loadSnapshot();});
</script>

<style scoped>
.bundle-editor{display:grid;gap:1rem}.field-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem}.heading,.anchor-row,.actions{display:flex;align-items:center;justify-content:space-between;gap:.75rem}.anchor-row>div:first-child{flex:1}code{color:rgb(var(--v-theme-secondary))}@media(max-width:760px){.field-grid{grid-template-columns:1fr}.heading,.anchor-row,.actions{align-items:stretch;flex-direction:column}}
</style>
