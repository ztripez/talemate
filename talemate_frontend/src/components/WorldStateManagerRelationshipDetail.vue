<template>
    <v-card variant="outlined" class="relationship-detail" :data-anchor="relationship.anchor">
        <v-card-title class="direction-title">
            <span>{{ relationship.source }} <v-icon size="small">mdi-arrow-right</v-icon> {{ relationship.target }}</span>
            <v-btn size="small" variant="text" prepend-icon="mdi-open-in-new" @click="$emit('navigate-anchor', relationship.anchor)">Game Systems</v-btn>
        </v-card-title>
        <v-card-text>
            <code class="canonical-ref">{{ relationship.anchor }}</code>
            <v-alert v-if="refError" type="error" density="compact" variant="tonal" class="mt-3">{{ refError }}</v-alert>
            <p v-if="relationship.summary" class="text-body-2 mt-2">{{ relationship.summary }}</p>
            <p v-else class="text-caption text-medium-emphasis mt-2">No prompt-visible summary.</p>

            <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mt-3" data-testid="relationship-error">{{ error }}</v-alert>
            <v-alert v-if="validation" :type="validation.ok ? 'success' : 'error'" density="compact" variant="tonal" class="mt-3" data-testid="relationship-validation">
                {{ validation.ok ? 'Draft validated. Committing…' : validation.errors.join('; ') }}
                <span v-if="validation.warnings.length"> {{ validation.warnings.join('; ') }}</span>
            </v-alert>
            <v-progress-linear v-if="busy" indeterminate color="primary" class="mt-3" />

            <div v-for="dimension in relationship.dimensions" :key="dimension.id" class="dimension mt-4">
                <div class="dimension-heading">
                    <strong>{{ dimension.label || dimension.id }}</strong>
                    <code>{{ primitiveRef(dimension.id) || 'Invalid primitive ref' }}</code>
                </div>
                <div class="authored-fields">
                    <GamePrimitiveMeterClockAuthoredFields v-model="drafts[dimension.id]" kind="meters" :render-policies="renderPolicies" :disabled="busy" />
                </div>
                <GamePrimitiveMeterRuntimeControls :value="dimension.value" :max="dimension.max" :disabled="busy" @adjust="adjust(dimension, $event)" />
                <div class="dimension-actions">
                    <v-btn color="primary" variant="tonal" size="small" :disabled="busy" @click="saveDimension(drafts[dimension.id])">Save authored fields</v-btn>
                    <v-btn color="error" variant="text" size="small" :disabled="busy" @click="previewDeleteDimension(dimension)">Delete</v-btn>
                </div>
            </div>

            <v-divider class="my-4" />
            <div class="text-subtitle-2">Add authored dimension</div>
            <div class="new-dimension mt-1">
                <v-text-field v-model="newDimension.id" label="Dimension id" density="compact" :disabled="busy" />
                <div class="authored-fields"><GamePrimitiveMeterClockAuthoredFields v-model="newDimension" kind="meters" :render-policies="renderPolicies" :disabled="busy" /></div>
                <v-btn color="primary" variant="tonal" :disabled="busy || !newDimension.id.trim()" @click="saveDimension(newDimension)">Add</v-btn>
            </div>

            <v-btn v-if="relationship.dimensions.length" color="error" variant="text" size="small" class="mt-3" :disabled="busy" @click="previewDeleteAnchor">Delete complete relationship</v-btn>

            <v-card v-if="deletePreview" color="error" variant="tonal" class="mt-3" data-testid="delete-preview">
                <v-card-text>
                    <strong>Deletion preview</strong>
                    <p class="text-body-2 mt-1">{{ deletePreview.message }}</p>
                    <code>{{ deletePreview.target.ref }}</code>
                    <p class="text-body-2 mt-2">Anchors {{ deletePreview.candidate.before.anchors }} -> {{ deletePreview.candidate.after.anchors }} · Primitives {{ deletePreview.candidate.before.primitives }} -> {{ deletePreview.candidate.after.primitives }}</p>
                    <v-alert v-for="finding in deletePreview.validation.errors" :key="`error-${finding}`" type="error" density="compact" variant="tonal" class="mt-2">{{ finding }}</v-alert>
                    <v-alert v-for="finding in deletePreview.validation.warnings" :key="`warning-${finding}`" type="warning" density="compact" variant="tonal" class="mt-2">{{ finding }}</v-alert>
                    <p v-if="!deletePreview.validation.errors.length && !deletePreview.validation.warnings.length" class="text-body-2 mt-2">No validation findings.</p>
                </v-card-text>
                <v-card-actions>
                    <v-btn variant="text" :disabled="busy" @click="deletePreview = null">Cancel</v-btn>
                    <v-btn color="error" variant="flat" :disabled="busy || deletePreview.validation.errors.length > 0" @click="confirmDelete">Confirm delete</v-btn>
                </v-card-actions>
            </v-card>
        </v-card-text>
    </v-card>
</template>

<script>
import { authoritativeGamePrimitivesResponseSchema, deletionPreviewResponseSchema } from './gamePrimitives/gamePrimitiveResponseContracts.js';
import { useCorrelatedWebsocketRequest } from './gamePrimitives/useCorrelatedWebsocketRequest.js';
import GamePrimitiveMeterClockAuthoredFields from './gamePrimitives/GamePrimitiveMeterClockAuthoredFields.vue';
import GamePrimitiveMeterRuntimeControls from './gamePrimitives/GamePrimitiveMeterRuntimeControls.vue';
import { canonicalAnchorRef, canonicalPrimitiveRef, parseAnchorRef, parsePrimitiveRef } from './game-systems/gamePrimitiveRefs.js';

export default {
    name: 'WorldStateManagerRelationshipDetail',
    components: { GamePrimitiveMeterClockAuthoredFields, GamePrimitiveMeterRuntimeControls },
    props: {
        relationship: { type: Object, required: true },
        revision: { type: String, required: true },
        renderPolicies: { type: Array, required: true },
    },
    emits: ['changed', 'navigate-anchor'],
    setup() {
        const transport = useCorrelatedWebsocketRequest();
        return { requestTransport: transport, busy: transport.busy, error: transport.error };
    },
    data() {
        return {
            validation: null,
            drafts: {},
            adjustments: {},
            deletePreview: null,
            newDimension: { id: '', label: null, min: -5, max: 5, value: 0, render_policy: 'summary' },
        };
    },
    computed: {
        canonicalAnchor() {
            try { return parseAnchorRef(this.relationship.anchor).ref; }
            catch { return null; }
        },
        refError() {
            if (!this.canonicalAnchor) return `Invalid relationship ref: ${this.relationship.anchor}`;
            const expected = canonicalAnchorRef('relationship', `${this.relationship.source}->${this.relationship.target}`);
            return this.canonicalAnchor === expected ? null : `Relationship ref does not match its participants: ${this.relationship.anchor}`;
        },
    },
    watch: {
        relationship: {
            immediate: true,
            deep: true,
            handler(value) {
                this.drafts = Object.fromEntries(value.dimensions.map((dimension) => [dimension.id, { ...dimension }]));
                this.adjustments = Object.fromEntries(value.dimensions.map((dimension) => [dimension.id, 0]));
            },
        },
    },
    methods: {
        request(action, fields) {
            return this.requestTransport.request({ action, responseAction: 'game_primitives', schema: authoritativeGamePrimitivesResponseSchema, fields });
        },
        primitiveRef(id) {
            if (!this.canonicalAnchor) return null;
            try { return canonicalPrimitiveRef(this.canonicalAnchor, 'meters', id); }
            catch { return null; }
        },
        async authorRelationship(change) {
            if (this.refError) throw new Error(this.refError);
            this.validation = null;
            const response = await this.request('author_game_primitive_relationship', {
                expected_revision: this.revision, source: this.relationship.source, target: this.relationship.target, change,
            });
            this.$emit('changed', response.data);
            return response.data;
        },
        saveDimension(dimension) {
            const id = dimension.id.trim();
            return this.authorRelationship({ operation: 'upsert_dimension', dimension: { ...dimension, id, label: dimension.label || null } });
        },
        async adjust(dimension, delta = this.adjustments[dimension.id]) {
            const ref = this.primitiveRef(dimension.id);
            if (!ref) throw new Error(`Invalid relationship dimension ref: ${dimension.id}`);
            const response = await this.request('adjust_game_primitive', { expected_revision: this.revision, ref, delta });
            this.$emit('changed', response.data);
            return response.data;
        },
        async previewDeleteDimension(dimension) {
            const ref = this.primitiveRef(dimension.id);
            if (!ref) throw new Error(`Invalid relationship dimension ref: ${dimension.id}`);
            const preview = await this.requestTransport.request({
                action: 'preview_delete_game_primitive', responseAction: 'game_primitive_deletion_preview', schema: deletionPreviewResponseSchema,
                fields: { expected_revision: this.revision, ref },
            });
            this.deletePreview = { ...preview,
                kind: 'dimension',
                message: `Delete only “${dimension.label || dimension.id}”. Other dimensions and the reverse edge remain unchanged.`,
            };
        },
        async previewDeleteAnchor() {
            if (this.refError) throw new Error(this.refError);
            const preview = await this.requestTransport.request({
                action: 'preview_delete_game_primitive_anchor', responseAction: 'game_primitive_deletion_preview', schema: deletionPreviewResponseSchema,
                fields: { expected_revision: this.revision, anchor: this.canonicalAnchor },
            });
            this.deletePreview = { ...preview,
                kind: 'anchor',
                message: `Delete ${this.relationship.source} → ${this.relationship.target} and all ${this.relationship.dimensions.length} dimensions. The reverse edge remains unchanged.`,
            };
        },
        async confirmDelete() {
            const preview = this.deletePreview;
            if (!preview) throw new Error('Deletion preview is required');
            if (preview.validation.errors.length) throw new Error('Deletion preview has validation errors');
            if (preview.kind === 'anchor') {
                await this.authorRelationship({ operation: 'delete_edge' });
            } else {
                await this.authorRelationship({ operation: 'delete_dimension', dimension_id: parsePrimitiveRef(preview.target.ref).id });
            }
            this.deletePreview = null;
        },
    },
};
</script>

<style scoped>
.relationship-detail { min-width: 0; }
.direction-title, .dimension-heading, .dimension-actions { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
.dimension { padding: 0.75rem; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; }
.dimension-heading code, .canonical-ref { color: rgb(var(--v-theme-secondary)); overflow-wrap: anywhere; }
.authored-fields { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem; margin: .75rem 0; }
.new-dimension { display: grid; grid-template-columns: minmax(10rem, 1fr) 3fr auto; gap: .75rem; align-items: start; }
@media (max-width: 700px) {
    .direction-title { align-items: flex-start; flex-direction: column; }
    .dimension-actions > * { width: 100%; max-width: none; }
    .authored-fields, .new-dimension { grid-template-columns: 1fr; }
}
</style>
