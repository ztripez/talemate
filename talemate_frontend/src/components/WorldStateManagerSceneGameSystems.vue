<template>
    <div class="game-systems">
        <div class="toolbar">
            <div>
                <div class="text-h6">Game Systems</div>
                <div class="text-caption text-medium-emphasis">Canonical Game Primitives inspection and editing</div>
            </div>
            <v-btn
                color="primary"
                variant="text"
                size="small"
                prepend-icon="mdi-refresh"
                :disabled="busy"
                @click="refresh"
            >Refresh</v-btn>
        </div>

        <v-progress-linear v-if="busy" indeterminate color="primary" class="mt-3" aria-label="Loading Game Systems" />
        <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mt-3" data-testid="game-systems-error">
            {{ error }}
        </v-alert>
        <v-alert v-else-if="busy && snapshot === null" color="muted" density="compact" variant="tonal" class="mt-3">
            Loading Game Systems snapshot...
        </v-alert>
        <v-alert v-else-if="snapshot === null" color="muted" density="compact" variant="tonal" class="mt-3">
            Game Systems have not been loaded.
        </v-alert>
        <v-alert v-else-if="!snapshot.initialized" type="info" density="compact" variant="tonal" class="mt-3" data-testid="uninitialized-state">
            Game Primitives are not initialized for this scene. Inspection did not initialize or modify them.
        </v-alert>

        <template v-if="snapshot && snapshot.initialized">
            <v-alert v-if="isEmpty" color="muted" density="compact" variant="tonal" class="mt-3" data-testid="empty-state">
                Game Primitives are initialized, but no definitions, anchors, drafts, adventure, or ledger records exist.
            </v-alert>

            <v-tabs v-model="section" color="primary" density="compact" show-arrows class="section-tabs mt-3">
                <v-tab v-for="item in sections" :key="item.value" :value="item.value">{{ item.title }}</v-tab>
            </v-tabs>
            <v-divider />

            <v-window v-model="section" class="mt-4">
                <v-window-item value="overview"><GameSystemsOverviewSection :snapshot="snapshot" /></v-window-item>

                <v-window-item value="definitions">
                    <GameSystemsDefinitionsSection v-if="section === 'definitions'" :snapshot="snapshot" :revision="editorRevision" :draft="editorDraft" @draft-state="applyDraftState" @snapshot="applySnapshot" />
                </v-window-item>

                <v-window-item value="anchors">
                    <GameSystemsAnchorsSection v-if="section === 'anchors'" :snapshot="snapshot" :revision="editorRevision" :draft="editorDraft" @draft-state="applyDraftState" @snapshot="applySnapshot" />
                </v-window-item>

                <v-window-item value="relationships">
                    <GameSystemsRelationshipsSection :snapshot="snapshot" :focused-anchor="focusedAnchor" @snapshot="applySnapshot" @focus-anchor="focusAnchor" />
                </v-window-item>

                <v-window-item value="drafts">
                    <GameSystemsDraftsSection :snapshot="snapshot" />
                </v-window-item>

                <v-window-item value="adventure">
                    <GameSystemsAdventureSection v-if="section === 'adventure'" :snapshot="snapshot" :revision="editorRevision" :draft="editorDraft" @draft-state="applyDraftState" @snapshot="applySnapshot" />
                </v-window-item>

                <v-window-item value="ledger">
                    <GameSystemsLedgerSection :snapshot="snapshot" />
                </v-window-item>
            </v-window>
        </template>
    </div>
</template>

<script>
import GameSystemsAdventureSection from './game-systems/GameSystemsAdventureSection.vue';
import GameSystemsAnchorsSection from './game-systems/GameSystemsAnchorsSection.vue';
import GameSystemsDefinitionsSection from './game-systems/GameSystemsDefinitionsSection.vue';
import GameSystemsDraftsSection from './game-systems/GameSystemsDraftsSection.vue';
import GameSystemsLedgerSection from './game-systems/GameSystemsLedgerSection.vue';
import GameSystemsOverviewSection from './game-systems/GameSystemsOverviewSection.vue';
import GameSystemsRelationshipsSection from './game-systems/GameSystemsRelationshipsSection.vue';
import { gamePrimitivesResponseSchema } from './gamePrimitives/gamePrimitiveResponseContracts.js';
import { useCorrelatedWebsocketRequest } from './gamePrimitives/useCorrelatedWebsocketRequest.js';
import { gamePrimitivesSnapshotSchema } from './gamePrimitivesSnapshotSchema.js';

/**
 * Owns the authoritative Game Primitives scene snapshot and coordinates focused
 * section editors without duplicating their request lifecycles.
 *
 * @component WorldStateManagerSceneGameSystems
 * @prop {boolean} [isVisible=false] Whether the containing panel is visible. A
 * false-to-true transition requests a fresh snapshot; hiding preserves the last
 * validated snapshot.
 * @inject {() => WebSocket} getWebsocket Returns the active websocket. The socket
 * must implement `send`, `addEventListener`, and `removeEventListener`.
 * @inject {(handler: (message: object) => void) => void} registerMessageHandler
 * Registers a callback for decoded application messages when the component mounts.
 * @inject {(handler: (message: object) => void) => void} unregisterMessageHandler
 * Removes the exact registered callback when the component unmounts.
 * @fires No Vue events. Child section updates are validated and applied locally.
 * Refresh requests are sent as `world_state_manager` websocket messages and
 * responses must satisfy the local strict Zod snapshot contract.
 * @slot None. Focused section components render the snapshot tabs.
 */
export default {
    name: 'WorldStateManagerSceneGameSystems',
    components: { GameSystemsAdventureSection, GameSystemsAnchorsSection, GameSystemsDefinitionsSection, GameSystemsDraftsSection, GameSystemsLedgerSection, GameSystemsOverviewSection, GameSystemsRelationshipsSection },
    props: { isVisible: { type: Boolean, default: false } },
    inject: ['registerMessageHandler', 'unregisterMessageHandler'],
    setup() {
        const transport = useCorrelatedWebsocketRequest();
        return { requestTransport: transport, busy: transport.busy, error: transport.error };
    },
    data() {
        return {
            snapshot: null,
            section: 'overview',
            focusedAnchor: null,
            editorDraft: null,
            editorRevision: '',
            refreshSequence: 0,
            sections: [
                { title: 'Overview', value: 'overview' },
                { title: 'Definitions', value: 'definitions' },
                { title: 'Anchors', value: 'anchors' },
                { title: 'Relationships', value: 'relationships' },
                { title: 'Drafts', value: 'drafts' },
                { title: 'Adventure', value: 'adventure' },
                { title: 'Ledger', value: 'ledger' },
            ],
        };
    },
    computed: {
        isEmpty() {
            return this.snapshot.definitions.length === 0 && this.snapshot.anchors.length === 0 && this.snapshot.drafts.length === 0 && this.snapshot.current_adventure === null && this.snapshot.recent_ledger.length === 0;
        },
    },
    watch: {
        isVisible(visible, wasVisible) {
            if (visible && !wasVisible) this.refresh();
        },
    },
    methods: {
        refresh() {
            const sequence = ++this.refreshSequence;
            return this.requestTransport.request({
                action: 'get_game_primitives', responseAction: 'game_primitives', schema: gamePrimitivesResponseSchema,
                requestKey: 'game-systems-snapshot',
                onResponse: (value) => { if (sequence === this.refreshSequence) this.applySnapshot(value.data); },
            });
         },
        handleMessage(message) {
            if (message.type === 'system' && message.id === 'scene.loaded') {
                this.snapshot = null;
                if (this.isVisible) void this.refresh().catch(this.showRefreshError);
                return;
            }
        },
        applySnapshot(data) {
            this.snapshot = gamePrimitivesSnapshotSchema.parse(data);
            this.editorRevision = this.snapshot.revision;
            this.error = null;
        },
        showRefreshError(reason) {
            const message = reason instanceof Error ? reason.message : String(reason);
            if (message.includes('superseded an earlier request')) return;
            this.error = message;
        },
        applyDraftState({ draft, revision }) {
            this.editorDraft = draft;
            this.editorRevision = revision;
            if (this.snapshot) this.snapshot = { ...this.snapshot, revision };
        },
        focusAnchor(anchor) {
            this.focusedAnchor = anchor;
            this.section = 'relationships';
        },
    },
    mounted() {
        this.registerMessageHandler(this.handleMessage);
        if (this.isVisible) void this.refresh().catch(this.showRefreshError);
    },
    unmounted() {
        this.unregisterMessageHandler(this.handleMessage);
    },
};
</script>

<style scoped>
.game-systems { padding: 1rem 0; min-width: 0; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.section-tabs { max-width: 100%; }
@media (max-width: 700px) {
    .game-systems { padding-top: 0.75rem; }
    .section-tabs { overflow-x: auto; }
}
</style>
