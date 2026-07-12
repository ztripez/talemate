<template>
    <section>
        <div class="metric-grid">
            <v-card variant="tonal"><v-card-text><div class="text-caption">Schema</div><strong>v{{ snapshot.version }}</strong></v-card-text></v-card>
            <v-card variant="tonal"><v-card-text><div class="text-caption">Definitions</div><strong>{{ snapshot.definitions.length }}</strong></v-card-text></v-card>
            <v-card variant="tonal"><v-card-text><div class="text-caption">Anchors</div><strong>{{ snapshot.anchor_count }}</strong></v-card-text></v-card>
            <v-card variant="tonal"><v-card-text><div class="text-caption">Primitives</div><strong>{{ snapshot.primitive_count }}</strong></v-card-text></v-card>
            <v-card variant="tonal"><v-card-text><div class="text-caption">Drafts</div><strong>{{ snapshot.drafts.length }}</strong></v-card-text></v-card>
            <v-card variant="tonal"><v-card-text><div class="text-caption">Ledger records</div><strong>{{ snapshot.recent_ledger.length }}</strong></v-card-text></v-card>
        </div>
        <div class="mt-4 text-caption text-medium-emphasis">Revision</div>
        <code class="canonical-ref">{{ snapshot.revision }}</code>
        <div class="mt-4 text-caption text-medium-emphasis">Definition catalog</div>
        <div v-if="definitionCounts.length" class="chip-list mt-1">
            <v-chip v-for="entry in definitionCounts" :key="entry[0]" size="small" variant="tonal">{{ entry[0] }}: {{ entry[1] }}</v-chip>
        </div>
        <div v-else class="text-body-2 text-medium-emphasis">No definition kinds.</div>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ snapshot: any }>();
const definitionCounts = computed(() => Object.entries(props.snapshot.definition_counts).sort(([a], [b]) => a.localeCompare(b)));
</script>

<style scoped>
.metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
.chip-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.canonical-ref { overflow-wrap: anywhere; color: rgb(var(--v-theme-secondary)); }
@media (max-width: 700px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
