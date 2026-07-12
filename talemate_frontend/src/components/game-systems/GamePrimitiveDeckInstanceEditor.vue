<template>
    <form class="primitive-editor" @submit.prevent="submit">
        <fieldset><legend>Deck authored configuration</legend>
            <label>Definition <select v-model="definition" required><option disabled value="">Select a deck</option><option v-for="item in definitions" :key="item.id" :value="item.id">{{ item.title || item.id }}</option></select></label>
            <section class="runtime" aria-label="Read-only deck runtime"><strong>Runtime state (read-only)</strong><GameSystemsDetail :value="runtime" /></section>
            <div><button type="submit">Save deck binding</button><button v-if="deletable" type="button" @click="$emit('preview-delete')">Preview deletion</button></div>
        </fieldset>
    </form>
</template>

<script setup>
import { ref, watch } from 'vue';
import GameSystemsDetail from '../WorldStateManagerSceneGameSystemsDetail.vue';
const props = defineProps({ definitions: { type: Array, required: true }, value: { type: Object, required: true }, deletable: Boolean });
const emit = defineEmits(['submit', 'preview-delete']);
const definition = ref('');
const runtime = ref({});
watch(() => props.value, (value) => { definition.value = value.definition ?? ''; runtime.value = value.runtime ?? {}; }, { immediate: true, deep: true });
function submit() { emit('submit', { kind: 'decks', value: { definition: definition.value, runtime: runtime.value } }); }
</script>

<style scoped>
.primitive-editor fieldset { display: grid; gap: .75rem; padding: 1rem; border: 1px solid rgb(var(--v-theme-outline)); border-radius: 8px; }
.primitive-editor label { display: grid; gap: .25rem; }.runtime { padding: .75rem; background: rgba(var(--v-theme-primary), .08); }.runtime pre { overflow: auto; }
</style>
