<template>
    <section class="catalog" :aria-labelledby="headingId">
        <div class="catalog-heading">
            <div>
                <h3 :id="headingId" class="text-h6">{{ title }}</h3>
                <div v-if="description" class="text-caption text-medium-emphasis">{{ description }}</div>
            </div>
            <v-chip size="small" variant="tonal">{{ items.length }}</v-chip>
        </div>
        <v-alert v-if="items.length === 0" color="muted" density="compact" variant="tonal" class="mt-3">
            {{ emptyMessage }}
        </v-alert>
        <div v-else class="catalog-items mt-3">
            <slot v-for="item in items" :key="itemKey(item)" name="item" :item="item" />
        </div>
    </section>
</template>

<script>
/**
 * Renders a labelled, keyed catalog section for one Game Systems collection.
 *
 * @component WorldStateManagerSceneGameSystemsCatalog
 * @prop {string} title Required visible heading; also normalized into the heading
 * element ID used by `aria-labelledby`.
 * @prop {string} [description=''] Optional explanatory text below the heading.
 * @prop {Array<unknown>} items Required ordered values to render. An empty array
 * displays `emptyMessage` instead of invoking the item slot.
 * @prop {string} emptyMessage Required message displayed for an empty collection.
 * @prop {(item: unknown) => string|number} itemKey Required stable-key function.
 * Keys must be unique within `items` and stable across renders.
 * @slot item Renders once per item and receives `{ item }`, where `item` is the
 * unchanged array value. The slot should produce one catalog entry root.
 * @inject None.
 * @fires No component events.
 */
export default {
    name: 'WorldStateManagerSceneGameSystemsCatalog',
    props: {
        title: { type: String, required: true },
        description: { type: String, default: '' },
        items: { type: Array, required: true },
        emptyMessage: { type: String, required: true },
        itemKey: { type: Function, required: true },
    },
    computed: {
        headingId() {
            return `game-systems-${this.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
        },
    },
};
</script>

<style scoped>
.catalog {
    min-width: 0;
}

.catalog-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
}

.catalog-items {
    display: grid;
    gap: 0.75rem;
}
</style>
