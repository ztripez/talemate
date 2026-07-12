<template>
    <form class="primitive-editor" @submit.prevent="submit">
        <fieldset><legend>Attribute source</legend>
            <label>Label <input v-model="label"></label>
            <label>Source <select v-model="source"><option v-for="item in sources" :key="item">{{ item }}</option></select></label>
            <label>Render policy <select v-model="renderPolicy"><option v-for="policy in renderPolicies" :key="policy">{{ policy }}</option></select></label>
            <template v-if="source === 'literal'"><label>Literal type <select v-model="valueType"><option>string</option><option>number</option><option>boolean</option><option>null</option></select></label><label v-if="valueType !== 'null'">Literal value <input v-if="valueType !== 'boolean'" v-model="valueText" :type="valueType === 'number' ? 'number' : 'text'"><select v-else v-model="valueText"><option value="true">true</option><option value="false">false</option></select></label></template>
            <label v-else>Canonical source ref <input v-model="sourceRef" required></label>
            <GamePrimitiveKeyValueField v-model="options" label="Typed source options" />
            <GamePrimitiveConditionsField v-model="conditions" :primitive-options="primitiveRefs" :anchor-options="anchorRefs" :condition-kinds="conditionKinds" />
            <p v-if="formError" role="alert">{{ formError }}</p><div><button type="submit">Save attribute source</button><button v-if="deletable" type="button" @click="$emit('preview-delete')">Preview deletion</button></div>
        </fieldset>
    </form>
</template>

<script setup>
import { ref, watch } from 'vue';
import GamePrimitiveConditionsField from '../gamePrimitives/GamePrimitiveConditionsField.vue';
import GamePrimitiveKeyValueField from '../gamePrimitives/GamePrimitiveKeyValueField.vue';
const props = defineProps({ value: { type: Object, required: true }, deletable: Boolean, primitiveRefs: { type: Array, default: () => [] }, anchorRefs: { type: Array, default: () => [] }, conditionKinds: { type: Array, default: () => [] }, renderPolicies: { type: Array, default: () => [] } });
const emit = defineEmits(['submit', 'preview-delete']);
const sources = ['literal', 'deck', 'roll_table', 'meter', 'clock', 'relationship', 'modifier', 'state_ref'];
const label = ref(''); const source = ref('literal'); const renderPolicy = ref('hidden'); const sourceRef = ref('');
const valueText = ref(''); const valueType = ref('null'); const options = ref({}); const conditions = ref([]); const formError = ref(null);
watch(() => props.value, (value) => {
    label.value = value.label ?? ''; source.value = value.source; renderPolicy.value = value.render_policy;
    sourceRef.value = value.ref ?? ''; valueType.value = value.value === null || value.value === undefined ? 'null' : typeof value.value;
    valueText.value = valueType.value === 'null' ? '' : String(value.value);
    options.value = JSON.parse(JSON.stringify(value.options ?? {})); conditions.value = JSON.parse(JSON.stringify(value.conditions ?? []));
}, { immediate: true, deep: true });
function submit() {
    try {
        const value = { id: props.value.id, source: source.value, render_policy: renderPolicy.value, options: options.value, conditions: conditions.value, ...(label.value ? { label: label.value } : {}) };
        if (source.value === 'literal') {
            value.value = valueType.value === 'null' ? null : valueType.value === 'number' ? Number(valueText.value) : valueType.value === 'boolean' ? valueText.value === 'true' : valueText.value;
            if (valueType.value === 'number' && !Number.isFinite(value.value)) throw new Error('Literal value must be a finite number');
        } else value.ref = sourceRef.value.trim();
        formError.value = null; emit('submit', { kind: 'attributes', value });
    } catch (error) { formError.value = error instanceof Error ? error.message : String(error); }
}
</script>

<style scoped>
.primitive-editor fieldset { display: grid; gap: .75rem; padding: 1rem; border: 1px solid rgb(var(--v-theme-outline)); border-radius: 8px; }.primitive-editor label { display: grid; gap: .25rem; }
</style>
