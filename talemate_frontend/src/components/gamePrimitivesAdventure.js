import { z } from 'zod';
import { conditionGroupSchema, effectSchema } from './gamePrimitives/gamePrimitiveDraftContracts.js';
import { renderPolicySchema } from './gamePrimitives/gamePrimitiveStructuralSchemas.js';

export { conditionGroupSchema, effectSchema };

/** Validates one story-scene definition sent through adventure draft authoring. */
export const storySceneSchema = z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().nullable().optional(),
    location: z.string().nullable().optional(),
    intro: z.string().nullable().optional(),
    goals: z.array(z.string()),
    local_anchors: z.array(z.string()),
    entry_effects: z.array(effectSchema),
    exit_effects: z.array(effectSchema),
    render_policy: renderPolicySchema,
}).strict();

/** Validates one transition definition sent through adventure draft authoring. */
export const transitionDefinitionSchema = z.object({
    id: z.string().min(1),
    from_scene: z.string().min(1),
    to_scene: z.string().min(1),
    label: z.string().min(1),
    description: z.string().nullable().optional(),
    conditions: z.array(conditionGroupSchema),
    carry_anchors: z.array(z.string()),
    exit_effects: z.array(effectSchema),
    entry_effects: z.array(effectSchema),
    intro: z.string().nullable().optional(),
}).strict();

/** Validates the complete adventure definition owned by the authoring wire. */
export const adventureDefinitionSchema = z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().nullable().optional(),
    start_scene: z.string().min(1),
    scenes: z.record(z.string(), storySceneSchema),
    transitions: z.record(z.string(), transitionDefinitionSchema),
}).strict();

/**
 * Return all structural errors in a candidate adventure definition.
 * @param {unknown} value Candidate adventure definition.
 * @returns {string[]} Field-qualified errors, or an empty array when valid.
 * @throws {Error} Never; schema failures are returned as strings.
 */
export function validateAdventureDefinition(value) {
    const parsed = adventureDefinitionSchema.safeParse(value);
    if (!parsed.success) return parsed.error.issues.map((issue) => `${issue.path.join('.')}: ${issue.message}`);
    return [];
}

/**
 * Move one property within an object's insertion order.
 * @param {Record<string, unknown>} record Ordered source record.
 * @param {string} id Property to move.
 * @param {number} offset Signed destination offset.
 * @returns {Record<string, unknown>} A reordered shallow copy.
 * @throws {TypeError} `record` cannot be enumerated as object entries.
 */
export function moveOrderedRecord(record, id, offset) {
    const entries = Object.entries(record);
    const index = entries.findIndex(([key]) => key === id);
    const destination = index + offset;
    if (index < 0 || destination < 0 || destination >= entries.length) return { ...record };
    [entries[index], entries[destination]] = [entries[destination], entries[index]];
    return Object.fromEntries(entries);
}

/**
 * Deep-clone a JSON-compatible adventure value.
 * @param {unknown} value JSON-compatible adventure value.
 * @returns {unknown} Detached JSON representation of `value`.
 * @throws {TypeError} The value is not JSON serializable.
 */
export function cloneAdventure(value) {
    return JSON.parse(JSON.stringify(value));
}
