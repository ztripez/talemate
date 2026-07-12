<template>
    <section class="runtime" aria-label="Runtime state">
        <strong>Runtime state</strong>
        <output>{{ value }} / {{ max }}</output>
        <div>
            <button type="button" :disabled="disabled" @click="$emit('adjust', -1)">-1</button>
            <button type="button" :disabled="disabled" @click="$emit('adjust', 1)">+1</button>
        </div>
    </section>
</template>

<script setup lang="ts">
defineProps<{ value: number; max: number; disabled?: boolean }>();
defineEmits<{ adjust: [delta: number] }>();
</script>

<style scoped>
.runtime { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .75rem; background: rgba(var(--v-theme-primary), .08); }
.runtime div { display: flex; gap: .5rem; }
</style>
