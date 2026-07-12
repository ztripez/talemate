import { z } from 'zod';
import { meterSchema, renderPolicySchema } from './gamePrimitiveStructuralSchemas.js';

const idSchema = z.string().trim().min(1).refine((value) => !value.includes('/'), 'Must not contain /');
const finiteNumberSchema = z.number().finite();
const jsonValueSchema = z.lazy(() => z.union([
    z.null(), z.boolean(), finiteNumberSchema, z.string(), z.array(jsonValueSchema),
    z.record(z.string(), jsonValueSchema),
]));
const jsonObjectSchema = z.record(z.string(), jsonValueSchema);

export { renderPolicySchema };

/** Validates the effect object wire shape accepted by draft mutation requests. */
export const effectSchema = z.object({
    op: z.string().trim().min(1),
    target: z.string().nullable().optional(),
    value: jsonValueSchema.nullable().optional(),
    by: finiteNumberSchema.nullable().optional(),
    data: jsonObjectSchema.optional().default({}),
}).strict();

/** Validates one condition wire object accepted by draft authoring requests. */
export const conditionSchema = z.object({
    kind: z.string().trim().min(1),
    path: z.string().nullable(),
    operator: z.enum(['==', '!=', '>', '<', '>=', '<=', 'in', 'not_in', 'is_true', 'is_false', 'is_null', 'is not null', 'is_not_null']).nullable(),
    value: jsonValueSchema.nullable(),
    anchor: z.string().nullable(),
    tag: z.string().nullable(),
    dimension: z.string().nullable(),
    data: jsonObjectSchema,
}).strict();

/** Validates an ordered AND/OR condition group sent over the authoring wire. */
export const conditionGroupSchema = z.object({
    operator: z.enum(['and', 'or']),
    conditions: z.array(conditionSchema),
}).strict();

const clockSchema = z.object({
    id: idSchema,
    label: z.string().nullable(),
    max: z.number().int(),
    value: z.number().int(),
    render_policy: renderPolicySchema,
}).strict();

const modifierSchema = z.object({
    id: idSchema,
    label: z.string().nullable(),
    explanation: z.string().nullable(),
    applies_to: z.string().trim().min(1),
    when: z.array(conditionGroupSchema),
    add: finiteNumberSchema,
}).strict();

const cardSchema = z.object({
    id: idSchema,
    label: z.string().trim().min(1),
    text: z.string().nullable(),
    weight: finiteNumberSchema,
    tags: z.array(z.string()),
    variables: jsonObjectSchema,
    effects: z.array(effectSchema),
    conditions: z.array(conditionGroupSchema),
    cooldown_turns: z.number().int().nullable(),
    unique: z.boolean(),
}).strict();

const deckSchema = z.object({
    id: idSchema,
    name: z.string().trim().min(1),
    mode: z.enum(['sample', 'draw', 'bag', 'physical']),
    shuffle: z.enum(['seeded', 'random']),
    reshuffle: z.enum(['never', 'when_empty']),
    cards: z.array(cardSchema),
    tags: z.array(z.string()),
    variables: jsonObjectSchema,
}).strict();

const rowSchema = z.object({
    id: idSchema,
    label: z.string().trim().min(1),
    text: z.string().nullable(),
    range: z.union([z.string(), z.number().int()]).nullable(),
    weight: finiteNumberSchema.nullable(),
    tags: z.array(z.string()),
    variables: jsonObjectSchema,
    effects: z.array(effectSchema),
    conditions: z.array(conditionGroupSchema),
}).strict();

const rollTableSchema = z.object({
    id: idSchema,
    name: z.string().trim().min(1),
    mode: z.enum(['dice', 'weighted']),
    dice: z.string().nullable(),
    rows: z.array(rowSchema),
    modifiers: z.array(z.string()),
}).strict();

/** Maps server-owned editable definition kinds to frontend form validators. */
export const definitionSchemas = Object.freeze({
    meters: meterSchema,
    clocks: clockSchema,
    modifiers: modifierSchema,
    decks: deckSchema,
    roll_tables: rollTableSchema,
});

const definitionsSchema = z.object({
    decks: z.record(z.string(), deckSchema),
    roll_tables: z.record(z.string(), rollTableSchema),
    meters: z.record(z.string(), meterSchema),
    clocks: z.record(z.string(), clockSchema),
    relationship_models: z.record(z.string(), jsonObjectSchema),
    modifiers: z.record(z.string(), modifierSchema),
    attribute_sources: z.record(z.string(), jsonObjectSchema),
    adventures: z.record(z.string(), jsonObjectSchema),
}).strict();

const targetsSchema = z.object({
    definitions: z.array(z.object({ kind: z.string(), id: z.string() }).strict()),
    anchors: z.array(z.string()),
    primitives: z.array(z.string()),
}).strict();
const validationSchema = z.object({ ok: z.boolean(), errors: z.array(z.string()), warnings: z.array(z.string()) }).strict();

/** Validates the complete persisted draft shape returned by the server. */
export const primitiveDraftSchema = z.object({
    id: idSchema,
    status: z.enum(['draft', 'validated', 'committed']),
    created_by: z.string().min(1),
    definitions: definitionsSchema,
    anchors: z.record(z.string(), jsonObjectSchema),
    replacements: targetsSchema,
    deletions: targetsSchema,
    validation: validationSchema,
}).strict();

/** Validates the server response carrying one correlated primitive draft. */
export const draftResponseSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitive_draft'),
    request_id: z.string().min(1),
    data: primitiveDraftSchema,
    revision: z.string().min(1),
}).strict();

/** Validates the server response carrying the correlated persisted draft list. */
export const draftsResponseSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitive_drafts'),
    request_id: z.string().min(1),
    data: z.array(primitiveDraftSchema),
    revision: z.string().min(1),
}).strict();

/**
 * Converts definition validation issues into form-field messages.
 * @param {string} kind Server-owned editable definition kind.
 * @param {unknown} value Candidate definition form value.
 * @returns {Record<string, string>} Field paths mapped to validation messages.
 * @throws {Error} Never; unsupported kinds become a `_form` error.
 */
export function definitionFieldErrors(kind, value) {
    const result = definitionSchemas[kind]?.safeParse(value);
    if (!result) return { _form: 'This definition type is read-only' };
    if (result.success) return {};
    return Object.fromEntries(result.error.issues.map((issue) => [issue.path.join('.') || '_form', issue.message]));
}

/**
 * Parse a definition into the canonical frontend wire shape.
 * @param {string} kind Server-owned editable definition kind.
 * @param {unknown} value Candidate definition value.
 * @returns {object} Parsed definition safe to send on the authoring wire.
 * @throws {Error} Zod parsing fails or `kind` has no editable schema.
 */
export function canonicalDefinition(kind, value) {
    return definitionSchemas[kind].parse(value);
}

/**
 * Create a detached form value for an editable definition kind.
 * @param {string} kind Server-owned editable definition kind.
 * @param {string} [id=''] Initial definition identifier.
 * @returns {object} Detached default definition value.
 * @throws {DOMException} The selected kind is unsupported or cannot be cloned.
 */
export function emptyDefinition(kind, id = '') {
    const common = { id };
    const values = {
        meters: { ...common, label: null, min: 0, max: 10, value: 0, render_policy: 'hidden' },
        clocks: { ...common, label: null, max: 4, value: 0, render_policy: 'summary' },
        modifiers: { ...common, label: null, explanation: null, applies_to: '', when: [], add: 0 },
        decks: { ...common, name: '', mode: 'bag', shuffle: 'seeded', reshuffle: 'when_empty', cards: [], tags: [], variables: {} },
        roll_tables: { ...common, name: '', mode: 'dice', dice: '1d6', rows: [], modifiers: [] },
    };
    return structuredClone(values[kind]);
}
