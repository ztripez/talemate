<template>
  <GamePrimitiveDefinitionsEditor
    :definitions="effectiveDefinitions"
    :editor-metadata="editorMetadata"
    title="Draft definitions"
    :description="`Structured editors stage changes only in ${draft.id}.`"
    :validation="draft.validation"
    :primitive-refs="primitiveRefs"
    :anchor-refs="anchorRefs"
    @upsert="(kind, value) => $emit('upsert', kind, value)"
    @delete="(kind, id) => $emit('delete', kind, id)"
    ><template #actions
      ><v-btn size="small" variant="text" @click="$emit('validate')"
        >Validate draft</v-btn
      ></template
    ></GamePrimitiveDefinitionsEditor
  >
</template>
<script setup lang="ts">
import { computed } from "vue";
import GamePrimitiveDefinitionsEditor from "./GamePrimitiveDefinitionsEditor.vue";
type Draft = {
  id: string;
  definitions: Record<string, Record<string, any>>;
  deletions: { definitions: Array<{ kind: string; id: string }> };
  validation: { errors: string[]; warnings: string[] };
};
type Definition = { kind: string; id: string; details: Record<string, any> };
const props = withDefaults(
  defineProps<{
    draft: Draft;
    editorMetadata: any;
    committedDefinitions?: Definition[];
    primitiveRefs?: string[];
    anchorRefs?: string[];
  }>(),
  {
    committedDefinitions: () => [],
    primitiveRefs: () => [],
    anchorRefs: () => [],
  },
);
defineEmits<{
  upsert: [kind: string, value: any];
  delete: [kind: string, id: string];
  validate: [];
}>();
const effectiveDefinitions = computed(() => {
  const result: Record<string, Record<string, any>> = {};
  const deleted = new Set(
    props.draft.deletions.definitions.map((item) => `${item.kind}/${item.id}`),
  );
  for (const item of props.committedDefinitions)
    if (!deleted.has(`${item.kind}/${item.id}`))
      (result[item.kind] ??= {})[item.id] = item.details;
  for (const [kind, values] of Object.entries(props.draft.definitions))
    result[kind] = { ...(result[kind] ?? {}), ...values };
  return result;
});
</script>
