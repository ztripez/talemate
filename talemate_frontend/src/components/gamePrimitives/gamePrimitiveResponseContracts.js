import { z } from 'zod';

import { gamePrimitiveEditorMetadataSchema, gamePrimitivesSnapshotSchema } from '../gamePrimitivesSnapshotSchema.js';
import { draftResponseSchema, draftsResponseSchema } from './gamePrimitiveDraftContracts.js';

const requestIdSchema = z.string().min(1);
const errorSchema = z.object({ message: z.string().min(1) }).strict();
const validationSchema = z.object({ ok: z.boolean(), errors: z.array(z.string()), warnings: z.array(z.string()) }).strict();

/** Validates a correlated server-owned authoritative snapshot response. */
export const gamePrimitivesResponseSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitives'),
    request_id: requestIdSchema,
    data: gamePrimitivesSnapshotSchema,
}).strict();

/** Requires a non-empty server revision on a snapshot response used as authority. */
export const authoritativeGamePrimitivesResponseSchema = gamePrimitivesResponseSchema.refine(
    (response) => response.data.revision.length > 0,
    { path: ['data', 'revision'], message: 'An authoritative revision is required' },
);

/** Validates a correlated scene-independent canonical editor metadata response. */
export const gamePrimitiveEditorMetadataResponseSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitive_editor_metadata'),
    request_id: requestIdSchema,
    data: gamePrimitiveEditorMetadataSchema,
}).strict();

const activationResultSchema = z.object({
    ok: z.boolean(),
    adventure_id: z.string().min(1),
    state: z.object({
        adventure_id: z.string().min(1),
        current_story_scene: z.string().min(1),
        visited: z.array(z.string()),
        completed: z.array(z.string()),
        transition_log: z.array(z.object({
            transition_id: z.string(), from_scene: z.string(), to_scene: z.string(), carry_anchors: z.array(z.string()),
        }).strict()),
    }).strict().nullable(),
    error: z.string().nullable(),
}).strict();

const effectResultSchema = z.object({
    ok: z.boolean(), op: z.string(), target: z.string().nullable(), previous: z.unknown().nullable(),
    current: z.unknown().nullable(), message: z.string().nullable(), error: z.string().nullable(),
}).strict();

const transitionResultSchema = z.object({
    ok: z.boolean(),
    transition_id: z.string().min(1),
    from_scene: z.string().nullable(),
    to_scene: z.string().nullable(),
    intro: z.string().nullable(),
    error: z.string().nullable(),
    effects: z.array(effectResultSchema),
}).strict();

/** Validates the server-owned adventure activation result and resulting snapshot. */
export const adventureActivationResponseSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitive_adventure_activation'),
    request_id: requestIdSchema,
    result: activationResultSchema,
    data: gamePrimitivesSnapshotSchema,
}).strict().refine((response) => response.data.revision.length > 0, {
    path: ['data', 'revision'], message: 'An authoritative revision is required',
});

/** Validates the server-owned transition result and resulting snapshot. */
export const adventureTransitionResponseSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitive_adventure_transition'),
    request_id: requestIdSchema,
    result: transitionResultSchema,
    data: gamePrimitivesSnapshotSchema,
}).strict().refine((response) => response.data.revision.length > 0, {
    path: ['data', 'revision'], message: 'An authoritative revision is required',
});

/** Validates a correlated server-owned pre-commit failure response. */
export const gamePrimitivesFailureSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitives_failed'),
    request_id: requestIdSchema,
    request_action: z.string().min(1),
    error: errorSchema,
}).strict();

/** Validates a server report that a committed mutation lacks confirmation. */
export const gamePrimitivesIndeterminateSchema = z.object({
    type: z.literal('world_state_manager'),
    action: z.literal('game_primitives_indeterminate'),
    request_id: requestIdSchema,
    request_action: z.string().min(1),
    outcome: z.literal('committed_but_unconfirmed'),
    revision: z.string().min(1),
    error: errorSchema,
}).strict();

/** Validates the server-owned impact preview for a prospective deletion. */
export const deletionPreviewResponseSchema = z.object({
    type: z.literal('world_state_manager'), action: z.literal('game_primitive_deletion_preview'), request_id: requestIdSchema,
    revision: z.string().min(1), target: z.object({ kind: z.enum(['anchor', 'primitive']), ref: z.string().min(1) }).strict(),
    draft: z.unknown(), validation: validationSchema,
    candidate: z.object({
        before: z.object({ definitions: z.number().int().nonnegative(), anchors: z.number().int().nonnegative(), primitives: z.number().int().nonnegative() }).strict(),
        after: z.object({ definitions: z.number().int().nonnegative(), anchors: z.number().int().nonnegative(), primitives: z.number().int().nonnegative() }).strict(),
        candidate_revision: z.string().min(1),
    }).strict(),
}).strict();

/** Maps success action discriminators to the frontend-owned response validators. */
export const gamePrimitiveResponseSchemas = Object.freeze({
    game_primitive_draft: draftResponseSchema,
    game_primitive_drafts: draftsResponseSchema,
    game_primitives: gamePrimitivesResponseSchema,
    game_primitive_editor_metadata: gamePrimitiveEditorMetadataResponseSchema,
    game_primitive_adventure_activation: adventureActivationResponseSchema,
    game_primitive_adventure_transition: adventureTransitionResponseSchema,
});
