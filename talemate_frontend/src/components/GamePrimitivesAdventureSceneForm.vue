<template>
    <v-card variant="outlined">
        <v-card-title class="form-heading"><span>Scene: {{ modelValue.id }}</span><slot name="actions" /></v-card-title>
        <v-card-text class="scene-form">
            <div class="field-grid">
                <v-text-field :model-value="modelValue.id" label="Scene ID" @update:model-value="update('id', $event)" />
                <v-text-field :model-value="modelValue.title" label="Title" @update:model-value="update('title', $event)" />
                <v-select :model-value="modelValue.render_policy" :items="renderPolicies" label="Render policy" @update:model-value="update('render_policy', $event)" />
                <v-text-field :model-value="modelValue.location" label="Location" @update:model-value="update('location', nullable($event))" />
            </div>
            <v-textarea :model-value="modelValue.description" label="Description" @update:model-value="update('description', nullable($event))" />
            <v-textarea :model-value="modelValue.intro" label="Intro text" @update:model-value="update('intro', nullable($event))" />
            <v-combobox :model-value="modelValue.goals" chips multiple label="Goals (ordered)" @update:model-value="update('goals', $event)" />
            <v-combobox :model-value="modelValue.local_anchors" chips multiple label="Local anchors (ordered)" @update:model-value="update('local_anchors', $event)" />
            <GamePrimitiveEffectsField :model-value="modelValue.entry_effects" label="Entry effects (ordered)" :primitive-options="primitiveRefs" :anchor-options="anchorRefs" :effect-kinds="effectKinds" @update:model-value="update('entry_effects', $event)" />
            <GamePrimitiveEffectsField :model-value="modelValue.exit_effects" label="Exit effects (ordered)" :primitive-options="primitiveRefs" :anchor-options="anchorRefs" :effect-kinds="effectKinds" @update:model-value="update('exit_effects', $event)" />
        </v-card-text>
    </v-card>
</template>

<script setup>
import GamePrimitiveEffectsField from './gamePrimitives/GamePrimitiveEffectsField.vue';
const props = defineProps({ modelValue: { type: Object, required: true }, primitiveRefs: { type: Array, default: () => [] }, anchorRefs: { type: Array, default: () => [] }, effectKinds: { type: Array, default: () => [] }, renderPolicies: { type: Array, default: () => [] } });
const emit = defineEmits(['update:modelValue']);
function update(field, value) { emit('update:modelValue', { ...JSON.parse(JSON.stringify(props.modelValue)), [field]: value }); }
function nullable(value) { return value || null; }
</script>

<style scoped>
.scene-form { display: grid; gap: 0.85rem; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.form-heading { display: flex; justify-content: space-between; gap: 1rem; }
@media (max-width: 700px) { .field-grid { grid-template-columns: 1fr; } }
</style>
