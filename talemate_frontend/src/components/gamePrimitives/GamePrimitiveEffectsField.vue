<template>
    <fieldset class="field-group">
        <legend class="text-caption">{{ label }}</legend>
        <v-card v-for="(effect, index) in model" :key="index" variant="outlined" class="mb-2">
            <v-card-text class="effect-grid">
                 <v-select v-model="effect.op" label="Operation" :items="effectKinds" density="compact" />
                 <v-select v-model="effect.target" label="Target" :items="targetOptionsFor(effect.op)" density="compact" :error-messages="errorFor(index, 'target')" />
                 <GamePrimitiveScalarValueField v-if="usesScalarValue(effect.op)" v-model="effect.value" label="Value" />
                 <v-combobox v-if="effect.op === 'extend'" v-model="effect.value" label="Values" multiple chips density="compact" />
                <v-number-input v-if="usesBy(effect.op)" v-model="effect.by" label="By" density="compact" />
                <v-btn icon="mdi-delete" size="small" variant="text" aria-label="Remove effect" @click="model.splice(index, 1)" />
            </v-card-text>
        </v-card>
        <v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="add">Add effect</v-btn>
    </fieldset>
</template>

<script setup lang="ts">
import GamePrimitiveScalarValueField from './GamePrimitiveScalarValueField.vue';
type Effect = { op: string; target: string | null; value: unknown; by: number | null; data: Record<string, unknown> };
const { label = 'Effects', primitiveOptions = [], anchorOptions = [], effectKinds = [], errors = {} } = defineProps<{ label?: string; primitiveOptions?: string[]; anchorOptions?: string[]; effectKinds?: string[]; errors?: Record<string, string> }>();
const model = defineModel<Effect[]>({ required: true });

function add(): void { model.value.push({ op: 'set', target: null, value: null, by: null, data: {} }); }
function usesScalarValue(op: string): boolean { return ['set', 'add_tag', 'remove_tag', 'append'].includes(op); }
function usesBy(op: string): boolean { return ['inc', 'dec'].includes(op); }
function targetOptionsFor(op: string): string[] { return ['add_tag', 'remove_tag'].includes(op) ? anchorOptions : primitiveOptions; }
function errorFor(index: number, field: string): string[] { return errors[`effects.${index}.${field}`] ? [errors[`effects.${index}.${field}`]] : []; }
</script>

<style scoped>
.field-group { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; padding: 0.75rem; }
.effect-grid { display: grid; grid-template-columns: 1fr 2fr 2fr auto; gap: 0.5rem; align-items: start; }
@media (max-width: 750px) { .effect-grid { grid-template-columns: 1fr; } }
</style>
