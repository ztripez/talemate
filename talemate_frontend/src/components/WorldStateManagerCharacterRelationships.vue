<template>
    <div class="character-relationships">
        <div class="relationship-toolbar">
            <div>
                <div class="text-h6">Directional relationships</div>
                <div class="text-caption text-medium-emphasis">Incoming and outgoing edges are independent.</div>
            </div>
            <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :disabled="busy" @click="refresh">Refresh</v-btn>
        </div>
        <v-progress-linear v-if="busy" indeterminate color="primary" class="mt-3" />
        <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mt-3" data-testid="relationships-error">{{ error }}</v-alert>

        <v-card v-if="snapshot" variant="tonal" class="mt-3">
            <v-card-text>
                <div class="text-subtitle-2">Create directional relationship</div>
                <div class="create-row mt-2">
                    <v-select v-model="createDirection" :items="directionItems" item-title="title" item-value="value" label="Direction" density="compact" />
                    <v-select v-model="otherCharacter" :items="availableCharacters" label="Other active character" density="compact" />
                    <v-btn color="primary" variant="tonal" :disabled="!otherCharacter || relationshipExists" @click="beginCreate">Create</v-btn>
                </div>
                <v-alert v-if="relationshipExists" type="info" density="compact" variant="text">That directional edge already exists below.</v-alert>
            </v-card-text>
        </v-card>

        <RelationshipDetail
            v-if="newRelationship"
            class="mt-4"
            :relationship="newRelationship"
            :revision="snapshot.revision"
            :render-policies="snapshot.editor_metadata.render_policies"
            @changed="applySnapshot"
            @navigate-anchor="navigateAnchor"
        />

        <section v-if="snapshot" class="mt-5" data-testid="outgoing-relationships">
            <div class="text-subtitle-1"><v-icon size="small">mdi-arrow-top-right</v-icon> Outgoing: {{ characterName }} → Other</div>
            <v-alert v-if="outgoing.length === 0" color="muted" density="compact" variant="tonal" class="mt-2">No outgoing relationships.</v-alert>
            <RelationshipDetail
                v-for="relationship in outgoing"
                :key="relationship.anchor"
                class="mt-3"
                :relationship="relationship"
                :revision="snapshot.revision"
                :render-policies="snapshot.editor_metadata.render_policies"
                @changed="applySnapshot"
                @navigate-anchor="navigateAnchor"
            />
        </section>

        <section v-if="snapshot" class="mt-5" data-testid="incoming-relationships">
            <div class="text-subtitle-1"><v-icon size="small">mdi-arrow-bottom-left</v-icon> Incoming: Other → {{ characterName }}</div>
            <v-alert v-if="incoming.length === 0" color="muted" density="compact" variant="tonal" class="mt-2">No incoming relationships.</v-alert>
            <RelationshipDetail
                v-for="relationship in incoming"
                :key="relationship.anchor"
                class="mt-3"
                :relationship="relationship"
                :revision="snapshot.revision"
                :render-policies="snapshot.editor_metadata.render_policies"
                @changed="applySnapshot"
                @navigate-anchor="navigateAnchor"
            />
        </section>
    </div>
</template>

<script>
import { gamePrimitivesResponseSchema } from './gamePrimitives/gamePrimitiveResponseContracts.js';
import { useCorrelatedWebsocketRequest } from './gamePrimitives/useCorrelatedWebsocketRequest.js';
import { canonicalAnchorRef } from './game-systems/gamePrimitiveRefs.js';
import { gamePrimitivesSnapshotSchema } from './gamePrimitivesSnapshotSchema.js';
import RelationshipDetail from './WorldStateManagerRelationshipDetail.vue';

export default {
    name: 'WorldStateManagerCharacterRelationships',
    components: { RelationshipDetail },
    props: { characterName: { type: String, required: true } },
    emits: ['navigate-anchor'],
    inject: ['registerMessageHandler', 'unregisterMessageHandler'],
    setup() {
        const transport = useCorrelatedWebsocketRequest();
        return { requestTransport: transport, busy: transport.busy, error: transport.error };
    },
    data() {
        return {
            snapshot: null,
            createDirection: 'outgoing',
            otherCharacter: null,
            newRelationship: null,
            directionItems: [
                { title: `${this.characterName} → Other`, value: 'outgoing' },
                { title: `Other → ${this.characterName}`, value: 'incoming' },
            ],
        };
    },
    computed: {
        outgoing() {
            return [...(this.snapshot?.relationships || [])]
                .filter((item) => item.source === this.characterName)
                .sort((a, b) => a.target.localeCompare(b.target));
        },
        incoming() {
            return [...(this.snapshot?.relationships || [])]
                .filter((item) => item.target === this.characterName)
                .sort((a, b) => a.source.localeCompare(b.source));
        },
        availableCharacters() {
            return (this.snapshot?.active_characters || []).filter((name) => name !== this.characterName);
        },
        proposedParticipants() {
            return this.createDirection === 'outgoing'
                ? [this.characterName, this.otherCharacter]
                : [this.otherCharacter, this.characterName];
        },
        relationshipExists() {
            if (!this.otherCharacter) return false;
            const [source, target] = this.proposedParticipants;
            return this.snapshot.relationships.some((item) => item.source === source && item.target === target);
        },
    },
    watch: {
        characterName() {
            this.otherCharacter = null;
            this.newRelationship = null;
            void this.refresh().catch(this.showRefreshError);
        },
    },
    methods: {
        refresh() {
            return this.requestTransport.request({
                action: 'get_game_primitives', responseAction: 'game_primitives', schema: gamePrimitivesResponseSchema,
                requestKey: 'relationship-snapshot',
                onResponse: (value) => this.applySnapshot(value.data),
            });
        },
        handleMessage(message) {
            if (message.type === 'system' && message.id === 'scene.loaded') {
                this.snapshot = null;
                void this.refresh().catch(this.showRefreshError);
            }
        },
        applySnapshot(data) {
            try {
                this.snapshot = gamePrimitivesSnapshotSchema.parse(data);
                this.error = null;
                this.newRelationship = null;
            } catch (error) {
                this.error = `Malformed relationship snapshot: ${error instanceof Error ? error.message : String(error)}`;
                throw error;
            }
        },
        showRefreshError(reason) {
            this.error = reason instanceof Error ? reason.message : String(reason);
        },
        beginCreate() {
            const [source, target] = this.proposedParticipants;
            this.newRelationship = {
                anchor: canonicalAnchorRef('relationship', `${source}->${target}`), source, target, summary: '', dimensions: [],
            };
        },
        navigateAnchor(anchor) { this.$emit('navigate-anchor', anchor); },
    },
    mounted() {
        this.registerMessageHandler(this.handleMessage);
        void this.refresh().catch(this.showRefreshError);
    },
    unmounted() {
        this.unregisterMessageHandler(this.handleMessage);
    },
};
</script>

<style scoped>
.character-relationships { min-width: 0; }
.relationship-toolbar, .create-row { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
.create-row > :not(:last-child) { flex: 1 1 220px; }
@media (max-width: 700px) {
    .relationship-toolbar, .create-row { align-items: stretch; flex-direction: column; }
    .create-row > * { width: 100%; }
}
</style>
