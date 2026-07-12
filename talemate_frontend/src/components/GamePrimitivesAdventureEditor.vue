<template>
  <section>
    <v-alert v-if="requestError" type="error">{{ requestError }}</v-alert
    ><v-alert
      v-for="error in currentValidation.errors"
      :key="error"
      type="error"
      >{{ error }}</v-alert
    >
    <GamePrimitivesAdventureGraphEditor
      ref="graph"
      :model-value="working"
      :editor-metadata="editorMetadata"
      :anchor-refs="anchorRefs"
      :primitive-refs="primitiveRefs"
      @update="working = $event"
      ><template #actions
        ><div>
          <v-btn variant="text" :disabled="busy" @click="saveDraft"
            >Save to draft</v-btn
          ><v-btn variant="text" :disabled="busy" @click="validateDraft"
            >Validate</v-btn
          ><v-btn
            color="primary"
            :disabled="busy || !currentValidation.ok"
            @click="commitDraft"
            >Commit</v-btn
          >
        </div></template
      ></GamePrimitivesAdventureGraphEditor
    >
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import GamePrimitivesAdventureGraphEditor from "./GamePrimitivesAdventureGraphEditor.vue";
import { cloneAdventure } from "./gamePrimitivesAdventure.js";
import { useGamePrimitiveDraftLifecycle } from "./gamePrimitives/useGamePrimitiveDraftLifecycle.js";
const props = withDefaults(
  defineProps<{
    modelValue: any;
    draft: any;
    draftId: string;
    revision: string;
    editorMetadata: any;
    anchorRefs?: string[];
    primitiveRefs?: string[];
  }>(),
  { anchorRefs: () => [], primitiveRefs: () => [] },
);
const emit = defineEmits<{
  "update:modelValue": [value: any];
  saved: [value: any];
  snapshot: [value: any];
}>();
const lifecycle = useGamePrimitiveDraftLifecycle({
  initialRevision: props.revision,
  initialDraft: props.draft,
  initialDraftId: props.draftId,
  onDraftAdopt: (draft, revision) => emit("saved", { draft, revision }),
});
const {
  busy,
  error: requestError,
  draft: currentDraft,
  revision: currentRevision,
} = lifecycle;
const graph = ref<any>(null);
const working = ref(cloneAdventure(props.modelValue));
const currentValidation = computed(
  () =>
    currentDraft.value?.validation ?? { ok: false, errors: [], warnings: [] },
);
watch(
  () => props.modelValue,
  (value) => {
    if (!busy.value) working.value = cloneAdventure(value);
  },
  { deep: false },
);
watch(
  () => props.draft,
  (value) => (currentDraft.value = value),
  { deep: true },
);
watch(
  () => props.revision,
  (value) => (currentRevision.value = value),
);
function moveScene(id: string, offset: number) {
  graph.value?.moveScene(id, offset);
}
async function saveDraft() {
  await lifecycle.upsertDefinition("adventures", cloneAdventure(working.value));
  emit("update:modelValue", cloneAdventure(working.value));
}
async function validateDraft() {
  await lifecycle.validateDraft();
}
async function commitDraft() {
  emit("snapshot", await lifecycle.commitDraft());
}
</script>
