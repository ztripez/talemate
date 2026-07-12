<template>
    <div class="scalar-field">
        <v-select v-model="valueType" :label="`${label} type`" :items="types" density="compact" />
        <v-select v-if="valueType === 'boolean'" :model-value="String(model)" :label="label" :items="['true', 'false']" density="compact" @update:model-value="model = $event === 'true'" />
        <v-number-input v-else-if="valueType === 'number'" :model-value="typeof model === 'number' ? model : 0" :label="label" density="compact" @update:model-value="model = Number($event)" />
        <v-text-field v-else-if="valueType === 'string'" :model-value="typeof model === 'string' ? model : ''" :label="label" density="compact" @update:model-value="model = String($event)" />
        <span v-else class="null-value">null</span>
    </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

type Scalar = string | number | boolean | null;
const { label = 'Value' } = defineProps<{ label?: string }>();
const model = defineModel<Scalar>({ required: true });
const types = ['string', 'number', 'boolean', 'null'];
const valueType = ref(model.value === null ? 'null' : typeof model.value);

watch(valueType, (type) => {
    if (type === 'null') model.value = null;
    else if (type === 'number') model.value = 0;
    else if (type === 'boolean') model.value = false;
    else model.value = '';
});
</script>

<style scoped>
.scalar-field { display: grid; grid-template-columns: 8rem minmax(10rem, 1fr); gap: .5rem; align-items: start; }
.null-value { padding: .6rem; opacity: .7; }
@media (max-width: 550px) { .scalar-field { grid-template-columns: 1fr; } }
</style>
