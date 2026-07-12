<template>
    <fieldset class="field-group">
        <legend class="text-caption">{{ label }}</legend>
        <div v-for="(entry, index) in entries" :key="index" class="field-row">
            <v-text-field v-model="entry.key" label="Key" density="compact" @update:model-value="publish" />
            <v-select v-model="entry.type" label="Type" :items="['string', 'number', 'boolean', 'null']" density="compact" :disabled="entry.readOnly" @update:model-value="publish" />
            <v-select v-if="entry.type === 'boolean'" v-model="entry.value" label="Value" :items="['true', 'false']" density="compact" @update:model-value="publish" />
            <v-text-field v-else-if="entry.type !== 'null'" v-model="entry.value" label="Value" density="compact" :type="entry.type === 'number' ? 'number' : 'text'" :disabled="entry.readOnly" :error-messages="entry.error ? [entry.error] : []" @update:model-value="publish" />
            <span v-else-if="entry.readOnly" class="read-only">Complex value preserved read-only</span>
            <v-btn icon="mdi-delete" size="small" variant="text" aria-label="Remove value" @click="remove(index)" />
        </div>
        <v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="add">Add value</v-btn>
    </fieldset>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
type Entry = { key: string; value: string; type: string; error: string; readOnly: boolean };

const { label } = defineProps<{ label: string }>();
const model = defineModel<Record<string, JsonValue>>({ required: true });
const entries = ref<Entry[]>(toEntries(model.value));

watch(model, (value) => { entries.value = toEntries(value); }, { deep: true });

function toEntries(value: Record<string, JsonValue>): Entry[] {
    return Object.entries(value).map(([key, item]) => {
        const type = item === null ? 'null' : typeof item;
        const readOnly = !['string', 'number', 'boolean'].includes(type) && item !== null;
        return { key, value: item === null || readOnly ? '' : String(item), type: readOnly ? 'null' : type, error: '', readOnly };
    });
}

function publish(): void {
    const next: Record<string, JsonValue> = {};
    let valid = true;
    for (const entry of entries.value) {
        entry.error = '';
        if (!entry.key.trim()) { entry.error = 'Key is required'; valid = false; continue; }
        if (entry.readOnly) { next[entry.key] = model.value[entry.key]; continue; }
        if (entry.type === 'null') next[entry.key] = null;
        else if (entry.type === 'boolean') next[entry.key] = entry.value === 'true';
        else if (entry.type === 'number') {
            const number = Number(entry.value);
            if (!Number.isFinite(number)) { entry.error = 'Enter a finite number'; valid = false; }
            else next[entry.key] = number;
        } else next[entry.key] = entry.value;
    }
    if (valid) model.value = next;
}

function add(): void { entries.value.push({ key: '', value: '', type: 'string', error: '', readOnly: false }); }
function remove(index: number): void { entries.value.splice(index, 1); publish(); }
</script>

<style scoped>
.field-group { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; padding: 0.75rem; }
.field-row { display: grid; grid-template-columns: minmax(0, 1fr) 8rem minmax(0, 1.4fr) auto; gap: 0.5rem; align-items: start; }
.read-only { padding-top: .5rem; opacity: .75; }
@media (max-width: 650px) { .field-row { grid-template-columns: 1fr auto; } .field-row > :nth-child(2) { grid-column: 1 / -1; grid-row: 2; } }
</style>
