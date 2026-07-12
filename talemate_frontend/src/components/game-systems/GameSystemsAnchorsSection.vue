<template>
    <section>
        <GamePrimitiveAnchorInstanceEditorPanel
            :revision="revision"
            :draft="draft"
            :anchors="anchors"
            :definitions="definitions"
            :editor-metadata="snapshot.editor_metadata"
            @state="$emit('draft-state', $event)"
            @snapshot="$emit('snapshot', $event)"
        />
        <v-divider class="my-4" />
        <GameSystemsCatalog title="Anchors" description="Canonical owners and attached primitive counts." :items="anchors" empty-message="No anchors." :item-key="item => item.ref">
            <template #item="{ item }">
                <v-card variant="outlined"><v-card-text>
                    <code class="canonical-ref">{{ item.ref }}</code>
                    <div class="text-caption mt-2">{{ item.primitive_count }} primitives</div>
                    <div class="chip-list mt-2">
                        <v-chip v-for="entry in sortedEntries(item.primitive_counts)" :key="entry[0]" size="x-small" variant="tonal">{{ entry[0] }}: {{ entry[1] }}</v-chip>
                        <v-chip v-for="tag in item.tags" :key="`tag-${tag}`" size="x-small" color="secondary" variant="outlined">#{{ tag }}</v-chip>
                    </div>
                    <div v-if="item.primitive_refs.length" class="primitive-refs mt-3">
                        <code v-for="ref in item.primitive_refs" :key="ref" class="canonical-ref">{{ ref }}</code>
                    </div>
                </v-card-text></v-card>
            </template>
        </GameSystemsCatalog>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import GamePrimitiveAnchorInstanceEditorPanel from './GamePrimitiveAnchorInstanceEditorPanel.vue';
import GameSystemsCatalog from '../WorldStateManagerSceneGameSystemsCatalog.vue';

const props = defineProps<{ snapshot: any; revision: string; draft: any | null }>();
defineEmits<{ 'draft-state': [value: any]; snapshot: [value: any] }>();
const definitionKey = (item: any): string => `${item.kind}/${item.id}`;
const definitions = computed(() => [...props.snapshot.definitions].sort((a, b) => definitionKey(a).localeCompare(definitionKey(b))));
const anchors = computed(() => [...props.snapshot.anchors].sort((a, b) => a.ref.localeCompare(b.ref)));
const sortedEntries = (value: Record<string, number>): [string, number][] => Object.entries(value).sort(([a], [b]) => a.localeCompare(b));
</script>

<style scoped>
.chip-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.primitive-refs { display: grid; gap: 0.35rem; }
.canonical-ref { overflow-wrap: anywhere; color: rgb(var(--v-theme-secondary)); }
</style>
