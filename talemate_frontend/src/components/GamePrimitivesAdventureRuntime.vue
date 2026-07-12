<template>
    <section class="adventure-runtime">
        <v-alert v-if="error" type="error" density="compact" variant="tonal">{{ error }}</v-alert>
        <template v-if="currentAdventure">
            <div class="runtime-heading"><div><h3 class="text-h6">{{ currentAdventure.title }}</h3><code>{{ currentAdventure.id }}</code></div><v-chip color="primary">{{ currentAdventure.current_story_scene.title }}</v-chip></div>
            <div class="state-grid"><div><span>Visited</span><strong>{{ currentAdventure.state.visited.length }}</strong></div><div><span>Completed</span><strong>{{ currentAdventure.state.completed.length }}</strong></div><div><span>History</span><strong>{{ currentAdventure.state.transition_log.length }}</strong></div></div>
            <div class="runtime-details">
                <section><strong>Visited scene IDs</strong><code v-for="id in currentAdventure.state.visited" :key="`visited-${id}`">{{ id }}</code><span v-if="currentAdventure.state.visited.length === 0">None</span></section>
                <section><strong>Completed scene IDs</strong><code v-for="id in currentAdventure.state.completed" :key="`completed-${id}`">{{ id }}</code><span v-if="currentAdventure.state.completed.length === 0">None</span></section>
            </div>
            <section><strong>Transition history</strong><v-list v-if="currentAdventure.state.transition_log.length" density="compact"><v-list-item v-for="(entry, index) in currentAdventure.state.transition_log" :key="`${entry.transition_id}-${index}`"><code>{{ entry.transition_id }}</code><div class="text-caption">{{ entry.from_scene }} -> {{ entry.to_scene }}<span v-if="entry.carry_anchors.length"> · carried {{ entry.carry_anchors.join(', ') }}</span></div></v-list-item></v-list><span v-else>None</span></section>
            <v-list lines="two">
                <v-list-item v-for="transition in currentAdventure.transitions" :key="transition.id">
                    <div><strong>{{ transition.label }}</strong><div class="text-caption">{{ transition.available ? `To ${transition.to_scene}` : transition.reasons.join('; ') }}</div></div>
                    <template #append><v-btn size="small" :disabled="busy || !transition.available" @click="takeTransition(transition.id)">Take</v-btn></template>
                </v-list-item>
            </v-list>
            <v-alert v-if="lastResult && !lastResult.ok" type="warning" density="compact" variant="tonal">{{ lastResult.error }}</v-alert>
        </template>
        <template v-else>
            <h3 class="text-h6">Activate adventure</h3>
            <v-alert v-if="adventures.length === 0" density="compact" variant="tonal">No adventure definitions are available.</v-alert>
            <v-list v-else><v-list-item v-for="adventure in orderedAdventures" :key="adventure.id"><div><strong>{{ adventure.title }}</strong><div class="text-caption">{{ adventure.id }}</div></div><template #append><v-btn size="small" :disabled="busy" @click="activate(adventure.id)">Activate</v-btn></template></v-list-item></v-list>
        </template>
    </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import { adventureActivationResponseSchema, adventureTransitionResponseSchema } from './gamePrimitives/gamePrimitiveResponseContracts.js';
import { useCorrelatedWebsocketRequest } from './gamePrimitives/useCorrelatedWebsocketRequest.js';
const props = defineProps({ snapshot: { type: Object, required: true }, adventures: { type: Array, required: true } });
const emit = defineEmits(['snapshot']);
const transport = useCorrelatedWebsocketRequest();
const busy = transport.busy; const error = transport.error; const lastResult = ref(null);
const currentAdventure = computed(() => props.snapshot.current_adventure);
const orderedAdventures = computed(() => [...props.adventures].sort((a, b) => a.id.localeCompare(b.id)));
async function request(action, responseAction, schema, field, value) {
    lastResult.value = null;
    const response = await transport.request({
        action, responseAction, schema, fields: { [field]: value },
        onResponse: (responseValue) => { lastResult.value = responseValue.result; emit('snapshot', responseValue.data); },
    });
    return response;
}
function activate(id) { return request('activate_game_primitive_adventure', 'game_primitive_adventure_activation', adventureActivationResponseSchema, 'adventure_id', id); }
function takeTransition(id) {
    const transition = currentAdventure.value?.transitions.find((item) => item.id === id);
    if (!transition?.available) return;
    return request('take_game_primitive_adventure_transition', 'game_primitive_adventure_transition', adventureTransitionResponseSchema, 'transition_id', id);
}
</script>

<style scoped>
.adventure-runtime { display: grid; gap: 1rem; }
.runtime-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.state-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
.state-grid div { display: flex; justify-content: space-between; padding: 0.75rem; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; }
.runtime-details { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }.runtime-details section { display: flex; flex-direction: column; gap: .35rem; }
@media (max-width: 600px) { .state-grid { grid-template-columns: 1fr; } }
</style>
