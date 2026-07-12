<template>
    <section>
        <div class="adventure-grid">
            <GamePrimitivesAdventureList :adventures="adventures" @select="selectAdventure" @create="createAdventure" />
            <GamePrimitivesAdventureEditor
                v-if="selectedAdventure && draft"
                :model-value="selectedAdventure"
                :draft="draft"
                :draft-id="draft.id"
                :revision="revision"
                :anchor-refs="anchorRefs"
                :primitive-refs="primitiveRefs"
                :editor-metadata="snapshot.editor_metadata"
                @update:model-value="selectedAdventure = $event"
                @saved="applyAdventureDraft"
                @snapshot="$emit('snapshot', $event)"
            />
            <v-alert v-else-if="!draft" type="info" density="compact" variant="tonal">Select or create a draft in Definitions to edit an adventure.</v-alert>
        </div>
        <v-divider class="my-4" />
        <GamePrimitivesAdventureRuntime :snapshot="snapshot" :adventures="adventures" @snapshot="$emit('snapshot', $event)" />
        <v-divider class="my-4" />
        <div class="text-subtitle-1 mb-2">Active adventure summary</div>
        <v-alert v-if="!snapshot.current_adventure" color="muted" density="compact" variant="tonal">No active adventure.</v-alert>
        <v-card v-else variant="outlined">
            <v-card-title>{{ snapshot.current_adventure.title }}</v-card-title>
            <v-card-text>
                <code class="canonical-ref">adventures/{{ snapshot.current_adventure.id }}</code>
                <p v-if="snapshot.current_adventure.description" class="mt-3">{{ snapshot.current_adventure.description }}</p>
                <v-divider class="my-3" />
                <div class="text-subtitle-1">Current story scene</div>
                <code class="canonical-ref">story_scenes/{{ snapshot.current_adventure.current_story_scene.id }}</code>
                <div class="text-h6 mt-1">{{ snapshot.current_adventure.current_story_scene.title }}</div>
                <p v-if="snapshot.current_adventure.current_story_scene.description">{{ snapshot.current_adventure.current_story_scene.description }}</p>
                <div class="chip-list mt-2">
                    <v-chip v-for="ref in snapshot.current_adventure.current_story_scene.local_anchors" :key="ref" size="small" variant="tonal"><code>{{ ref }}</code></v-chip>
                </div>
                <div class="text-caption mt-3">Visited {{ snapshot.current_adventure.state.visited.length }} · Completed {{ snapshot.current_adventure.state.completed.length }} · Transitions {{ snapshot.current_adventure.transitions.length }}</div>
            </v-card-text>
        </v-card>
    </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import GamePrimitivesAdventureEditor from '../GamePrimitivesAdventureEditor.vue';
import GamePrimitivesAdventureList from '../GamePrimitivesAdventureList.vue';
import GamePrimitivesAdventureRuntime from '../GamePrimitivesAdventureRuntime.vue';

const props = defineProps<{ snapshot: any; revision: string; draft: any | null }>();
const emit = defineEmits<{ 'draft-state': [value: any]; snapshot: [value: any] }>();
const selectedAdventure = ref<any | null>(null);
const definitions = computed(() => [...props.snapshot.definitions].sort((a, b) => `${a.kind}/${a.id}`.localeCompare(`${b.kind}/${b.id}`)));
const anchors = computed(() => [...props.snapshot.anchors].sort((a, b) => a.ref.localeCompare(b.ref)));
const anchorRefs = computed(() => anchors.value.map((item) => item.ref));
const primitiveRefs = computed(() => anchors.value.flatMap((item) => item.primitive_refs).sort());
const adventures = computed(() => {
    const values = new Map(definitions.value.filter((item) => item.kind === 'adventures').map((item) => [item.id, item.details]));
    for (const [id, value] of Object.entries(props.draft?.definitions?.adventures || {})) values.set(id, value);
    return [...values.values()].sort((a: any, b: any) => a.id.localeCompare(b.id));
});

function selectAdventure(id: string): void {
    const adventure = adventures.value.find((item: any) => item.id === id);
    if (adventure) selectedAdventure.value = JSON.parse(JSON.stringify(adventure));
}
function createAdventure(): void {
    selectedAdventure.value = { id: 'new-adventure', title: 'New adventure', description: null, start_scene: '', scenes: {}, transitions: {} };
}
function applyAdventureDraft(value: any): void {
    emit('draft-state', value);
    const adventure = value.draft.definitions?.adventures?.[selectedAdventure.value?.id];
    if (adventure) selectedAdventure.value = adventure;
}
</script>

<style scoped>
.adventure-grid { display: grid; grid-template-columns: minmax(15rem, 0.75fr) minmax(0, 2fr); gap: 1rem; align-items: start; }
.chip-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.canonical-ref { overflow-wrap: anywhere; color: rgb(var(--v-theme-secondary)); }
@media (max-width: 700px) { .adventure-grid { grid-template-columns: 1fr; } }
</style>
