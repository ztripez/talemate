<template>
    <v-combobox
        v-model="model"
        :label="label"
        :items="options"
        multiple
        chips
        closable-chips
        density="compact"
        :error-messages="error ? [error] : []"
    />
</template>

<script setup lang="ts">
defineProps<{ label: string; options?: string[]; error?: string }>();
const model = defineModel<string[]>({ required: true });
</script>
