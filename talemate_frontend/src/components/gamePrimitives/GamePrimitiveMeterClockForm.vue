<template>
    <v-card variant="outlined">
        <v-card-title>{{ kind === 'meters' ? 'Meter' : 'Clock' }}</v-card-title>
        <v-card-text class="form-grid">
            <v-text-field v-model="form.id" label="ID" density="compact" :error-messages="fieldError('id')" />
            <GamePrimitiveMeterClockAuthoredFields :kind="kind" :model-value="form" :render-policies="renderPolicies" @update:model-value="Object.assign(form, $event)" />
            <v-number-input v-model="form.value" label="Value" density="compact" :error-messages="fieldError('value')" />
            <div v-if="errors._form" class="text-error form-error">{{ errors._form }}</div>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="$emit('cancel')">Cancel</v-btn><v-btn color="primary" @click="$emit('save', form)">Save</v-btn></v-card-actions>
    </v-card>
</template>

<script setup lang="ts">
import { reactive, toRaw, watch } from 'vue';
import GamePrimitiveMeterClockAuthoredFields from './GamePrimitiveMeterClockAuthoredFields.vue';
type NumericDefinition = { id: string; label: string | null; min?: number; max: number; value: number; render_policy: string };
const props = withDefaults(defineProps<{ kind: 'meters' | 'clocks'; value: NumericDefinition; errors?: Record<string, string>; renderPolicies?: string[] }>(), { renderPolicies: () => [] });
defineEmits<{ save: [value: NumericDefinition]; cancel: [] }>();
const form = reactive<NumericDefinition>(structuredClone(toRaw(props.value)));
watch(() => props.value, (value) => Object.assign(form, structuredClone(toRaw(value))), { deep: true });
function fieldError(field: string): string[] { return props.errors?.[field] ? [props.errors[field]] : []; }
</script>

<style scoped>
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.form-error { grid-column: 1 / -1; }
@media (max-width: 650px) { .form-grid { grid-template-columns: 1fr; } }
</style>
