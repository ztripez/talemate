<template>
    <v-card variant="outlined">
        <v-card-title>Roll table</v-card-title>
        <v-card-text class="definition-grid">
            <v-text-field v-model="form.id" label="ID" density="compact" :error-messages="fieldError('id')" />
            <v-text-field v-model="form.name" label="Name" density="compact" :error-messages="fieldError('name')" />
            <v-select v-model="form.mode" label="Mode" :items="['dice', 'weighted']" density="compact" />
            <v-text-field v-if="form.mode === 'dice'" v-model="form.dice" label="Dice" density="compact" :error-messages="fieldError('dice')" />
            <GamePrimitiveStringListField v-model="form.modifiers" label="Modifiers" :options="modifierOptions" class="wide" />
            <section class="wide">
                <div class="section-heading"><strong>Rows</strong><v-btn size="small" variant="text" prepend-icon="mdi-plus" @click="addRow">Add row</v-btn></div>
                <v-alert v-if="errors.rows" type="error" density="compact" variant="tonal">{{ errors.rows }}</v-alert>
                <v-card v-for="(row, index) in form.rows" :key="`${index}-${row.id}`" variant="tonal" class="item-card">
                    <v-card-text class="row-grid">
                        <v-text-field v-model="row.id" label="Row ID" density="compact" :error-messages="nestedError(index, 'id')" />
                        <v-text-field v-model="row.label" label="Label" density="compact" :error-messages="nestedError(index, 'label')" />
                        <v-text-field v-if="form.mode === 'dice'" v-model="row.range" label="Range" density="compact" :error-messages="nestedError(index, 'range')" />
                        <v-number-input v-else v-model="row.weight" label="Weight" density="compact" :error-messages="nestedError(index, 'weight')" />
                        <v-textarea v-model="row.text" label="Text" density="compact" class="wide" />
                        <GamePrimitiveStringListField v-model="row.tags" label="Tags" class="wide" />
                        <GamePrimitiveKeyValueField v-model="row.variables" label="Variables" class="wide" />
                        <GamePrimitiveEffectsField v-model="row.effects" :primitive-options="primitiveOptions" :anchor-options="anchorOptions" :effect-kinds="effectKinds" :errors="nestedErrors(index)" class="wide" />
                        <GamePrimitiveConditionsField v-model="row.conditions" :primitive-options="primitiveOptions" :anchor-options="anchorOptions" :condition-kinds="conditionKinds" class="wide" />
                        <div class="item-actions wide">
                            <v-btn size="small" variant="text" :disabled="index === 0" @click="move(index, -1)">Up</v-btn>
                            <v-btn size="small" variant="text" :disabled="index === form.rows.length - 1" @click="move(index, 1)">Down</v-btn>
                            <v-btn size="small" variant="text" @click="duplicateRow(index)">Duplicate</v-btn>
                            <v-btn size="small" color="error" variant="text" @click="form.rows.splice(index, 1)">Delete</v-btn>
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
type Row = { id:string; label:string; text:string|null; range:string|number|null; weight:number|null; tags:string[]; variables:Record<string,any>; effects:any[]; conditions:any[] };
type Table = { id:string; name:string; mode:'dice'|'weighted'; dice:string|null; rows:Row[]; modifiers:string[] };
const props = withDefaults(defineProps<{ value:Table; errors?:Record<string,string>; modifierOptions?:string[]; primitiveOptions?:string[]; anchorOptions?:string[]; conditionKinds?:string[]; effectKinds?:string[] }>(), { errors:()=>({}), modifierOptions:()=>[], primitiveOptions:()=>[], anchorOptions:()=>[], conditionKinds:()=>[], effectKinds:()=>[] });
defineEmits<{ save:[value:Table]; cancel:[] }>();
const form=reactive<Table>(structuredClone(toRaw(props.value)));
watch(()=>props.value,(value)=>Object.assign(form,structuredClone(toRaw(value))),{deep:true});
function newRow():Row{return{id:'',label:'',text:null,range:form.mode==='dice'?'1':null,weight:form.mode==='weighted'?1:null,tags:[],variables:{},effects:[],conditions:[]};}
function addRow():void{form.rows.push(newRow());}
function duplicateRow(index:number):void{const copy=structuredClone(toRaw(form.rows[index]));copy.id=`${copy.id}-copy`;form.rows.splice(index+1,0,copy);}
function move(index:number,offset:number):void{const[item]=form.rows.splice(index,1);form.rows.splice(index+offset,0,item);}
function fieldError(field:string):string[]{return props.errors[field]?[props.errors[field]]:[];}
function nestedError(index:number,field:string):string[]{const value=props.errors[`rows.${index}.${field}`];return value?[value]:[];}
function nestedErrors(index:number):Record<string,string>{return Object.fromEntries(Object.entries(props.errors).filter(([key])=>key.startsWith(`rows.${index}.`)).map(([key,value])=>[key.slice(`rows.${index}.`.length),value]));}
</script>

<style scoped>
.definition-grid,.row-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.wide{grid-column:1/-1}.section-heading,.item-actions{display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap}.item-card{margin-top:.75rem}@media(max-width:700px){.definition-grid,.row-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
