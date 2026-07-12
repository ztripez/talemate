import { z } from 'zod';
import { meterSchema, renderPolicySchema } from './gamePrimitives/gamePrimitiveStructuralSchemas.js';

const countSchema = z.number().int().nonnegative();
const jsonValueSchema = z.lazy(() => z.union([
    z.null(), z.boolean(), z.number(), z.string(), z.array(jsonValueSchema), z.record(z.string(), jsonValueSchema),
]));
const jsonObjectSchema = z.record(z.string(), jsonValueSchema);
const countMapSchema = z.record(z.string(), countSchema);
const anchorRefSchema = z.string();
const primitiveRefSchema = z.string();
const validationSchema = z.object({
    ok: z.boolean(), errors: z.array(z.string()), warnings: z.array(z.string()),
}).strict();
const storySceneSchema = z.object({
    id: z.string(), title: z.string(), description: z.string().nullable(), location: z.string().nullable(),
    intro: z.string().nullable(), goals: z.array(z.string()), local_anchors: z.array(anchorRefSchema),
    render_policy: renderPolicySchema,
}).strict();
const transitionLogSchema = z.object({
    transition_id: z.string(), from_scene: z.string(), to_scene: z.string(), carry_anchors: z.array(z.string()),
}).strict();
const transitionSchema = z.object({
    id: z.string(), label: z.string(), to_scene: z.string(), available: z.boolean(), reasons: z.array(z.string()),
}).strict();

/** Validates canonical server-owned metadata used by Game Primitive editors. */
export const gamePrimitiveEditorMetadataSchema = z.object({
    definition_kinds: z.array(z.string()), editable_definition_kinds: z.array(z.string()), primitive_kinds: z.array(z.string()), editable_primitive_kinds: z.array(z.string()),
    definition_editor_kinds: z.array(z.string()), primitive_editor_kinds: z.array(z.string()), anchor_kinds: z.array(z.string()), condition_kinds: z.array(z.string()), effect_kinds: z.array(z.string()), render_policies: z.array(z.string()),
}).strict();

/** Validates the complete server-owned `game_primitives` snapshot wire payload. */
export const gamePrimitivesSnapshotSchema = z.object({
    initialized: z.boolean(),
    version: countSchema.nullable(),
    revision: z.string(),
    editor_metadata: gamePrimitiveEditorMetadataSchema,
    definition_counts: countMapSchema,
    definitions: z.array(z.object({
        kind: z.string(), id: z.string(), title: z.string(), details: jsonObjectSchema,
    }).strict()),
    anchor_count: countSchema,
    primitive_count: countSchema,
    anchors: z.array(z.object({
        ref: anchorRefSchema, kind: z.string(), id: z.string(), tags: z.array(z.string()),
        meta: jsonObjectSchema, primitives: z.record(z.string(), z.record(z.string(), jsonObjectSchema)),
        primitive_counts: countMapSchema, primitive_count: countSchema, primitive_refs: z.array(primitiveRefSchema),
    }).strict()),
    active_characters: z.array(z.string()),
    relationships: z.array(z.object({
        anchor: anchorRefSchema, source: z.string(), target: z.string(), summary: z.string(),
        dimensions: z.array(meterSchema),
    }).strict()),
    drafts: z.array(z.object({
        id: z.string(), status: z.enum(['draft', 'validated', 'committed']), created_by: z.string(),
        definition_counts: countMapSchema, anchor_count: countSchema, primitive_count: countSchema,
        validation: validationSchema,
    }).strict()),
    current_adventure: z.object({
        id: z.string(), title: z.string(), description: z.string().nullable(), current_story_scene: storySceneSchema,
        state: z.object({
            visited: z.array(z.string()), completed: z.array(z.string()), transition_log: z.array(transitionLogSchema),
        }).strict(),
        transitions: z.array(transitionSchema),
    }).strict().nullable(),
    recent_ledger: z.array(z.object({
        id: z.string(), op: z.string(), ref: primitiveRefSchema.nullable(), anchor: anchorRefSchema.nullable(),
        input: jsonObjectSchema, output: jsonObjectSchema, message: z.string().nullable(),
    }).strict()),
}).strict();
