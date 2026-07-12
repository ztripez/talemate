<template>
    <GameSystemsCatalog title="Relationships" description="Canonical directional relationship anchors. Each direction is an independent edge." :items="relationships" empty-message="No relationships." :item-key="item => item.anchor">
        <template #item="{ item }">
            <RelationshipDetail
                :class="{ 'focused-anchor': focusedAnchor === item.anchor }"
                :relationship="item"
                :revision="snapshot.revision"
                :render-policies="snapshot.editor_metadata.render_policies"
                @changed="$emit('snapshot', $event)"
                @navigate-anchor="$emit('focus-anchor', $event)"
            />
        </template>
    </GameSystemsCatalog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import GameSystemsCatalog from '../WorldStateManagerSceneGameSystemsCatalog.vue';
import RelationshipDetail from '../WorldStateManagerRelationshipDetail.vue';

const props = defineProps<{ snapshot: any; focusedAnchor?: string | null }>();
defineEmits<{ snapshot: [value: any]; 'focus-anchor': [value: string] }>();
const relationships = computed(() => [...props.snapshot.relationships].sort((a, b) => a.anchor.localeCompare(b.anchor)));
</script>

<style scoped>
.focused-anchor { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 2px; }
</style>
