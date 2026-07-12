<template>
    <fieldset class="field-group">
        <legend class="text-caption">Conditions</legend>
        <v-card v-for="(group, groupIndex) in model" :key="groupIndex" variant="outlined" class="mb-2">
            <v-card-text>
                <div class="group-heading">
                    <v-select v-model="group.operator" label="Group" :items="['and', 'or']" density="compact" />
                    <v-btn icon="mdi-delete" size="small" variant="text" aria-label="Remove condition group" @click="model.splice(groupIndex, 1)" />
                </div>
                <div v-for="(condition, conditionIndex) in group.conditions" :key="conditionIndex" class="condition-grid">
                    <v-select v-model="condition.kind" label="Kind" :items="conditionKinds" density="compact" />
                    <v-text-field v-if="condition.kind === 'path'" v-model="condition.path" label="State path" density="compact" />
                    <v-select v-if="usesPrimitiveRef(condition.kind)" v-model="condition.path" label="Primitive ref" :items="primitiveOptions" clearable density="compact" />
                    <v-select v-if="usesAnchor(condition.kind)" v-model="condition.anchor" label="Anchor" :items="anchorOptions" clearable density="compact" />
                    <v-text-field v-if="usesTag(condition.kind)" v-model="condition.tag" label="Tag" density="compact" />
                    <v-text-field v-if="usesDimension(condition.kind)" v-model="condition.dimension" label="Dimension" density="compact" />
                    <v-select v-if="usesComparison(condition.kind)" v-model="condition.operator" label="Compare" :items="operators" clearable density="compact" />
                    <GamePrimitiveScalarValueField v-if="usesComparison(condition.kind)" v-model="condition.value" label="Expected" />
                    <v-btn icon="mdi-delete" size="small" variant="text" aria-label="Remove condition" @click="group.conditions.splice(conditionIndex, 1)" />
                </div>
                <v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="addCondition(group)">Add condition</v-btn>
            </v-card-text>
        </v-card>
        <v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="addGroup">Add condition group</v-btn>
    </fieldset>
</template>

<script setup lang="ts">
import GamePrimitiveScalarValueField from './GamePrimitiveScalarValueField.vue';
type Condition = { kind: string; path: string | null; operator: string | null; value: unknown; anchor: string | null; tag: string | null; dimension: string | null; data: Record<string, unknown> };
type Group = { operator: 'and' | 'or'; conditions: Condition[] };
const { primitiveOptions = [], anchorOptions = [], conditionKinds = [] } = defineProps<{ primitiveOptions?: string[]; anchorOptions?: string[]; conditionKinds?: string[] }>();
const model = defineModel<Group[]>({ required: true });
const operators = ['==', '!=', '>', '<', '>=', '<=', 'in', 'not_in', 'is_true', 'is_false', 'is_null', 'is_not_null'];

function newCondition(): Condition { return { kind: 'always', path: null, operator: null, value: null, anchor: null, tag: null, dimension: null, data: {} }; }
function addGroup(): void { model.value.push({ operator: 'and', conditions: [newCondition()] }); }
function addCondition(group: Group): void { group.conditions.push(newCondition()); }
function usesPrimitiveRef(kind: string): boolean { return ['primitive', 'meter', 'clock_complete'].includes(kind); }
function usesAnchor(kind: string): boolean { return ['anchor_has_tag', 'anchor_missing_tag', 'meter', 'clock_complete', 'relationship'].includes(kind); }
function usesTag(kind: string): boolean { return ['anchor_has_tag', 'anchor_missing_tag'].includes(kind); }
function usesDimension(kind: string): boolean { return ['meter', 'clock_complete', 'relationship'].includes(kind); }
function usesComparison(kind: string): boolean { return !['always', 'never', 'anchor_has_tag', 'anchor_missing_tag', 'clock_complete'].includes(kind); }
</script>

<style scoped>
.field-group { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; padding: 0.75rem; }
.group-heading { display: flex; gap: 0.5rem; align-items: start; }
.condition-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) auto; gap: 0.5rem; align-items: start; margin-top: 0.5rem; }
@media (max-width: 750px) { .condition-grid { grid-template-columns: 1fr; } }
</style>
