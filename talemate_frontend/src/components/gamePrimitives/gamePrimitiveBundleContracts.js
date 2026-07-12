import { z } from 'zod';

import { adventureDefinitionSchema } from '../gamePrimitivesAdventure.js';
import { conditionGroupSchema, definitionSchemas } from './gamePrimitiveDraftContracts.js';

const nonEmpty = z.string().trim().min(1);
const jsonValueSchema = z.lazy(() => z.union([
    z.null(), z.boolean(), z.number().finite(), z.string(), z.array(jsonValueSchema),
    z.record(z.string(), jsonValueSchema),
]));
const jsonObjectSchema = z.record(z.string(), jsonValueSchema);
const clockSchema = definitionSchemas.clocks;
const modifierSchema = definitionSchemas.modifiers;
const meterSchema = definitionSchemas.meters;
const deckRuntimeSchema = z.object({
    definition_id: nonEmpty,
    mode: z.enum(['sample', 'draw', 'bag', 'physical']),
    draw_pile: z.array(z.string()), discard: z.array(z.string()), recent: z.array(z.string()),
    cooldowns: z.record(z.string(), z.number().int().nonnegative()), exhausted: z.array(z.string()),
    draw_count: z.number().int().nonnegative(), seed: z.string().nullable(),
}).strict();
const deckInstanceSchema = z.object({ definition: nonEmpty, runtime: deckRuntimeSchema }).strict();
const rollTableInstanceSchema = z.object({ definition: nonEmpty }).strict();
const attributeSchema = z.object({
    id: nonEmpty, label: z.string().nullable(),
    source: z.enum(['literal', 'deck', 'roll_table', 'meter', 'clock', 'relationship', 'modifier', 'state_ref']),
    render_policy: nonEmpty, value: jsonValueSchema.nullable(), ref: z.string().nullable(),
    options: jsonObjectSchema, conditions: z.array(conditionGroupSchema),
}).strict();

/** Strict canonical definition collections persisted by GamePrimitiveBundle. */
export const bundleDefinitionsSchema = z.object({
    decks: z.record(z.string(), definitionSchemas.decks),
    roll_tables: z.record(z.string(), definitionSchemas.roll_tables),
    meters: z.record(z.string(), meterSchema), clocks: z.record(z.string(), clockSchema),
    relationship_models: z.record(z.string(), jsonObjectSchema),
    modifiers: z.record(z.string(), modifierSchema),
    attribute_sources: z.record(z.string(), jsonObjectSchema),
    adventures: z.record(z.string(), adventureDefinitionSchema),
}).strict();

/** Strict exact-anchor and typed-instance payload persisted by GamePrimitiveBundle. */
export const bundleAnchorSchema = z.object({
    tags: z.array(z.string()),
    primitives: z.object({
        meters: z.record(z.string(), meterSchema), clocks: z.record(z.string(), clockSchema),
        decks: z.record(z.string(), deckInstanceSchema),
        roll_tables: z.record(z.string(), rollTableInstanceSchema),
        attributes: z.record(z.string(), attributeSchema),
        modifiers: z.record(z.string(), modifierSchema),
    }).strict(),
    meta: jsonObjectSchema,
}).strict();

/** Complete strict websocket/YAML representation of GamePrimitiveBundle. */
export const gamePrimitiveBundleSchema = z.object({
    name: z.string(), template_type: z.literal('game_primitive_bundle'), instructions: z.string().nullable(),
    group: z.string().nullable(), favorite: z.boolean(), uid: z.string().min(1), priority: z.number().int(),
    bundle_schema_version: z.literal(1), definitions: bundleDefinitionsSchema,
    anchors: z.record(z.string(), bundleAnchorSchema),
}).strict();

/** Validates the correlated websocket response containing a newly captured bundle. */
export const bundleCaptureResponseSchema = z.object({
    type: z.literal('world_state_manager'), action: z.literal('game_primitive_bundle_captured'),
    request_id: z.string().min(1), revision: z.string().min(1), data: gamePrimitiveBundleSchema,
}).strict();

/** Validates collision details and resource counts from bundle preview or application. */
export const bundleApplicationSchema = z.object({
    applied: z.boolean(), draft_id: z.string().nullable(), revision: z.string().min(1),
    definition_count: z.number().int().nonnegative(), anchor_count: z.number().int().nonnegative(),
    collisions: z.array(z.object({
        resource: z.enum(['definition', 'anchor']), ref: z.string().min(1),
        location: z.enum(['committed', 'draft']),
    }).strict()),
}).strict();

/** Validates the correlated websocket response for bundle preview or application. */
export const bundleApplicationResponseSchema = z.object({
    type: z.literal('world_state_manager'), action: z.literal('game_primitive_bundle_application'),
    request_id: z.string().min(1), data: bundleApplicationSchema,
}).strict();
