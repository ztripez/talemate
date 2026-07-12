<template>
    <form class="primitive-editor" @submit.prevent="submit">
        <fieldset>
            <legend>{{ kind === 'meters' ? 'Meter' : 'Clock' }} authored configuration</legend>
            <GamePrimitiveMeterClockAuthoredFields :kind="kind" :model-value="authored" :render-policies="renderPolicies" @update:model-value="authored = $event" />
            <GamePrimitiveMeterRuntimeControls v-if="showRuntime" :value="value.value" :max="value.max" @adjust="$emit('adjust', $event)" />
            <div><button type="submit">Save authored configuration</button><button v-if="deletable" type="button" @click="$emit('preview-delete')">Preview deletion</button></div>
        </fieldset>
    </form>
</template>

<script setup>
import { ref, watch } from 'vue';
import GamePrimitiveMeterClockAuthoredFields from '../gamePrimitives/GamePrimitiveMeterClockAuthoredFields.vue';
import GamePrimitiveMeterRuntimeControls from '../gamePrimitives/GamePrimitiveMeterRuntimeControls.vue';

const props = defineProps({ kind: { type: String, required: true, validator: (value) => ['meters', 'clocks'].includes(value) }, value: { type: Object, required: true }, renderPolicies: { type: Array, default: () => [] }, deletable: Boolean, showRuntime: { type: Boolean, default: true } });
const emit = defineEmits(['submit', 'adjust', 'preview-delete']);
const authored = ref({ label: null, min: 0, max: 1, render_policy: 'hidden' });
watch(() => props.value, (value) => {
    authored.value = { label: value.label ?? null, min: value.min ?? 0, max: value.max, render_policy: value.render_policy };
}, { immediate: true, deep: true });
function submit() {
    emit('submit', { kind: props.kind, value: {
        id: props.value.id, ...(props.kind === 'meters' ? { min: authored.value.min } : {}),
        max: authored.value.max, value: props.value.value, render_policy: authored.value.render_policy,
        ...(authored.value.label ? { label: authored.value.label } : {}),
    } });
}
</script>

<style scoped>
.primitive-editor fieldset { display: grid; gap: .75rem; padding: 1rem; border: 1px solid rgb(var(--v-theme-outline)); border-radius: 8px; }
.primitive-editor label { display: grid; gap: .25rem; }
</style>
