<template>
    <GameSystemsCatalog title="Drafts" description="Persisted authoring drafts and their latest validation." :items="drafts" empty-message="No drafts." :item-key="item => item.id">
        <template #item="{ item }">
            <v-card variant="outlined"><v-card-text>
                <div class="item-title"><code class="canonical-ref">drafts/{{ item.id }}</code><v-chip size="x-small" :color="item.validation.ok ? 'success' : 'warning'">{{ item.status }}</v-chip></div>
                <div class="text-caption mt-2">Created by {{ item.created_by }} · {{ item.anchor_count }} anchors · {{ item.primitive_count }} primitives</div>
                <v-alert v-for="finding in item.validation.errors" :key="`error-${finding}`" type="error" density="compact" variant="tonal" class="mt-2">{{ finding }}</v-alert>
                <v-alert v-for="finding in item.validation.warnings" :key="`warning-${finding}`" type="warning" density="compact" variant="tonal" class="mt-2">{{ finding }}</v-alert>
                <div v-if="item.validation.errors.length === 0 && item.validation.warnings.length === 0" class="text-body-2 text-medium-emphasis mt-2">No validation findings.</div>
            </v-card-text></v-card>
        </template>
    </GameSystemsCatalog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import GameSystemsCatalog from '../WorldStateManagerSceneGameSystemsCatalog.vue';

const props = defineProps<{ snapshot: any }>();
const drafts = computed(() => [...props.snapshot.drafts].sort((a, b) => a.id.localeCompare(b.id)));
</script>

<style scoped>
.item-title { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.canonical-ref { overflow-wrap: anywhere; color: rgb(var(--v-theme-secondary)); }
@media (max-width: 700px) { .item-title { align-items: flex-start; flex-direction: column; gap: 0.4rem; } }
</style>
