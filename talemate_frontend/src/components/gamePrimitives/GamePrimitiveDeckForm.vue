<template>
    <v-card variant="outlined">
        <v-card-title>Deck</v-card-title>
        <v-card-text class="definition-grid">
            <v-text-field v-model="form.id" label="ID" density="compact" :error-messages="fieldError('id')" />
            <v-text-field v-model="form.name" label="Name" density="compact" :error-messages="fieldError('name')" />
            <v-select v-model="form.mode" label="Mode" :items="['sample', 'draw', 'bag', 'physical']" density="compact" />
            <v-select v-model="form.shuffle" label="Shuffle" :items="['seeded', 'random']" density="compact" />
            <v-select v-model="form.reshuffle" label="Reshuffle" :items="['never', 'when_empty']" density="compact" />
            <GamePrimitiveStringListField v-model="form.tags" label="Tags" />
            <GamePrimitiveKeyValueField v-model="form.variables" label="Variables" class="wide" />
            <section class="wide">
                <div class="section-heading"><strong>Cards</strong><v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="addCard">Add card</v-btn></div>
                <v-alert v-if="errors.cards" type="error" density="compact" variant="tonal">{{ errors.cards }}</v-alert>
                <v-card v-for="(card, index) in form.cards" :key="`${index}-${card.id}`" variant="tonal" class="item-card">
                    <v-card-text class="card-grid">
                        <v-text-field v-model="card.id" label="Card ID" density="compact" :error-messages="nestedError(index, 'id')" />
                        <v-text-field v-model="card.label" label="Label" density="compact" :error-messages="nestedError(index, 'label')" />
                        <v-number-input v-model="card.weight" label="Weight" density="compact" :error-messages="nestedError(index, 'weight')" />
                        <v-number-input v-model="card.cooldown_turns" label="Cooldown turns" density="compact" clearable />
                        <v-checkbox v-model="card.unique" label="Unique" density="compact" />
                        <v-textarea v-model="card.text" label="Text" density="compact" class="wide" />
                        <GamePrimitiveStringListField v-model="card.tags" label="Tags" class="wide" />
                        <GamePrimitiveKeyValueField v-model="card.variables" label="Variables" class="wide" />
                        <GamePrimitiveEffectsField v-model="card.effects" :primitive-options="primitiveOptions" :anchor-options="anchorOptions" :effect-kinds="effectKinds" :errors="nestedErrors(index)" class="wide" />
                        <GamePrimitiveConditionsField v-model="card.conditions" :primitive-options="primitiveOptions" :anchor-options="anchorOptions" :condition-kinds="conditionKinds" class="wide" />
                        <div class="item-actions wide">
                            <v-btn size="small" variant="text" :disabled="index === 0" @click="move(index, -1)">Up</v-btn>
                            <v-btn size="small" variant="text" :disabled="index === form.cards.length - 1" @click="move(index, 1)">Down</v-btn>
                            <v-btn size="small" variant="text" @click="duplicateCard(index)">Duplicate</v-btn>
                            <v-btn size="small" color="error" variant="text" @click="form.cards.splice(index, 1)">Delete</v-btn>
                        </div>
                    </v-card-text>
                </v-card>
            </section>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="$emit('cancel')">Cancel</v-btn><v-btn color="primary" @click="$emit('save', form)">Save</v-btn></v-card-actions>
    </v-card>
</template>

<script setup lang="ts">
import { reactive, toRaw, watch } from 'vue';
import GamePrimitiveConditionsField from './GamePrimitiveConditionsField.vue';
import GamePrimitiveEffectsField from './GamePrimitiveEffectsField.vue';
import GamePrimitiveKeyValueField from './GamePrimitiveKeyValueField.vue';
import GamePrimitiveStringListField from './GamePrimitiveStringListField.vue';
type Card = { id: string; label: string; text: string | null; weight: number; tags: string[]; variables: Record<string, any>; effects: any[]; conditions: any[]; cooldown_turns: number | null; unique: boolean };
type Deck = { id: string; name: string; mode: string; shuffle: string; reshuffle: string; cards: Card[]; tags: string[]; variables: Record<string, any> };
const props = withDefaults(defineProps<{ value: Deck; errors?: Record<string, string>; primitiveOptions?: string[]; anchorOptions?: string[]; conditionKinds?: string[]; effectKinds?: string[] }>(), { errors: () => ({}), primitiveOptions: () => [], anchorOptions: () => [], conditionKinds: () => [], effectKinds: () => [] });
defineEmits<{ save: [value: Deck]; cancel: [] }>();
const form = reactive<Deck>(structuredClone(toRaw(props.value)));
watch(() => props.value, (value) => Object.assign(form, structuredClone(toRaw(value))), { deep: true });
function newCard(id = ''): Card { return { id, label: '', text: null, weight: 1, tags: [], variables: {}, effects: [], conditions: [], cooldown_turns: null, unique: false }; }
function addCard(): void { form.cards.push(newCard()); }
function duplicateCard(index: number): void { const copy = structuredClone(toRaw(form.cards[index])); copy.id = `${copy.id}-copy`; form.cards.splice(index + 1, 0, copy); }
function move(index: number, offset: number): void { const [item] = form.cards.splice(index, 1); form.cards.splice(index + offset, 0, item); }
function fieldError(field: string): string[] { return props.errors[field] ? [props.errors[field]] : []; }
function nestedError(index: number, field: string): string[] { const value = props.errors[`cards.${index}.${field}`]; return value ? [value] : []; }
function nestedErrors(index: number): Record<string, string> { return Object.fromEntries(Object.entries(props.errors).filter(([key]) => key.startsWith(`cards.${index}.`)).map(([key, value]) => [key.slice(`cards.${index}.`.length), value])); }
</script>

<style scoped>
.definition-grid,.card-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }.wide { grid-column:1/-1; }.section-heading,.item-actions { display:flex; align-items:center; justify-content:space-between; gap:.5rem; flex-wrap:wrap; }.item-card { margin-top:.75rem; }
@media(max-width:700px){.definition-grid,.card-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
