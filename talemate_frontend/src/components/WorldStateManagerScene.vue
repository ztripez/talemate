<template>
    <div v-if="scene !== null && scene.data != null" class="scene-manager" :style="{ maxWidth: MAX_CONTENT_WIDTH }">
        <v-card class="scene-card">
            <v-card-title>
                {{ title }}
                <div class="text-muted text-caption">
                    {{ scene.data.context }}
                </div>
            </v-card-title>
            <v-card-text class="scene-content">
                <v-tabs v-model="page" color="primary" density="compact" show-arrows class="scene-navigation">
                    <v-tab value="outline">
                        <v-icon size="small" class="mr-1">mdi-script-text</v-icon>
                        Outline
                    </v-tab>
                    <v-tab value="director">
                        <v-icon size="small" class="mr-1">mdi-bullhorn</v-icon>
                        Direction
                    </v-tab>
                    <v-tab value="gamestate">
                        <v-icon size="small" class="mr-1">mdi-gamepad-square</v-icon>
                        Game State
                    </v-tab>
                    <v-tab value="primitives" @click="navigate('primitives')">
                        <v-icon size="small" class="mr-1">mdi-puzzle</v-icon>
                        Game Systems
                    </v-tab>
                    <v-tab value="shared">
                        <v-icon size="small" class="mr-1">mdi-earth-arrow-right</v-icon>
                        Shared World
                    </v-tab>
                    <!--
                    <v-tab value="messages">
                        <v-icon size="small" class="mr-1">mdi-tools</v-icon>
                        Utilities
                    </v-tab>
                    -->
                    <v-tab value="settings">
                        <v-icon size="small" class="mr-1">mdi-cogs</v-icon>
                        Settings
                    </v-tab>
                    <v-tab value="export">
                        <v-icon size="small" class="mr-1">mdi-export</v-icon>
                        Export
                    </v-tab>
                </v-tabs>
                <v-divider></v-divider>
                <v-window v-model="page">
                    <v-window-item value="outline">
                        <WorldStateManagerSceneOutline 
                            :app-config="appConfig"
                            :templates="templates"
                            :generation-options="generationOptions"
                            :immutableScene="scene">
                        </WorldStateManagerSceneOutline>
                    </v-window-item>

                    <v-window-item value="director">
                        <WorldStateManagerSceneDirection 
                            ref="director"
                            :is-visible="page === 'director'"
                            :templates="templates"
                            :immutableScene="scene">
                        </WorldStateManagerSceneDirection>
                    </v-window-item>

                    <v-window-item value="gamestate">
                        <GameState 
                            ref="gamestate"
                            :is-visible="page === 'gamestate'"
                            :scene="scene"
                        />
                    </v-window-item>

                    <v-window-item value="primitives">
                        <WorldStateManagerSceneGameSystems
                            ref="primitives"
                            :is-visible="page === 'primitives'"
                        />
                    </v-window-item>

                    <v-window-item value="shared">
                        <WorldStateManagerSceneSharedWorld 
                            ref="shared"
                            :scene="scene"
                            :app-config="appConfig"
                            :templates="templates"
                            :generation-options="generationOptions">
                        </WorldStateManagerSceneSharedWorld>
                    </v-window-item>

                    <v-window-item value="settings">
                        <WorldStateManagerSceneSettings 
                            :app-config="appConfig"
                            :templates="templates"
                            :generation-options="generationOptions"
                            :immutableScene="scene">
                        </WorldStateManagerSceneSettings>
                    </v-window-item>

                    <v-window-item value="export">
                        <WorldStateManagerSceneExport 
                            :immutableScene="scene">
                        </WorldStateManagerSceneExport>
                    </v-window-item>
                </v-window> 

            </v-card-text>
        </v-card>
    </div>
    <div v-else>
        <v-alert color="muted" density="compact" variant="text">
            No scene active.. 
        </v-alert>
    </div>
</template>
<script>

import WorldStateManagerSceneOutline from './WorldStateManagerSceneOutline.vue';
import WorldStateManagerSceneSettings from './WorldStateManagerSceneSettings.vue';
import WorldStateManagerSceneExport from './WorldStateManagerSceneExport.vue';
import WorldStateManagerSceneDirection from './WorldStateManagerSceneDirection.vue';
import GameState from './GameState.vue';
import WorldStateManagerSceneGameSystems from './WorldStateManagerSceneGameSystems.vue';
import WorldStateManagerSceneSharedWorld from './WorldStateManagerSceneSharedWorld.vue';
import { MAX_CONTENT_WIDTH } from '@/constants';

export default {
    name: "WorldStateManagerScene",
    components: {
        WorldStateManagerSceneOutline,
        WorldStateManagerSceneSettings,
        WorldStateManagerSceneExport,
        WorldStateManagerSceneDirection,
        GameState,
        WorldStateManagerSceneGameSystems,
        WorldStateManagerSceneSharedWorld,
    },
    props: {
        scene: Object,
        appConfig: Object,
        templates: Object,
        generationOptions: Object,
    },
    inject:[
        'getWebsocket',
        'registerMessageHandler',
        'unregisterMessageHandler',
        'setWaitingForInput',
        'requestSceneAssets',
    ],
    computed: {
        title() {
            if(!this.scene) {
                return "No Scene Selected";
            }
            return this.scene.title || this.scene.name;
        },
    },
    data() {
        return {
            selected: null,
            page: 'outline',
            MAX_CONTENT_WIDTH,
        }
    },
    methods:{
        refresh() {
            try {
                if (this.page === 'gamestate') {
                    this.$refs.gamestate?.refresh?.();
                } else if (this.page === 'primitives') {
                    this.$refs.primitives?.refresh?.();
                } else if (this.page === 'director') {
                    this.$refs.director?.getSceneIntent?.();
                } else if (this.page === 'shared') {
                    this.$refs.shared?.refresh?.();
                }
            } catch(e) {
                console.error('WorldStateManagerScene: refresh failed', e);
            }
        },
        navigate(page, anchor) {
            this.page = page;
            if (page === 'primitives' && anchor) {
                this.$nextTick(() => this.$refs.primitives?.focusAnchor?.(anchor));
            }
        },
        handleMessage(message) {
            return message;
        }
    },
    mounted(){
        this.registerMessageHandler(this.handleMessage);
    },
    unmounted(){
        this.unregisterMessageHandler(this.handleMessage);
    }
}

</script>

<style scoped>
.scene-manager, .scene-card, .scene-content, .scene-navigation { min-width: 0; max-width: 100%; }

@media (max-width: 700px) {
    .scene-content { padding-inline: 0.75rem; }
    .scene-navigation { overflow-x: auto; }
}
</style>
