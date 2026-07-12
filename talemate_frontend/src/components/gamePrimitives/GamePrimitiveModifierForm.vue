<template>
    <v-card variant="outlined">
        <v-card-title>Modifier</v-card-title>
        <v-card-text class="form-grid">
            <v-text-field v-model="form.id" label="ID" density="compact" :error-messages="fieldError('id')" />
            <v-text-field v-model="form.label" label="Label" density="compact" clearable />
            <v-combobox v-model="form.applies_to" label="Roll table" :items="rollTableOptions" density="compact" :error-messages="fieldError('applies_to')" />
            <v-number-input v-model="form.add" label="Add" density="compact" :error-messages="fieldError('add')" />
            <v-textarea v-model="form.explanation" label="Explanation" density="compact" class="wide" />
            <GamePrimitiveConditionsField v-model="form.when" :primitive-options="primitiveOptions" :anchor-options="anchorOptions" :condition-kinds="conditionKinds" class="wide" />
            <div v-if="errors._form" class="text-error wide">{{ errors._form }}</div>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="$emit('cancel')">Cancel</v-btn><v-btn color="primary" @click="$emit('save', form)">Save</v-btn></v-card-actions>
    </v-card>
</template>

<script setup lang="ts">
import { reactive, toRaw, watch } from 'vue';
import GamePrimitiveConditionsField from './GamePrimitiveConditionsField.vue';
type Modifier = { id: string; label: string | null; explanation: string | null; applies_to: string; when: any[]; add: number };
const props = withDefaults(defineProps<{ value: Modifier; errors?: Record<string, string>; rollTableOptions?: string[]; primitiveOptions?: string[]; anchorOptions?: string[]; conditionKinds?: string[] }>(), { errors: () => ({}), rollTableOptions: () => [], primitiveOptions: () => [], anchorOptions: () => [], conditionKinds: () => [] });
defineEmits<{ save: [value: Modifier]; cancel: [] }>();
const form = reactive<Modifier>(structuredClone(toRaw(props.value)));
watch(() => props.value, (value) => Object.assign(form, structuredClone(toRaw(value))), { deep: true });
function fieldError(field: string): string[] { return props.errors[field] ? [props.errors[field]] : []; }
</script>

<style scoped>
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }.wide { grid-column: 1 / -1; }
@media (max-width: 650px) { .form-grid { grid-template-columns: 1fr; }.wide { grid-column: auto; } }
</style>
