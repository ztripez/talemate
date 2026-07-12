import { describe, expect, it } from 'vitest';

import { gamePrimitivesSnapshotSchema } from '../gamePrimitivesSnapshotSchema.js';
import { definitionSchemas } from './gamePrimitiveDraftContracts.js';
import { meterSchema, renderPolicySchema } from './gamePrimitiveStructuralSchemas.js';

describe('Game Primitive structural schemas', () => {
    it('shares the meter schema between draft and snapshot contracts', () => {
        expect(definitionSchemas.meters).toBe(meterSchema);
    });

    it('accepts backend-owned render policy strings structurally', () => {
        expect(renderPolicySchema.parse('memory')).toBe('memory');
        expect(meterSchema.parse({ id: 'trust', label: null, min: -5, max: 5, value: 1, render_policy: 'future-policy' }).render_policy).toBe('future-policy');
    });

    it('accepts metadata-driven kind and policy additions in snapshots', () => {
        const snapshot = {
            initialized: false, version: null, revision: '',
            editor_metadata: {
                definition_kinds: [], editable_definition_kinds: [], primitive_kinds: [], editable_primitive_kinds: [],
                definition_editor_kinds: [], primitive_editor_kinds: [], anchor_kinds: ['custom'], condition_kinds: ['custom-condition'], effect_kinds: ['custom-effect'], render_policies: ['memory'],
            },
            definition_counts: {}, definitions: [], anchor_count: 0, primitive_count: 0, anchors: [], active_characters: [], relationships: [], drafts: [], current_adventure: null, recent_ledger: [],
        };
        expect(gamePrimitivesSnapshotSchema.parse(snapshot).editor_metadata.render_policies).toEqual(['memory']);
    });
});
