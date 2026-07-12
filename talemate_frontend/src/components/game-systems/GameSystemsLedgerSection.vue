<template>
    <GameSystemsCatalog title="Recent ledger" description="Most recent operation records, oldest to newest." :items="snapshot.recent_ledger" empty-message="No recent ledger records." :item-key="item => item.id">
        <template #item="{ item }">
            <v-card variant="outlined"><v-card-text>
                <div class="item-title"><strong>{{ item.op }}</strong><span class="text-caption text-medium-emphasis">{{ item.id }}</span></div>
                <div v-if="item.ref" class="mt-2"><span class="text-caption">Primitive ref </span><code class="canonical-ref">{{ item.ref }}</code></div>
                <div v-if="item.anchor" class="mt-1"><span class="text-caption">Anchor ref </span><code class="canonical-ref">{{ item.anchor }}</code></div>
                <p v-if="item.message" class="mt-2 mb-0">{{ item.message }}</p>
                <GameSystemsDetail v-if="hasRecordData(item)" class="mt-3" :value="{ input: item.input, output: item.output }" />
            </v-card-text></v-card>
        </template>
    </GameSystemsCatalog>
</template>

<script setup lang="ts">
import GameSystemsCatalog from '../WorldStateManagerSceneGameSystemsCatalog.vue';
import GameSystemsDetail from '../WorldStateManagerSceneGameSystemsDetail.vue';

defineProps<{ snapshot: any }>();
const hasRecordData = (item: any): boolean => Object.keys(item.input).length > 0 || Object.keys(item.output).length > 0;
</script>

<style scoped>
.item-title { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.canonical-ref { overflow-wrap: anywhere; color: rgb(var(--v-theme-secondary)); }
@media (max-width: 700px) { .item-title { align-items: flex-start; flex-direction: column; gap: 0.4rem; } }
</style>
