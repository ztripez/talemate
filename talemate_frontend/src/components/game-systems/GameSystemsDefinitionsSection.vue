<template>
    <section>
        <GamePrimitiveDraftEditorPanel
            :initial-revision="revision"
            :initial-draft-id="draft?.id || ''"
            :editor-metadata="snapshot.editor_metadata"
            :committed-definitions="definitions"
            :primitive-refs="primitiveRefs"
            :anchor-refs="anchorRefs"
            data-testid="definition-draft-editor"
            @state="$emit('draft-state', $event)"
            @snapshot="$emit('snapshot', $event)"
        />
        <v-divider class="my-4" />
        <GameSystemsCatalog title="Definitions" description="Reusable definitions ordered by canonical kind and id." :items="definitions" empty-message="No definitions." :item-key="definitionKey">
            <template #item="{ item }">
                <v-card variant="outlined">
                    <v-card-title class="text-subtitle-1">{{ item.title }}</v-card-title>
                    <v-card-text>
                        <code class="canonical-ref">{{ definitionKey(item) }}</code>
                        <GameSystemsDetail class="mt-3" :value="item.details" />
                    </v-card-text>
                </v-card>
            </template>
        </GameSystemsCatalog>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import GamePrimitiveDraftEditorPanel from '../gamePrimitives/GamePrimitiveDraftEditorPanel.vue';
import GameSystemsCatalog from '../WorldStateManagerSceneGameSystemsCatalog.vue';
import GameSystemsDetail from '../WorldStateManagerSceneGameSystemsDetail.vue';

const props = defineProps<{ snapshot: any; revision: string; draft: any | null }>();
defineEmits<{ 'draft-state': [value: any]; snapshot: [value: any] }>();
const definitionKey = (item: any): string => `${item.kind}/${item.id}`;
const definitions = computed(() => [...props.snapshot.definitions].sort((a, b) => definitionKey(a).localeCompare(definitionKey(b))));
const anchors = computed(() => [...props.snapshot.anchors].sort((a, b) => a.ref.localeCompare(b.ref)));
const anchorRefs = computed(() => anchors.value.map((item) => item.ref));
const primitiveRefs = computed(() => anchors.value.flatMap((item) => item.primitive_refs).sort());
</script>

<style scoped>
.canonical-ref { overflow-wrap: anywhere; color: rgb(var(--v-theme-secondary)); }
</style>
