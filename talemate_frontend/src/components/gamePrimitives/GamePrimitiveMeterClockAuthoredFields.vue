<template>
    <div class="authored-fields">
        <v-text-field :model-value="modelValue.label" label="Label" density="compact" clearable :disabled="disabled" @update:model-value="update('label', $event || null)" />
        <v-number-input v-if="kind === 'meters'" :model-value="modelValue.min" label="Minimum" density="compact" :disabled="disabled" @update:model-value="update('min', $event)" />
        <v-number-input :model-value="modelValue.max" label="Maximum" density="compact" :disabled="disabled" @update:model-value="update('max', $event)" />
        <v-select :model-value="modelValue.render_policy" label="Render policy" :items="renderPolicies" density="compact" :disabled="disabled" @update:model-value="update('render_policy', $event)" />
    </div>
</template>

<script setup lang="ts">
type AuthoredFields = { label?: string | null; min?: number; max: number; render_policy: string };
const props = withDefaults(defineProps<{ kind: 'meters' | 'clocks'; modelValue: AuthoredFields; renderPolicies?: string[]; disabled?: boolean }>(), { renderPolicies: () => [] });
const emit = defineEmits<{ 'update:modelValue': [value: AuthoredFields] }>();
function update(field: string, value: unknown): void { emit('update:modelValue', { ...props.modelValue, [field]: value }); }
</script>

<style scoped>
.authored-fields { display: contents; }
</style>
