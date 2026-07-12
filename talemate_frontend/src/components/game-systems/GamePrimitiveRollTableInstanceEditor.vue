<template>
    <form class="primitive-editor" @submit.prevent="$emit('submit', { kind: 'roll_tables', value: { definition } })">
        <fieldset><legend>Roll-table instance</legend><label>Definition <select v-model="definition" required><option disabled value="">Select a table</option><option v-for="item in definitions" :key="item.id" :value="item.id">{{ item.title || item.id }}</option></select></label><div><button type="submit">Save table binding</button><button v-if="deletable" type="button" @click="$emit('preview-delete')">Preview deletion</button></div></fieldset>
    </form>
</template>

<script setup>
import { ref, watch } from 'vue';
const props = defineProps({ definitions: { type: Array, required: true }, value: { type: Object, required: true }, deletable: Boolean });
defineEmits(['submit', 'preview-delete']);
const definition = ref('');
watch(() => props.value.definition, (value) => { definition.value = value ?? ''; }, { immediate: true });
</script>

<style scoped>
.primitive-editor fieldset { display: grid; gap: .75rem; padding: 1rem; border: 1px solid rgb(var(--v-theme-outline)); border-radius: 8px; }.primitive-editor label { display: grid; gap: .25rem; }
</style>
