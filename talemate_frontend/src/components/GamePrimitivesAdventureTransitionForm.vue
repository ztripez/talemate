<template>
    <v-card variant="outlined">
        <v-card-title class="form-heading"><span>Transition: {{ modelValue.id }}</span><slot name="actions" /></v-card-title>
        <v-card-text class="transition-form">
            <div class="field-grid">
                <v-text-field :model-value="modelValue.id" label="Transition ID" @update:model-value="update('id', $event)" />
                <v-text-field :model-value="modelValue.label" label="Label" @update:model-value="update('label', $event)" />
                <v-select :model-value="modelValue.from_scene" :items="sceneIds" label="From scene" @update:model-value="update('from_scene', $event)" />
                <v-select :model-value="modelValue.to_scene" :items="sceneIds" label="To scene" @update:model-value="update('to_scene', $event)" />
            </div>
            <v-textarea :model-value="modelValue.description" label="Description" @update:model-value="update('description', $event || null)" />
            <v-textarea :model-value="modelValue.intro" label="Transition intro" @update:model-value="update('intro', $event || null)" />
            <v-combobox :model-value="modelValue.carry_anchors" chips multiple label="Carried anchors (ordered, never pruned)" @update:model-value="update('carry_anchors', $event)" />
            <GamePrimitiveConditionsField :model-value="modelValue.conditions" :primitive-options="primitiveRefs" :anchor-options="anchorRefs" :condition-kinds="conditionKinds" @update:model-value="update('conditions', $event)" />
            <GamePrimitiveEffectsField :model-value="modelValue.exit_effects" label="Exit effects (ordered)" :primitive-options="primitiveRefs" :anchor-options="anchorRefs" :effect-kinds="effectKinds" @update:model-value="update('exit_effects', $event)" />
            <GamePrimitiveEffectsField :model-value="modelValue.entry_effects" label="Entry effects (ordered)" :primitive-options="primitiveRefs" :anchor-options="anchorRefs" :effect-kinds="effectKinds" @update:model-value="update('entry_effects', $event)" />
        </v-card-text>
    </v-card>
</template>

<script setup>
import GamePrimitiveConditionsField from './gamePrimitives/GamePrimitiveConditionsField.vue';
import GamePrimitiveEffectsField from './gamePrimitives/GamePrimitiveEffectsField.vue';
const props = defineProps({ modelValue: { type: Object, required: true }, sceneIds: { type: Array, required: true }, primitiveRefs: { type: Array, default: () => [] }, anchorRefs: { type: Array, default: () => [] }, conditionKinds: { type: Array, default: () => [] }, effectKinds: { type: Array, default: () => [] } });
const emit = defineEmits(['update:modelValue']);
function update(field, value) { emit('update:modelValue', { ...JSON.parse(JSON.stringify(props.modelValue)), [field]: value }); }
</script>

<style scoped>
.transition-form { display: grid; gap: 0.85rem; }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; }
.form-heading { display: flex; justify-content: space-between; gap: 1rem; }
@media (max-width: 700px) { .field-grid { grid-template-columns: 1fr; } }
</style>
