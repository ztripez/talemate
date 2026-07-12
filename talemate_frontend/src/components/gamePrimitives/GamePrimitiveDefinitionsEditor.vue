<template>
  <section class="definition-editor" data-testid="authored-definitions-editor">
    <div class="toolbar">
      <div>
        <h3 class="text-h6">{{ title }}</h3>
        <div v-if="description" class="text-caption text-medium-emphasis">
          {{ description }}
        </div>
      </div>
      <div class="toolbar-actions">
        <v-select
          v-model="newKind"
          label="Definition type"
          :items="kindItems"
          density="compact"
          hide-details
        /><v-btn color="primary" size="small" @click="startAdd">Add</v-btn
        ><slot name="actions" />
      </div>
    </div>
    <v-alert
      v-for="finding in validation.errors"
      :key="`error-${finding}`"
      type="error"
      density="compact"
      >{{ finding }}</v-alert
    ><v-alert
      v-for="finding in validation.warnings"
      :key="`warning-${finding}`"
      type="warning"
      density="compact"
      >{{ finding }}</v-alert
    >
    <component
      :is="activeForm"
      v-if="editing"
      class="mt-3"
      v-bind="formProps"
      :value="editing.value"
      :errors="{}"
      @save="save"
      @cancel="editing = null"
    />
    <div class="catalog mt-3">
      <section v-for="collection in collections" :key="collection.kind" :data-testid="`definition-collection-${collection.kind}`">
        <h4 class="text-subtitle-1">{{ collection.label }}</h4>
        <div v-if="collection.readOnly" class="text-caption text-medium-emphasis">
          Capture-only, read-only definitions. This collection has no canonical structured domain model and is preserved unchanged when the template is saved.
        </div>
        <v-card v-for="item in collection.items" :key="`${item.kind}/${item.id}`" variant="outlined">
          <v-card-text class="definition-row"><div>
            <strong>{{ item.title }}</strong>
            <div><code>{{ item.kind }}/{{ item.id }}</code></div>
            <pre v-if="collection.readOnly" class="captured-content">{{ stableJson(item.details) }}</pre>
          </div>
          <div v-if="!collection.readOnly" class="row-actions">
            <v-btn size="small" variant="text" @click="startEdit(item)">Edit</v-btn>
            <v-btn size="small" variant="text" @click="startDuplicate(item)">Duplicate</v-btn>
            <v-btn size="small" variant="text" color="error" @click="$emit('delete', item.kind, item.id)">Delete</v-btn>
          </div></v-card-text>
        </v-card>
        <v-alert v-if="collection.items.length === 0" color="muted" density="compact">No {{ collection.label.toLowerCase() }}.</v-alert>
      </section>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, toRaw, watch } from "vue";
import GamePrimitiveDeckForm from "./GamePrimitiveDeckForm.vue";
import GamePrimitiveMeterClockForm from "./GamePrimitiveMeterClockForm.vue";
import GamePrimitiveModifierForm from "./GamePrimitiveModifierForm.vue";
import GamePrimitiveRollTableForm from "./GamePrimitiveRollTableForm.vue";
import { emptyDefinition } from "./gamePrimitiveDraftContracts.js";
type Definitions = Record<string, Record<string, any>>;
type Metadata = {
  definition_kinds: string[];
  definition_editor_kinds: string[];
  condition_kinds: string[];
  effect_kinds: string[];
  render_policies?: string[];
};
const props = withDefaults(
  defineProps<{
    definitions: Definitions;
    editorMetadata: Metadata;
    title?: string;
    description?: string;
    validation?: { errors: string[]; warnings: string[] };
    primitiveRefs?: string[];
    anchorRefs?: string[];
  }>(),
  {
    title: "Definitions",
    description: "",
    validation: () => ({ errors: [], warnings: [] }),
    primitiveRefs: () => [],
    anchorRefs: () => [],
  },
);
const emit = defineEmits<{
  upsert: [kind: string, value: any];
  delete: [kind: string, id: string];
}>();
const forms: Record<string, any> = {
  meters: GamePrimitiveMeterClockForm,
  clocks: GamePrimitiveMeterClockForm,
  modifiers: GamePrimitiveModifierForm,
  decks: GamePrimitiveDeckForm,
  roll_tables: GamePrimitiveRollTableForm,
};
const readOnlyKinds = new Set(["relationship_models", "attribute_sources"]);
const supported = computed(() =>
  props.editorMetadata.definition_editor_kinds.filter((kind) => kind in forms),
);
const kindItems = computed(() =>
  supported.value.map((kind) => ({
    title: kind.replaceAll("_", " "),
    value: kind,
  })),
);
const newKind = ref("meters");
const editing = ref<{ kind: string; value: any } | null>(null);
watch(
  supported,
  (kinds) => {
    if (!kinds.includes(newKind.value)) newKind.value = kinds[0] ?? "";
  },
  { immediate: true },
);
const order = computed(
  () =>
    new Map(
      props.editorMetadata.definition_kinds.map((kind, index) => [kind, index]),
    ),
);
const items = computed(() =>
  Object.entries(props.definitions)
    .flatMap(([kind, values]) =>
      kind in forms
        ? Object.entries(values).map(([id, details]) => ({
            kind,
            id,
            details,
            title: String(details.name ?? details.label ?? details.title ?? id),
          }))
        : [],
    )
    .sort(
      (a, b) =>
        (order.value.get(a.kind) ?? 99) - (order.value.get(b.kind) ?? 99) ||
        a.id.localeCompare(b.id),
    ),
);
const collections = computed(() =>
  props.editorMetadata.definition_kinds
    .filter((kind) => kind !== "adventures" && (kind in forms || readOnlyKinds.has(kind)))
    .map((kind) => ({
      kind,
      label: kind.replaceAll("_", " "),
      readOnly: readOnlyKinds.has(kind),
      items: Object.entries(props.definitions[kind] ?? {})
        .map(([id, details]) => ({ kind, id, details, title: String((details as any).name ?? (details as any).label ?? (details as any).title ?? id) }))
        .sort((a, b) => a.id.localeCompare(b.id)),
    })),
);
function stableJson(value: any): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[\n${value.map((item) => stableJson(item)).join(",\n")}\n]`;
  const entries = Object.keys(value).sort().map((key) => `${JSON.stringify(key)}: ${stableJson(value[key])}`);
  return `{\n${entries.join(",\n")}\n}`;
}
const activeForm = computed(() => forms[editing.value?.kind ?? ""]);
const ids = (kind: string) =>
  items.value.filter((item) => item.kind === kind).map((item) => item.id);
const formProps = computed(() => ({
  kind: editing.value?.kind,
  rollTableOptions: ids("roll_tables"),
  modifierOptions: ids("modifiers"),
  primitiveOptions: props.primitiveRefs,
  anchorOptions: props.anchorRefs,
  conditionKinds: props.editorMetadata.condition_kinds,
  effectKinds: props.editorMetadata.effect_kinds,
  renderPolicies: props.editorMetadata.render_policies,
}));
function startAdd() {
  editing.value = {
    kind: newKind.value,
    value: emptyDefinition(newKind.value),
  };
}
function startEdit(item: any) {
  editing.value = {
    kind: item.kind,
    value: structuredClone(toRaw(item.details)),
  };
}
function startDuplicate(item: any) {
  const value = structuredClone(toRaw(item.details));
  const existing = new Set(ids(item.kind));
  let id = `${item.id}-copy`,
    suffix = 2;
  while (existing.has(id)) id = `${item.id}-copy-${suffix++}`;
  value.id = id;
  editing.value = { kind: item.kind, value };
}
function save(value: any) {
  if (!editing.value) return;
  emit("upsert", editing.value.kind, structuredClone(toRaw(value)));
  editing.value = null;
}
function cancel() { editing.value = null; }
</script>
<style scoped>
.toolbar,
.definition-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}
.toolbar-actions,
.row-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.toolbar-actions :deep(.v-select) {
  min-width: 12rem;
}
.catalog {
  display: grid;
  gap: 0.65rem;
}
.catalog > section { display: grid; gap: 0.5rem; }
.captured-content { margin-top: 0.5rem; overflow: auto; white-space: pre-wrap; }
code {
  color: rgb(var(--v-theme-secondary));
}
@media (max-width: 750px) {
  .toolbar,
  .definition-row {
    flex-direction: column;
  }
}
</style>
