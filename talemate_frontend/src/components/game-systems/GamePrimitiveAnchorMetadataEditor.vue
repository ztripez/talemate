<template>
    <form class="primitive-editor" @submit.prevent="submit">
        <fieldset>
            <legend>Anchor metadata</legend>
            <label>Kind <select v-model="kind" :disabled="Boolean(anchorRef)"><option v-for="item in kinds" :key="item">{{ item }}</option></select></label>
            <label>Anchor id <input v-model="anchorId" :disabled="Boolean(anchorRef)" required></label>
            <label>Tags <input v-model="tagsText" placeholder="hero, active"></label>
            <fieldset class="metadata"><legend>Metadata</legend>
                <div v-for="(entry, index) in metadata" :key="index" class="metadata-row">
                    <input v-model="entry.key" aria-label="Metadata key" placeholder="Key">
                    <select v-model="entry.type" aria-label="Metadata type"><option>string</option><option>number</option><option>boolean</option></select>
                    <input v-if="entry.type !== 'boolean'" v-model="entry.value" :type="entry.type === 'number' ? 'number' : 'text'" aria-label="Metadata value">
                    <select v-else v-model="entry.value" aria-label="Metadata value"><option value="true">true</option><option value="false">false</option></select>
                    <button type="button" aria-label="Remove metadata" @click="metadata.splice(index, 1)">Remove</button>
                </div>
                <button type="button" @click="metadata.push({ key: '', type: 'string', value: '' })">Add metadata</button>
                <p v-if="complexMetadata.length" class="hint">Complex metadata is preserved read-only: {{ complexMetadata.join(', ') }}</p>
            </fieldset>
            <p v-if="formError" role="alert">{{ formError }}</p>
            <code v-if="resolvedRef">{{ resolvedRef }}</code>
            <p v-else role="alert">{{ refError }}</p>
            <div><button type="submit">Save metadata</button><button v-if="deletable && resolvedRef" type="button" @click="$emit('preview-delete', resolvedRef)">Preview deletion</button></div>
        </fieldset>
    </form>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { canonicalAnchorRef, parseAnchorRef } from './gamePrimitiveRefs.js';

const props = defineProps({ anchorRef: { type: String, default: '' }, value: { type: Object, default: () => ({ tags: [], meta: {} }) }, anchorKinds: { type: Array, required: true }, deletable: Boolean });
const emit = defineEmits(['submit', 'preview-delete']);
const kinds = computed(() => props.anchorKinds.filter((item) => item !== 'relationship'));
const kind = ref('scene');
const anchorId = ref('main');
const tagsText = ref('');
const metadata = ref([]);
const complexMetadata = ref([]);
const formError = ref(null);
const refError = ref(null);
const resolvedRef = computed(() => {
    try {
        const value = props.anchorRef ? parseAnchorRef(props.anchorRef).ref : canonicalAnchorRef(kind.value, anchorId.value);
        refError.value = null;
        return value;
    } catch (error) {
        refError.value = `Invalid anchor ref: ${error instanceof Error ? error.message : String(error)}`;
        return null;
    }
});

watch(() => props.value, (value) => {
    tagsText.value = (value.tags ?? []).join(', ');
    metadata.value = [];
    complexMetadata.value = [];
    for (const [key, item] of Object.entries(value.meta ?? {})) {
        if (['string', 'number', 'boolean'].includes(typeof item)) metadata.value.push({ key, type: typeof item, value: String(item) });
        else complexMetadata.value.push(key);
    }
}, { immediate: true, deep: true });

function submit() {
    try {
        const meta = { ...(props.value.meta ?? {}) };
        for (const key of Object.keys(meta)) if (!complexMetadata.value.includes(key)) delete meta[key];
        for (const entry of metadata.value) {
            const key = entry.key.trim();
            if (!key) throw new Error('Metadata keys are required');
            meta[key] = entry.type === 'number' ? Number(entry.value) : entry.type === 'boolean' ? entry.value === 'true' : entry.value;
            if (entry.type === 'number' && !Number.isFinite(meta[key])) throw new Error(`Metadata '${key}' must be a finite number`);
        }
        formError.value = null;
        const anchor = props.anchorRef ? parseAnchorRef(props.anchorRef).ref : canonicalAnchorRef(kind.value, anchorId.value);
        emit('submit', { anchor, value: { tags: tagsText.value.split(',').map((item) => item.trim()).filter(Boolean), meta } });
    } catch (error) {
        formError.value = error instanceof Error ? error.message : String(error);
    }
}
</script>

<style scoped>
.primitive-editor fieldset { display: grid; gap: .75rem; padding: 1rem; border: 1px solid rgb(var(--v-theme-outline)); border-radius: 8px; }
.primitive-editor label { display: grid; gap: .25rem; }
.primitive-editor div { display: flex; gap: .5rem; }
.primitive-editor .metadata { display: grid; gap: .5rem; border: 1px solid rgb(var(--v-theme-outline)); padding: .75rem; }
.metadata-row { display: grid !important; grid-template-columns: 1fr 8rem 1fr auto; }
.hint { margin: 0; opacity: .75; }
@media (max-width: 650px) { .metadata-row { grid-template-columns: 1fr; } }
</style>
