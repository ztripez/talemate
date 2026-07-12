<template>
    <section class="adventure-list">
        <div class="list-heading"><div><h3 class="text-h6">Adventures</h3><div class="text-caption text-medium-emphasis">Authored graphs in deterministic catalog order</div></div><v-btn size="small" color="primary" @click="$emit('create')">New adventure</v-btn></div>
        <v-alert v-if="ordered.length === 0" density="compact" variant="tonal">No authored adventures.</v-alert>
        <v-list v-else lines="two">
            <v-list-item v-for="adventure in ordered" :key="adventure.id" :title="adventure.title" :subtitle="`${Object.keys(adventure.scenes).length} scenes · ${Object.keys(adventure.transitions).length} transitions`" @click="$emit('select', adventure.id)">
                <template #append><code>{{ adventure.id }}</code></template>
            </v-list-item>
        </v-list>
    </section>
</template>

<script setup>
import { computed } from 'vue';
const props = defineProps({ adventures: { type: Array, required: true } });
defineEmits(['create', 'select']);
const ordered = computed(() => [...props.adventures].sort((a, b) => a.id.localeCompare(b.id)));
</script>

<style scoped>
.adventure-list { display: grid; gap: 1rem; }
.list-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
</style>
