<template>
  <section data-testid="authored-anchor-editor">
    <GamePrimitiveAnchorMetadataEditor
      :anchor-ref="anchorRef"
      :value="value"
      :anchor-kinds="editorMetadata.anchor_kinds"
      @submit="saveMetadata"
    />
    <div class="heading">
      <h4>Primitive instances</h4>
      <div class="add">
        <v-select
          v-model="newKind"
          label="Type"
          :items="kindItems"
        /><v-text-field v-model="newId" label="Instance ID" /><v-btn
          :disabled="!newId.trim()"
          @click="add"
          >Add</v-btn
        >
      </div>
    </div>
    <v-select
      v-model="selectedRef"
      label="Instance"
      :items="primitiveRefs"
      clearable
    /><component
      :is="activeEditor"
      v-if="editing"
      :key="selectedRef"
      v-bind="editorProps"
      :value="editing.value"
      :deletable="true"
      @submit="saveInstance"
      @save="saveModifier"
      @preview-delete="removeInstance"
      @cancel="selectedRef = ''"
    />
  </section>
</template>
<script setup lang="ts">
import { computed, ref, toRaw, watch } from "vue";
import GamePrimitiveAnchorMetadataEditor from "./GamePrimitiveAnchorMetadataEditor.vue";
import GamePrimitiveAttributeSourceEditor from "./GamePrimitiveAttributeSourceEditor.vue";
import GamePrimitiveDeckInstanceEditor from "./GamePrimitiveDeckInstanceEditor.vue";
import GamePrimitiveMeterClockEditor from "./GamePrimitiveMeterClockEditor.vue";
import GamePrimitiveRollTableInstanceEditor from "./GamePrimitiveRollTableInstanceEditor.vue";
import GamePrimitiveModifierForm from "../gamePrimitives/GamePrimitiveModifierForm.vue";
import {
  canonicalPrimitiveRef,
  parsePrimitiveRef,
} from "./gamePrimitiveRefs.js";
type Payload = {
  tags: string[];
  meta: Record<string, unknown>;
  primitives: Record<string, Record<string, any>>;
};
const props = defineProps<{
  anchorRef: string;
  value: Payload;
  editorMetadata: any;
  definitions: Record<string, Record<string, any>>;
  anchorRefs?: string[];
}>();
const emit = defineEmits<{ update: [anchorRef: string, value: Payload] }>();
const editors: Record<string, any> = {
  meters: GamePrimitiveMeterClockEditor,
  clocks: GamePrimitiveMeterClockEditor,
  decks: GamePrimitiveDeckInstanceEditor,
  roll_tables: GamePrimitiveRollTableInstanceEditor,
  attributes: GamePrimitiveAttributeSourceEditor,
  modifiers: GamePrimitiveModifierForm,
};
const newKind = ref("meters"),
  newId = ref(""),
  selectedRef = ref("");
watch(
  () => props.anchorRef,
  () => {
    selectedRef.value = "";
    newId.value = "";
  },
);
const kinds = computed(() =>
  [
    ...new Set([
      ...(props.editorMetadata.primitive_editor_kinds ?? []),
      ...(props.editorMetadata.editable_primitive_kinds ?? []),
    ]),
  ].filter((kind) => kind in editors),
);
const kindItems = computed(() =>
  kinds.value.map((kind: string) => ({
    title: kind.replaceAll("_", " "),
    value: kind,
  })),
);
const primitiveRefs = computed(() =>
  Object.entries(props.value.primitives).flatMap(([kind, values]) =>
    Object.keys(values).map((id) =>
      canonicalPrimitiveRef(props.anchorRef, kind, id),
    ),
  ),
);
const editing = computed(() => {
  if (!selectedRef.value) return null;
  const { kind, id } = parsePrimitiveRef(selectedRef.value);
  return { kind, id, value: props.value.primitives[kind]?.[id] };
});
const activeEditor = computed(() => editors[editing.value?.kind ?? ""]);
const editorProps = computed(() => ({
  showRuntime: false,
  kind: editing.value?.kind,
  definitions: Object.entries(
    props.definitions[
      editing.value?.kind === "decks" ? "decks" : "roll_tables"
    ] ?? {},
  ).map(([id, details]) => ({ id, details })),
  rollTableOptions: Object.keys(props.definitions.roll_tables ?? {}),
  primitiveRefs: primitiveRefs.value,
  primitiveOptions: primitiveRefs.value,
  anchorRefs: props.anchorRefs ?? [props.anchorRef],
  anchorOptions: props.anchorRefs ?? [props.anchorRef],
  conditionKinds: props.editorMetadata.condition_kinds,
  renderPolicies: props.editorMetadata.render_policies,
  errors: {},
}));
function output(mutator: (next: Payload) => void) {
  const next = structuredClone(toRaw(props.value));
  mutator(next);
  emit("update", props.anchorRef, next);
}
function saveMetadata(change: any) {
  output((next) => {
    next.tags = change.value.tags;
    next.meta = change.value.meta;
  });
}
function defaults(kind: string, id: string) {
  if (kind === "meters")
    return {
      id,
      label: null,
      min: 0,
      max: 10,
      value: 0,
      render_policy: "summary",
    };
  if (kind === "clocks")
    return { id, label: null, max: 4, value: 0, render_policy: "summary" };
  if (kind === "decks")
    return {
      definition: Object.keys(props.definitions.decks ?? {})[0] ?? "",
      runtime: {
        definition_id: Object.keys(props.definitions.decks ?? {})[0] ?? "",
        mode: "sample",
        draw_pile: [],
        discard: [],
        recent: [],
        cooldowns: {},
        exhausted: [],
        draw_count: 0,
        seed: null,
      },
    };
  if (kind === "roll_tables")
    return {
      definition: Object.keys(props.definitions.roll_tables ?? {})[0] ?? "",
    };
  if (kind === "attributes")
    return {
      id,
      label: null,
      source: "literal",
      value: null,
      ref: null,
      render_policy: "summary",
      options: {},
      conditions: [],
    };
  return {
    id,
    label: null,
    explanation: null,
    applies_to: Object.keys(props.definitions.roll_tables ?? {})[0] ?? "",
    when: [],
    add: 0,
  };
}
function add() {
  const id = newId.value.trim();
  if (!id) return;
  output(
    (next) =>
      ((next.primitives[newKind.value] ??= {})[id] = defaults(
        newKind.value,
        id,
      )),
  );
  selectedRef.value = canonicalPrimitiveRef(props.anchorRef, newKind.value, id);
  newId.value = "";
}
function saveInstance(change: any) {
  if (!editing.value) return;
  output(
    (next) =>
      (next.primitives[editing.value!.kind][editing.value!.id] =
        structuredClone(toRaw(change.value))),
  );
}
function saveModifier(value: any) {
  saveInstance({ value });
}
function removeInstance() {
  if (!editing.value) return;
  output(
    (next) => delete next.primitives[editing.value!.kind][editing.value!.id],
  );
  selectedRef.value = "";
}
</script>
<style scoped>
.heading,
.add {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.add {
  max-width: 35rem;
}
@media (max-width: 760px) {
  .heading,
  .add {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
