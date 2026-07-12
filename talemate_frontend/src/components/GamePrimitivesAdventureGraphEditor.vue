<template>
  <section class="adventure-editor" data-testid="adventure-graph-editor">
    <div class="editor-heading">
      <div>
        <h3 class="text-h6">Adventure graph</h3>
        <div class="text-caption text-medium-emphasis">
          Scenes and transitions retain displayed order
        </div>
      </div>
      <slot name="actions" />
    </div>
    <div class="field-grid">
      <v-text-field v-model="working.id" label="Adventure ID" /><v-text-field
        v-model="working.title"
        label="Title"
      /><v-select
        v-model="working.start_scene"
        :items="sceneIds"
        label="Start scene"
      />
    </div>
    <v-textarea v-model="working.description" label="Description" />
    <div class="editor-heading">
      <h4 class="text-h6">Story scenes</h4>
      <v-btn size="small" variant="text" @click="addScene">Add scene</v-btn>
    </div>
    <AdventureSceneForm
      v-for="(scene, sceneId, index) in working.scenes"
      :key="sceneId"
      :model-value="scene"
      :anchor-refs="anchorRefs"
      :primitive-refs="primitiveRefs"
      :effect-kinds="editorMetadata.effect_kinds"
      @update:model-value="updateScene(sceneId, $event)"
      ><template #actions
        ><OrderActions
          :first="index === 0"
          :last="index === sceneIds.length - 1"
          @up="moveScene(sceneId, -1)"
          @down="moveScene(sceneId, 1)"
          @remove="removeScene(sceneId)" /></template
    ></AdventureSceneForm>
    <div class="editor-heading">
      <h4 class="text-h6">Transitions</h4>
      <v-btn
        size="small"
        variant="text"
        :disabled="!sceneIds.length"
        @click="addTransition"
        >Add transition</v-btn
      >
    </div>
    <AdventureTransitionForm
      v-for="(transition, transitionId, index) in working.transitions"
      :key="transitionId"
      :model-value="transition"
      :scene-ids="sceneIds"
      :anchor-refs="anchorRefs"
      :primitive-refs="primitiveRefs"
      :condition-kinds="editorMetadata.condition_kinds"
      :effect-kinds="editorMetadata.effect_kinds"
      @update:model-value="updateTransition(transitionId, $event)"
      ><template #actions
        ><OrderActions
          :first="index === 0"
          :last="index === transitionIds.length - 1"
          @up="moveTransition(transitionId, -1)"
          @down="moveTransition(transitionId, 1)"
          @remove="removeTransition(transitionId)" /></template
    ></AdventureTransitionForm>
  </section>
</template>
<script setup lang="ts">
import { computed, defineComponent, h, ref, toRaw, watch } from "vue";
import AdventureSceneForm from "./GamePrimitivesAdventureSceneForm.vue";
import AdventureTransitionForm from "./GamePrimitivesAdventureTransitionForm.vue";
import {
  cloneAdventure,
  moveOrderedRecord,
} from "./gamePrimitivesAdventure.js";
const props = withDefaults(
  defineProps<{
    modelValue: any;
    editorMetadata: any;
    anchorRefs?: string[];
    primitiveRefs?: string[];
  }>(),
  { anchorRefs: () => [], primitiveRefs: () => [] },
);
const emit = defineEmits<{ update: [value: any] }>();
const working = ref(cloneAdventure(props.modelValue));
watch(
  () => props.modelValue,
  (value) => {
    if (JSON.stringify(value) !== JSON.stringify(working.value)) working.value = cloneAdventure(value);
  },
  { deep: false },
);
watch(working, (value) => emit("update", cloneAdventure(toRaw(value))), {
  deep: true,
});
const sceneIds = computed(() => Object.keys(working.value.scenes));
const transitionIds = computed(() => Object.keys(working.value.transitions));
const OrderActions = defineComponent({
  props: { first: Boolean, last: Boolean },
  emits: ["up", "down", "remove"],
  setup(p, { emit: e }) {
    return () =>
      h("div", { class: "order-actions" }, [
        h(
          "button",
          {
            disabled: p.first,
            "aria-label": "Move up",
            onClick: () => e("up"),
          },
          "up",
        ),
        h(
          "button",
          {
            disabled: p.last,
            "aria-label": "Move down",
            onClick: () => e("down"),
          },
          "down",
        ),
        h(
          "button",
          { "aria-label": "Remove", onClick: () => e("remove") },
          "remove",
        ),
      ]);
  },
});
function uniqueId(prefix: string, record: any) {
  let i = Object.keys(record).length + 1;
  while (`${prefix}-${i}` in record) i++;
  return `${prefix}-${i}`;
}
function addScene() {
  const id = uniqueId("scene", working.value.scenes);
  working.value.scenes[id] = {
    id,
    title: "New scene",
    description: null,
    location: null,
    intro: null,
    goals: [],
    local_anchors: [],
    entry_effects: [],
    exit_effects: [],
    render_policy: "prompt",
  };
  if (!working.value.start_scene) working.value.start_scene = id;
}
function updateScene(oldId: string, value: any) {
  working.value.scenes = Object.fromEntries(
    Object.entries(working.value.scenes).map(([id, v]) =>
      id === oldId ? [value.id, value] : [id, v],
    ),
  );
}
function removeScene(id: string) {
  const next = { ...working.value.scenes };
  delete next[id];
  working.value.scenes = next;
}
function moveScene(id: string, n: number) {
  working.value.scenes = moveOrderedRecord(working.value.scenes, id, n);
}
function addTransition() {
  const id = uniqueId("transition", working.value.transitions),
    scene = sceneIds.value[0];
  working.value.transitions[id] = {
    id,
    from_scene: scene,
    to_scene: scene,
    label: "Continue",
    description: null,
    conditions: [],
    carry_anchors: [],
    exit_effects: [],
    entry_effects: [],
    intro: null,
  };
}
function updateTransition(oldId: string, value: any) {
  working.value.transitions = Object.fromEntries(
    Object.entries(working.value.transitions).map(([id, v]) =>
      id === oldId ? [value.id, value] : [id, v],
    ),
  );
}
function removeTransition(id: string) {
  const next = { ...working.value.transitions };
  delete next[id];
  working.value.transitions = next;
}
function moveTransition(id: string, n: number) {
  working.value.transitions = moveOrderedRecord(
    working.value.transitions,
    id,
    n,
  );
}
defineExpose({ moveScene });
</script>
<style scoped>
.adventure-editor {
  display: grid;
  gap: 1rem;
}
.editor-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}
:deep(.order-actions) {
  display: flex;
  gap: 0.35rem;
}
@media (max-width: 760px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
  .editor-heading {
    flex-direction: column;
  }
}
</style>
