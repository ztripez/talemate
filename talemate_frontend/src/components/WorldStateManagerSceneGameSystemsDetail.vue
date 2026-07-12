<template>
    <pre class="detail text-caption">{{ formattedValue }}</pre>
</template>

<script>
/**
 * Formats a JSON-compatible Game Systems value as indented read-only detail.
 *
 * @component WorldStateManagerSceneGameSystemsDetail
 * @prop {Object|Array|string|number|boolean} value Required JSON-compatible value.
 * Object properties and array elements must also be JSON-compatible; `undefined`,
 * functions, symbols, bigint values, and cyclic references are outside the contract.
 * The value is serialized with two-space indentation and is never mutated.
 * @slot None.
 * @inject None.
 * @fires No component events.
 */
export default {
    name: 'WorldStateManagerSceneGameSystemsDetail',
    props: {
        value: { type: [Object, Array, String, Number, Boolean], required: true },
    },
    computed: {
        formattedValue() {
            return JSON.stringify(this.value, null, 2);
        },
    },
};
</script>

<style scoped>
.detail {
    margin: 0;
    padding: 0.875rem;
    overflow: auto;
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 6px;
    background: rgba(var(--v-theme-surface-variant), 0.22);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
</style>
