<template>
    <v-dialog v-model="dialog" scrollable max-width="960px" max-height="90vh">
        <v-card v-if="app_config !== null">
            <v-card-title><v-icon class="mr-1">mdi-cog</v-icon>Settings</v-card-title>
            <v-tabs color="primary" v-model="tab">
                <v-tab value="game">
                    <v-icon start>mdi-gamepad-square</v-icon>
                    Game
                </v-tab>
                <v-tab value="appearance">
                    <v-icon start>mdi-palette-outline</v-icon>
                    Appearance
                </v-tab>
                <v-tab value="application">
                    <v-icon start>mdi-application</v-icon>
                    Application
                </v-tab>
                <v-tab value="presets">
                    <v-icon start>mdi-tune</v-icon>
                    Presets
                </v-tab>
                <v-tab value="creator">
                    <v-icon start>mdi-palette-outline</v-icon>
                    Creator
                </v-tab>
                <v-tab value="providers">
                    <v-icon start>mdi-cloud-outline</v-icon>
                    Providers
                </v-tab>
            </v-tabs>
            <v-divider></v-divider>
            <v-window v-model="tab">

                <!-- GAME -->

                <v-window-item value="game">
                    <v-card flat>
                        <v-card-text>
                            <v-row>
                                <v-col cols="4">
                                    <v-tabs v-model="gamePageSelected" color="primary" direction="vertical">
                                        <v-tab v-for="(item, index) in navigation.game" :key="index" :value="item.value">
                                            <v-icon class="mr-1">{{ item.icon }}</v-icon>
                                            {{ item.title }}
                                        </v-tab>
                                    </v-tabs>
                                </v-col>
                                <v-col cols="8">
                                    <div v-if="gamePageSelected === 'general'">
                                        <v-alert color="white" variant="text" icon="mdi-cog" density="compact">
                                            <v-alert-title>General</v-alert-title>
                                            <div class="text-grey">
                                                General game settings.
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-checkbox color="primary" v-model="app_config.game.general.auto_save" label="Auto save" messages="Automatically save after each game-loop"></v-checkbox>
                                                <v-checkbox color="primary" v-model="app_config.game.general.auto_progress" label="Auto progress" messages="AI automatically progresses after player turn."></v-checkbox>
                                            </v-col>
                                        </v-row>
                                        <v-row>
                                            <v-col cols="6">
                                                <v-text-field v-model="app_config.game.general.max_backscroll" type="number" label="Max backscroll" messages="Maximum number of messages to keep in the scene backscroll"></v-text-field>
                                            </v-col>
                                        </v-row>        
                                    </div>
                                    <div v-else-if="gamePageSelected === 'character'">
                                        <v-alert color="white" variant="text" icon="mdi-human-edit" density="compact">
                                            <v-alert-title>Default player character</v-alert-title>
                                            <div class="text-grey">
                                                This will be default player character that will be added to a scene if the scene does not come with a defined player character. Mostly relevant when you load character-cards that aren't in the talemate scene format.                 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="6">
                                                <v-text-field v-model="app_config.game.default_player_character.name"
                                                    label="Name"></v-text-field>
                                            </v-col>
                                            <v-col cols="6">
                                                <v-text-field v-model="app_config.game.default_player_character.gender"
                                                    label="Gender"></v-text-field>
                                            </v-col>
                                        </v-row>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-textarea v-model="app_config.game.default_player_character.description"
                                                    auto-grow label="Description"></v-textarea>
                                            </v-col>
                                        </v-row>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-checkbox color="primary" v-model="app_config.game.general.add_default_character" label="Add default character to blank talemate scenes" messages="When creating a new scene, add the default player character to the scene."></v-checkbox>
                                            </v-col>
                                        </v-row>
                                    </div>
                                </v-col>
                            </v-row>
                        </v-card-text>
                    </v-card>
                </v-window-item>

                <!-- APPEARANCE -->

                <v-window-item value="appearance">
                    <AppConfigAppearance 
                    ref="appearance"
                    :immutableConfig="app_config" 
                    :sceneActive="sceneActive"
                    ></AppConfigAppearance>
                </v-window-item>

                <!-- APPLICATION -->

                <v-window-item value="application">
                    <v-card flat>
                        <v-card-text>
                            <v-row>
                                <v-col cols="4">
                                    <v-list>
                                        <v-list-subheader>Third Party APIs</v-list-subheader>

                                        <v-tabs v-model="applicationPageSelected" color="primary" direction="vertical" density="compact">
                                            <v-tab v-for="(item, index) in navigation.application" :key="index" :value="item.value">
                                                <v-icon class="mr-1">{{ item.icon }}</v-icon>
                                                {{ item.title }}
                                            </v-tab>
                                        </v-tabs>
                                    </v-list>
                                </v-col>
                                <v-col cols="8">

                                    <!-- OPENAI API -->
                                    <div v-if="applicationPageSelected === 'openai_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>OpenAI</v-alert-title>
                                            <div class="text-grey">
                                                Configure your OpenAI API key here. You can get one from <a href="https://platform.openai.com/" target="_blank">https://platform.openai.com/</a> 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.openai.api_key"
                                                    label="OpenAI API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- MISTRAL.AI API -->
                                    <div v-if="applicationPageSelected === 'mistralai_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>mistral.ai</v-alert-title>
                                            <div class="text-grey">
                                                Configure your mistral.ai API key here. You can get one from <a href="https://console.mistral.ai/api-keys/" target="_blank">https://console.mistral.ai/api-keys/</a> 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.mistralai.api_key"
                                                    label="mistral.ai API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- ANTHROPIC API -->
                                    <div v-if="applicationPageSelected === 'anthropic_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>Anthropic</v-alert-title>
                                            <div class="text-grey">
                                                Configure your Anthropic API key here. You can get one from <a href="https://console.anthropic.com/settings/keys" target="_blank">https://console.anthropic.com/settings/keys</a> 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.anthropic.api_key"
                                                    label="Anthropic API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- COHERE API -->
                                    <div v-if="applicationPageSelected === 'cohere_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>Cohere</v-alert-title>
                                            <div class="text-grey">
                                                Configure your Cohere API key here. You can get one from <a href="https://dashboard.cohere.com/api-keys" target="_blank">https://dashboard.cohere.com/api-keys</a> 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.cohere.api_key"
                                                    label="Cohere API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- DEEPSEEK API -->
                                    <div v-if="applicationPageSelected === 'deepseek_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>DeepSeek</v-alert-title>
                                            <div class="text-grey">
                                                Configure your DeepSeek API key here. You can get one from <a href="https://platform.deepseek.com/" target="_blank">https://platform.deepseek.com/</a>
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.deepseek.api_key"
                                                    label="DeepSeek API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- OPENROUTER API -->
                                    <div v-if="applicationPageSelected === 'openrouter_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>OpenRouter</v-alert-title>
                                            <div class="text-grey">
                                                Configure your OpenRouter API key here. You can get one from <a href="https://openrouter.ai/api-keys" target="_blank">https://openrouter.ai/settings/keys</a> 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.openrouter.api_key"
                                                    label="OpenRouter API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- GROQ API -->
                                    <div v-if="applicationPageSelected === 'groq_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>groq</v-alert-title>
                                            <div class="text-grey">
                                                Configure your GROQ API key here. You can get one from <a href="https://console.groq.com/keys" target="_blank">https://console.groq.com/keys</a> 
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.groq.api_key"
                                                    label="GROQ API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- GOOGLE API
                                         THis adds fields for 
                                            gcloud_credentials_path
                                            gcloud_project_id
                                            gcloud_location
                                    -->

                                    <div v-if="applicationPageSelected === 'google_api'">
                                        <v-alert color="white" variant="text" icon="mdi-google-cloud" density="compact">
                                            <v-alert-title>Google</v-alert-title>
                                            <div class="text-grey">
                                                <p class="mb-2"><strong>Option&nbsp;1 – API&nbsp;Key&nbsp;(recommended)</strong></p>
                                                <p class="mb-1">Create a Google API key at <a href="https://aistudio.google.com/apikey" target="_blank">aistudio.google.com/apikey</a> and paste it in the field below. This is the quickest way to start using Gemini models.</p>

                                                <v-divider class="my-4"></v-divider>

                                                <p class="mb-2"><strong>Option&nbsp;2 – Vertex&nbsp;AI service&nbsp;account&nbsp;(advanced)</strong></p>
                                                <p class="mb-0">If you prefer using a full Google Cloud project, follow the setup guide <a href="https://cloud.google.com/vertex-ai/docs/start/client-libraries" target="_blank">here</a> to generate a service-account JSON credential file, then complete the legacy fields below.</p>

                                                <p class="text-caption mt-1 text-muted">
                                                    If both are setup, the API key will be used.
                                                </p>
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <!-- API KEY -->
                                        <v-row class="mb-4">
                                            <v-col cols="12">
                                                <v-text-field type="password"
                                                              v-model="app_config.google.api_key"
                                                              label="Google API Key"
                                                              messages="Paste your Google API key here. This is the easiest way to authenticate.">
                                                </v-text-field>
                                            </v-col>
                                        </v-row>
                                        <!-- Vertex AI (legacy) fields -->
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field v-model="app_config.google.gcloud_credentials_path"
                                                    label="Google Cloud Credentials Path" messages="Path to the service-account JSON credentials file on the machine running the Talemate backend."></v-text-field>
                                            </v-col>
                                            <v-col cols="6">
                                                <v-combobox v-model="app_config.google.gcloud_location"
                                                    label="Google Cloud Location" :items="googleCloudLocations" messages="Pick something close to you" :return-object="false"></v-combobox>
                                            </v-col>
                                        </v-row>
                                    </div>

                                    <!-- ELEVENLABS API -->
                                    <div v-if="applicationPageSelected === 'elevenlabs_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>ElevenLabs</v-alert-title>
                                            <div class="text-grey">
                                                <p class="mb-1">Generate realistic speech with the most advanced AI voice model ever.</p>
                                                Configure your ElevenLabs API key here. You can get one from <a href="https://elevenlabs.io/?from=partnerewing2048" target="_blank">https://elevenlabs.io</a> <span class="text-caption">(affiliate link)</span>
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.elevenlabs.api_key"
                                                    label="ElevenLabs API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>


                                    <!-- RUNPOD API -->
                                    <div v-if="applicationPageSelected === 'runpod_api'">
                                        <v-alert color="white" variant="text" icon="mdi-api" density="compact">
                                            <v-alert-title>RunPod</v-alert-title>
                                            <div class="text-grey">
                                                <p class="mb-1">Launch a GPU instance in seconds.</p>
                                                Configure your RunPod API key here. You can get one from <a href="https://runpod.io?ref=gma8kdu0" target="_blank">https://runpod.io/</a>  <span class="text-caption">(affiliate link)</span>
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-text-field type="password" v-model="app_config.runpod.api_key"
                                                    label="RunPod API Key"></v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>

                                </v-col>
                            </v-row>
                        </v-card-text>
                    </v-card>
                </v-window-item>

                <!-- PRESETS -->

                <v-window-item value="presets">
                    <AppConfigPresets 
                    ref="presets"
                    :immutable-config="app_config" 
                    :agentStatus="agentStatus"
                    :sceneActive="sceneActive"
                    :clientStatus="clientStatus"
                    ></AppConfigPresets>
                </v-window-item>

                <!-- CREATOR -->

                <v-window-item value="creator">
                    <v-card flat>
                        <v-card-text>
                            <v-row>
                                <v-col cols="4">
                                    <v-tabs v-model="creatorPageSelected" color="primary" direction="vertical">
                                        <v-tab v-for="(item, index) in navigation.creator" :key="index" :value="item.value">
                                            <v-icon class="mr-1">{{ item.icon }}</v-icon>
                                            {{ item.title }}
                                        </v-tab>
                                    </v-tabs>
                                </v-col>
                                <v-col cols="8">
                                    <div v-if="creatorPageSelected === 'content_context'">
                                        <!-- Content for Content context will go here -->
                                        <v-alert color="white" variant="text" icon="mdi-cube-scan" density="compact">
                                            <v-alert-title>Content context</v-alert-title>
                                            <div class="text-grey">
                                                Available content-context choices when generating characters or scenarios. This can strongly influence the content that is generated.
                                            </div>
                                        </v-alert>
                                        <v-divider class="mb-2"></v-divider>
                                        <v-row>
                                            <v-col cols="12">
                                                <v-list density="compact">
                                                    <v-list-item v-for="(value, index) in app_config.creator.content_context" :key="index">
                                                        <v-list-item-title><v-icon color="red-darken-1" class="mr-2" @click="contentContextRemove(index)">mdi-close-box-outline</v-icon>{{ value }}</v-list-item-title>
                                                    </v-list-item>
                                                </v-list>
                                                <v-divider></v-divider>
                                                <v-text-field v-model="content_context_input" label="Add content context (Press enter to add)"
                                                    @keyup.enter="app_config.creator.content_context.push(content_context_input); content_context_input = ''"></v-text-field>
                                            </v-col>
                                        </v-row>

                                        
                                    </div>
                                </v-col>
                            </v-row>
                        </v-card-text>
                    </v-card>
                </v-window-item>

                <!-- PROVIDERS -->

                <v-window-item value="providers">
                    <v-card flat>
                        <v-card-text style="max-height: 70vh; overflow-y: auto;">
                            <v-row>
                                <v-col cols="12">
                                    <v-alert color="white" variant="text" icon="mdi-cloud-outline" density="compact">
                                        <v-alert-title>LiteLLM Providers</v-alert-title>
                                        <div class="text-grey">
                                            Configure LiteLLM providers for unified AI model access.
                                        </div>
                                    </v-alert>
                                    
                                    <v-progress-linear v-if="loadingProviders" indeterminate color="primary" class="mb-4"></v-progress-linear>
                                    
                                    <div v-if="!loadingProviders && providers.length === 0" class="text-center py-8">
                                        <v-icon size="64" color="grey">mdi-cloud-off-outline</v-icon>
                                        <div class="text-h6 text-grey mt-2">No providers available</div>
                                        <div class="text-body-2 text-grey">LiteLLM providers are not configured</div>
                                    </div>
                                    
                                    <v-row v-if="!loadingProviders && providers.length > 0">
                                        <!-- Single Instance Providers -->
                                        <v-col cols="12" md="6" v-for="provider in getSingleInstanceProviders()" :key="provider.identifier">
                                            <v-card elevation="2" class="mb-4">
                                                <v-card-title class="d-flex align-center">
                                                    <v-icon class="mr-2">mdi-cloud</v-icon>
                                                    {{ provider.name }}
                                                    <v-spacer></v-spacer>
                                                    <v-chip size="small" color="primary">{{ provider.identifier }}</v-chip>
                                                </v-card-title>
                                                <v-card-text>
                                                    <div class="text-body-2 text-grey mb-3">
                                                        Configure {{ provider.name }} settings
                                                    </div>
                                                    
                                                    <v-form v-if="provider.settings_schema && providerSettings[provider.identifier]">
                                                        <!-- Basic/Required Settings -->
                                                        <div v-for="setting in getBasicSettings(provider.settings_schema)" :key="setting.key" class="mb-3">
                                                            <v-text-field
                                                                v-if="setting.type === 'text'"
                                                                v-model="providerSettings[provider.identifier][setting.key]"
                                                                :label="setting.label"
                                                                :hint="setting.description"
                                                                :required="setting.required"
                                                                density="compact"
                                                                variant="outlined"
                                                                persistent-hint
                                                            ></v-text-field>
                                                            
                                                            <v-text-field
                                                                v-else-if="setting.type === 'password'"
                                                                v-model="providerSettings[provider.identifier][setting.key]"
                                                                :label="setting.label"
                                                                :hint="setting.description"
                                                                :required="setting.required"
                                                                type="password"
                                                                density="compact"
                                                                variant="outlined"
                                                                persistent-hint
                                                            ></v-text-field>
                                                            
                                                            <v-text-field
                                                                v-else-if="setting.type === 'number'"
                                                                v-model.number="providerSettings[provider.identifier][setting.key]"
                                                                :label="setting.label"
                                                                :hint="setting.description"
                                                                :required="setting.required"
                                                                type="number"
                                                                density="compact"
                                                                variant="outlined"
                                                                persistent-hint
                                                            ></v-text-field>
                                                            
                                                            <v-switch
                                                                v-else-if="setting.type === 'boolean'"
                                                                v-model="providerSettings[provider.identifier][setting.key]"
                                                                :label="setting.label"
                                                                :hint="setting.description"
                                                                density="compact"
                                                                color="primary"
                                                                persistent-hint
                                                            ></v-switch>
                                                            
                                                            <v-select
                                                                v-else-if="setting.type === 'select'"
                                                                v-model="providerSettings[provider.identifier][setting.key]"
                                                                :label="setting.label"
                                                                :hint="setting.description"
                                                                :items="setting.options"
                                                                :required="setting.required"
                                                                density="compact"
                                                                variant="outlined"
                                                                persistent-hint
                                                            ></v-select>
                                                        </div>
                                                        
                                                        <!-- Advanced Settings Toggle -->
                                                        <div v-if="getAdvancedSettings(provider.settings_schema).length > 0" class="mb-3">
                                                            <v-btn
                                                                @click="toggleAdvanced(provider.identifier)"
                                                                variant="text"
                                                                size="small"
                                                                :prepend-icon="showAdvanced[provider.identifier] ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                                                                color="primary"
                                                            >
                                                                {{ showAdvanced[provider.identifier] ? 'Hide' : 'Show' }} Advanced Settings
                                                            </v-btn>
                                                        </div>
                                                        
                                                        <!-- Advanced Settings -->
                                                        <v-expand-transition>
                                                            <div v-if="showAdvanced[provider.identifier]">
                                                                <div v-for="setting in getAdvancedSettings(provider.settings_schema)" :key="setting.key" class="mb-3">
                                                                    <v-text-field
                                                                        v-if="setting.type === 'text'"
                                                                        v-model="providerSettings[provider.identifier][setting.key]"
                                                                        :label="setting.label"
                                                                        :hint="setting.description"
                                                                        :required="setting.required"
                                                                        density="compact"
                                                                        variant="outlined"
                                                                        persistent-hint
                                                                    ></v-text-field>
                                                                    
                                                                    <v-text-field
                                                                        v-else-if="setting.type === 'password'"
                                                                        v-model="providerSettings[provider.identifier][setting.key]"
                                                                        :label="setting.label"
                                                                        :hint="setting.description"
                                                                        :required="setting.required"
                                                                        type="password"
                                                                        density="compact"
                                                                        variant="outlined"
                                                                        persistent-hint
                                                                    ></v-text-field>
                                                                    
                                                                    <v-text-field
                                                                        v-else-if="setting.type === 'number'"
                                                                        v-model.number="providerSettings[provider.identifier][setting.key]"
                                                                        :label="setting.label"
                                                                        :hint="setting.description"
                                                                        :required="setting.required"
                                                                        type="number"
                                                                        density="compact"
                                                                        variant="outlined"
                                                                        persistent-hint
                                                                    ></v-text-field>
                                                                    
                                                                    <v-switch
                                                                        v-else-if="setting.type === 'boolean'"
                                                                        v-model="providerSettings[provider.identifier][setting.key]"
                                                                        :label="setting.label"
                                                                        :hint="setting.description"
                                                                        density="compact"
                                                                        color="primary"
                                                                        persistent-hint
                                                                    ></v-switch>
                                                                    
                                                                    <v-select
                                                                        v-else-if="setting.type === 'select'"
                                                                        v-model="providerSettings[provider.identifier][setting.key]"
                                                                        :label="setting.label"
                                                                        :hint="setting.description"
                                                                        :items="setting.options"
                                                                        :required="setting.required"
                                                                        density="compact"
                                                                        variant="outlined"
                                                                        persistent-hint
                                                                    ></v-select>
                                                                </div>
                                                            </div>
                                                        </v-expand-transition>
                                                    </v-form>
                                                </v-card-text>
                                                <v-card-actions>
                                                    <v-spacer></v-spacer>
                                                    <v-btn 
                                                        color="primary" 
                                                        variant="outlined" 
                                                        size="small"
                                                        @click="saveProviderSettings(provider.identifier)"
                                                    >
                                                        Save Settings
                                                    </v-btn>
                                                </v-card-actions>
                                            </v-card>
                                        </v-col>
                                        
                                        <!-- Multi-Instance Providers -->
                                        <v-col cols="12" v-for="provider in getMultiInstanceProviders()" :key="provider.identifier">
                                            <v-card elevation="2" class="mb-4">
                                                <v-card-title class="d-flex align-center">
                                                    <v-icon class="mr-2">mdi-cloud-plus</v-icon>
                                                    {{ provider.name }}
                                                    <v-spacer></v-spacer>
                                                    <v-chip size="small" color="secondary">Multi-Instance</v-chip>
                                                </v-card-title>
                                                <v-card-text>
                                                    <div class="text-body-2 text-grey mb-3">
                                                        Create multiple instances of {{ provider.name }} with different configurations
                                                    </div>
                                                    
                                                    <!-- Existing Instances -->
                                                    <div v-if="getProviderInstances(provider.identifier).length > 0" class="mb-4">
                                                        <h4 class="text-subtitle-2 text-grey mb-2">Existing Instances</h4>
                                                        <v-card 
                                                            v-for="instance in getProviderInstances(provider.identifier)" 
                                                            :key="instance.id"
                                                            elevation="1" 
                                                            class="mb-2"
                                                        >
                                                            <v-card-title class="d-flex align-center py-2">
                                                                <v-icon size="small" class="mr-2">mdi-server</v-icon>
                                                                <span class="font-weight-regular">{{ instance.name || instance.id }}</span>
                                                                <v-spacer></v-spacer>
                                                                <v-btn
                                                                    @click="editProviderInstance(provider.identifier, instance.id)"
                                                                    size="small"
                                                                    variant="text"
                                                                    icon="mdi-pencil"
                                                                ></v-btn>
                                                                <v-btn
                                                                    @click="deleteProviderInstance(provider.identifier, instance.id)"
                                                                    size="small"
                                                                    variant="text"
                                                                    icon="mdi-delete"
                                                                    color="error"
                                                                ></v-btn>
                                                            </v-card-title>
                                                        </v-card>
                                                    </div>
                                                </v-card-text>
                                                <v-card-actions>
                                                    <v-btn
                                                        @click="addProviderInstance(provider.identifier)"
                                                        color="primary"
                                                        variant="outlined"
                                                        prepend-icon="mdi-plus"
                                                    >
                                                        Add Instance
                                                    </v-btn>
                                                </v-card-actions>
                                            </v-card>
                                        </v-col>
                                    </v-row>
                                </v-col>
                            </v-row>
                        </v-card-text>
                    </v-card>
                </v-window-item>
            </v-window>
            
            <!-- Instance Edit Dialog -->
            <v-dialog v-model="instanceEditDialog" max-width="600px">
                <v-card v-if="editingInstance">
                    <v-card-title>
                        <v-icon class="mr-2">mdi-cloud-edit</v-icon>
                        {{ editingInstance.isNew ? 'Add' : 'Edit' }} {{ editingInstance.providerName }} Instance
                    </v-card-title>
                    <v-card-text>
                        <v-form v-if="editingInstance.schema">
                            <!-- Basic Settings -->
                            <div v-for="setting in getBasicSettings(editingInstance.schema)" :key="setting.key" class="mb-3">
                                <v-text-field
                                    v-if="setting.type === 'text'"
                                    v-model="editingInstance.settings[setting.key]"
                                    :label="setting.label"
                                    :hint="setting.description"
                                    :required="setting.required"
                                    density="compact"
                                    variant="outlined"
                                    persistent-hint
                                ></v-text-field>
                                
                                <v-text-field
                                    v-else-if="setting.type === 'password'"
                                    v-model="editingInstance.settings[setting.key]"
                                    :label="setting.label"
                                    :hint="setting.description"
                                    :required="setting.required"
                                    type="password"
                                    density="compact"
                                    variant="outlined"
                                    persistent-hint
                                ></v-text-field>
                                
                                <v-text-field
                                    v-else-if="setting.type === 'number'"
                                    v-model.number="editingInstance.settings[setting.key]"
                                    :label="setting.label"
                                    :hint="setting.description"
                                    :required="setting.required"
                                    type="number"
                                    density="compact"
                                    variant="outlined"
                                    persistent-hint
                                ></v-text-field>
                            </div>
                            
                            <!-- Advanced Settings Toggle -->
                            <div v-if="getAdvancedSettings(editingInstance.schema).length > 0" class="mb-3">
                                <v-btn
                                    @click="editingInstance.showAdvanced = !editingInstance.showAdvanced"
                                    variant="text"
                                    size="small"
                                    :prepend-icon="editingInstance.showAdvanced ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                                    color="primary"
                                >
                                    {{ editingInstance.showAdvanced ? 'Hide' : 'Show' }} Advanced Settings
                                </v-btn>
                            </div>
                            
                            <!-- Advanced Settings -->
                            <v-expand-transition>
                                <div v-if="editingInstance.showAdvanced">
                                    <div v-for="setting in getAdvancedSettings(editingInstance.schema)" :key="setting.key" class="mb-3">
                                        <v-text-field
                                            v-if="setting.type === 'text'"
                                            v-model="editingInstance.settings[setting.key]"
                                            :label="setting.label"
                                            :hint="setting.description"
                                            :required="setting.required"
                                            density="compact"
                                            variant="outlined"
                                            persistent-hint
                                        ></v-text-field>
                                        
                                        <v-text-field
                                            v-else-if="setting.type === 'number'"
                                            v-model.number="editingInstance.settings[setting.key]"
                                            :label="setting.label"
                                            :hint="setting.description"
                                            :required="setting.required"
                                            type="number"
                                            density="compact"
                                            variant="outlined"
                                            persistent-hint
                                        ></v-text-field>
                                    </div>
                                </div>
                            </v-expand-transition>
                        </v-form>
                    </v-card-text>
                    <v-card-actions>
                        <v-spacer></v-spacer>
                        <v-btn @click="cancelInstanceEdit" variant="text">Cancel</v-btn>
                        <v-btn @click="saveInstanceEdit" color="primary">Save</v-btn>
                    </v-card-actions>
                </v-card>
            </v-dialog>
            
            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn color="primary" text @click="saveConfig" prepend-icon="mdi-check-circle-outline">Save</v-btn>
            </v-card-actions>
        </v-card>
        <v-card v-else>
            <v-card-title>
                <span class="headline">Configuration</span>
            </v-card-title>
            <v-card-text>
                <v-progress-circular indeterminate="disable-shrink" color="primary" size="20"></v-progress-circular>
            </v-card-text>
        </v-card>
    </v-dialog>
</template>
<script>

import AppConfigPresets from './AppConfigPresets.vue';
import AppConfigAppearance from './AppConfigAppearance.vue';

export default {
    name: 'AppConfig',
    components: {
        AppConfigPresets,
        AppConfigAppearance,
    },
    props: {
        agentStatus: Object,
        sceneActive: Boolean,
        clientStatus: Object,
    },
    data() {
        return {
            tab: 'game',
            dialog: false,
            app_config: null,
            content_context_input: '',
            navigation: {
                game: [
                    {title: 'General', icon: 'mdi-cog', value: 'general'},
                    {title: 'Default Character', icon: 'mdi-human-edit', value: 'character'},
                ],
                appearance: [
                    {title: 'Scene', icon: 'mdi-script-text', value: 'scene'},
                ],
                application: [
                    {title: 'Anthropic', icon: 'mdi-api', value: 'anthropic_api'},
                    {title: 'Cohere', icon: 'mdi-api', value: 'cohere_api'},
                    {title: 'DeepSeek', icon: 'mdi-api', value: 'deepseek_api'},
                    {title: 'ElevenLabs', icon: 'mdi-api', value: 'elevenlabs_api'},
                    {title: 'Google', icon: 'mdi-api', value: 'google_api'},
                    {title: 'groq', icon: 'mdi-api', value: 'groq_api'},
                    {title: 'mistral.ai', icon: 'mdi-api', value: 'mistralai_api'},
                    {title: 'OpenAI', icon: 'mdi-api', value: 'openai_api'},
                    {title: 'OpenRouter', icon: 'mdi-api', value: 'openrouter_api'},
                    {title: 'RunPod', icon: 'mdi-api', value: 'runpod_api'},
                ],
                creator: [
                    {title: 'Content Context', icon: 'mdi-cube-scan', value: 'content_context'},
                ]
            },
            gamePageSelected: 'general',
            applicationPageSelected: 'openai_api',
            creatorPageSelected: 'content_context',
            // Provider-related data
            providers: [],
            loadingProviders: false,
            providerSettings: {},
            showAdvanced: {},
            providerInstances: {}, // For multi-instance providers
            editingInstance: null, // Currently editing instance
            instanceEditDialog: false, // Instance edit dialog visibility
            googleCloudLocations: [
                {"value": 'us-central1', "title": 'US Central - Iowa'},
                {"value": 'us-west4', "title": 'US West 4 - Las Vegas'},
                {"value": 'us-east1', "title": 'US East 1 - South Carolina'},
                {"value": 'us-east4', "title": 'US East 4 - Northern Virginia'},
                {"value": 'us-west1', "title": 'US West 1 - Oregon'},
                {"value": 'northamerica-northeast1', "title": 'North America Northeast 1 - Montreal'},
                {"value": 'southamerica-east1', "title": 'South America East 1 - Sao Paulo'},
                {"value": 'europe-west1', "title": 'Europe West 1 - Belgium'},
                {"value": 'europe-north1', "title": 'Europe North 1 - Finland'},
                {"value": 'europe-west3', "title": 'Europe West 3 - Frankfurt'},
                {"value": 'europe-west2', "title": 'Europe West 2 - London'},
                {"value": 'europe-southwest1', "title": 'Europe Southwest 1 - Zurich'},
                {"value": 'europe-west8', "title": 'Europe West 8 - Netherlands'},
                {"value": 'europe-west4', "title": 'Europe West 4 - London'},
                {"value": 'europe-west9', "title": 'Europe West 9 - Stockholm'},
                {"value": 'europe-central2', "title": 'Europe Central 2 - Warsaw'},
                {"value": 'europe-west6', "title": 'Europe West 6 - Zurich'},
                {"value": 'asia-east1', "title": 'Asia East 1 - Taiwan'},
                {"value": 'asia-east2', "title": 'Asia East 2 - Hong Kong'},
                {"value": 'asia-south1', "title": 'Asia South 1 - Mumbai'},
                {"value": 'asia-northeast1', "title": 'Asia Northeast 1 - Tokyo'},
                {"value": 'asia-northeast3', "title": 'Asia Northeast 3 - Seoul'},
                {"value": 'asia-southeast1', "title": 'Asia Southeast 1 - Singapore'},
                {"value": 'asia-southeast2', "title": 'Asia Southeast 2 - Jakarta'},
                {"value": 'australia-southeast1', "title": 'Australia Southeast 1 - Sydney'},
                {"value": 'australia-southeast2', "title": 'Australia Southeast 2 - Melbourne'},
                {"value": 'me-west1', "title": 'Middle East West 1 - Dammam'},
                {"value": 'asia-northeast2', "title": 'Asia Northeast 2 - Osaka'},
                {"value": 'asia-northeast3', "title": 'Asia Northeast 3 - Seoul'},
                {"value": 'asia-south1', "title": 'Asia South 1 - Mumbai'},
                {"value": 'asia-southeast1', "title": 'Asia Southeast 1 - Singapore'},
                {"value": 'asia-southeast2', "title": 'Asia Southeast 2 - Jakarta'}
            ].sort((a, b) => a.title.localeCompare(b.title))
        }
    },
    inject: ['getWebsocket', 'registerMessageHandler', 'setWaitingForInput', 'requestSceneAssets', 'requestAppConfig'],

    methods: {
        show(tab, page, item) {
            this.requestAppConfig();
            this.dialog = true;
            if(tab) {
                this.tab = tab;
                if(page) {
                    if(this[tab + 'PageSelected'] !== undefined) {
                        this[tab + 'PageSelected'] = page;
                    } else {
                        this.$nextTick(() => {
                            console.log("SETTING SELECTION", {tab, page, item});

                            if(this.$refs[tab] && this.$refs[tab].setSelection) {
                                this.$refs[tab].setSelection(page);
                            
                                this.$nextTick(() => {
                                    if(item && this.$refs[tab].$refs[page] && this.$refs[tab].$refs[page].setSelection) {
                                        this.$refs[tab].$refs[page].setSelection(item);
                                    }
                                });
                            }

                            
                        })
                    }
                }
            }
        },
        exit() {
            this.dialog = false
        },

        contentContextRemove(index) {
            this.app_config.creator.content_context.splice(index, 1);
        },

        handleMessage(message) {
            if (message.type == "app_config") {
                this.app_config = message.data;
                return;
            }

            if (message.type == 'config') {
                if (message.action == 'save_complete') {
                    this.exit();
                } else if (message.action == 'litellm_providers') {
                    this.handleProvidersMessage(message);
                } else if (message.action == 'provider_save_complete') {
                    console.log('Provider settings saved:', message.data);
                    // Could show a toast/snackbar here
                } else if (message.action == 'provider_save_error') {
                    console.error('Provider save error:', message.data);
                    // Could show error toast/snackbar here
                } else if (message.action == 'provider_instance_save_complete') {
                    console.log('Provider instance saved:', message.data);
                    // Could show a toast/snackbar here
                } else if (message.action == 'provider_instance_save_error') {
                    console.error('Provider instance save error:', message.data);
                    // Could show error toast/snackbar here
                } else if (message.action == 'provider_instance_delete_complete') {
                    console.log('Provider instance deleted:', message.data);
                    // Could show a toast/snackbar here
                } else if (message.action == 'provider_instance_delete_error') {
                    console.error('Provider instance delete error:', message.data);
                    // Could show error toast/snackbar here
                }
            }
        },

        sendRequest(data) {
            data.type = 'config';
            this.getWebsocket().send(JSON.stringify(data));
        },

        saveConfig() {

            // check if presets component is present
            if(this.$refs.presets) {
                // update app_config.presets from $refs.presets.config

                let inferenceConfig = this.$refs.presets.inference_config();
                let inferenceGroupsConfig = this.$refs.presets.inference_groups_config();
                let embeddingsConfig = this.$refs.presets.embeddings_config();
                let systemPromptsConfig = this.$refs.presets.system_prompts_config();

                if(inferenceConfig) {
                    this.app_config.presets.inference = inferenceConfig;
                }

                if(inferenceGroupsConfig) {
                    this.app_config.presets.inference_groups = inferenceGroupsConfig;
                }

                if(embeddingsConfig) {
                    this.app_config.presets.embeddings = embeddingsConfig;
                }

                if(systemPromptsConfig) {
                    this.app_config.system_prompts = systemPromptsConfig;
                }

            }

            // check if appearance component is present
            if(this.$refs.appearance) {
                // update app_config.appearance from $refs.appearance.config
                this.app_config.appearance = this.$refs.appearance.get_config();
            }

            console.log("SAVING", this.app_config);

            this.sendRequest({
                action: 'save',
                config: this.app_config,
            })
        },
        
        // Provider-related methods
        requestProviders() {
            this.loadingProviders = true;
            this.sendRequest({
                action: 'request_litellm_providers'
            });
        },
        
        saveProviderSettings(providerId) {
            const settings = this.providerSettings[providerId];
            console.log('Saving provider settings', { providerId, settings });
            
            // TODO: Send provider settings to backend
            this.sendRequest({
                action: 'save_provider_settings',
                provider_id: providerId,
                settings: settings
            });
        },
        
        initializeProviderSettings() {
            // Initialize settings object for each provider
            this.providers.forEach(provider => {
                if (provider.multi_instance) {
                    // Load instances for multi-instance providers
                    this.providerInstances[provider.identifier] = provider.instances || [];
                } else {
                    // Initialize single-instance provider settings
                    if (!this.providerSettings[provider.identifier]) {
                        const providerDefaults = {};
                        
                        // Set values from saved settings first, then defaults
                        provider.settings_schema.forEach(setting => {
                            // Check if there's a saved value for this setting
                            if (provider.saved_settings && provider.saved_settings[setting.key] !== undefined) {
                                providerDefaults[setting.key] = provider.saved_settings[setting.key];
                            } else if (setting.default !== null && setting.default !== undefined) {
                                providerDefaults[setting.key] = setting.default;
                            } else {
                                providerDefaults[setting.key] = '';
                            }
                        });
                        
                        this.providerSettings[provider.identifier] = providerDefaults;
                    }
                }
                
                // Initialize advanced settings visibility
                if (this.showAdvanced[provider.identifier] === undefined) {
                    this.showAdvanced[provider.identifier] = false;
                }
            });
        },
        
        handleProvidersMessage(data) {
            if (data.action === 'litellm_providers') {
                this.providers = data.data;
                this.loadingProviders = false;
                this.initializeProviderSettings();
            }
        },
        
        getBasicSettings(settings) {
            return settings.filter(setting => !setting.advanced && !setting.hidden);
        },
        
        getAdvancedSettings(settings) {
            return settings.filter(setting => setting.advanced && !setting.hidden);
        },
        
        toggleAdvanced(providerId) {
            const current = this.showAdvanced[providerId] || false;
            this.showAdvanced[providerId] = !current;
        },
        
        getSingleInstanceProviders() {
            return this.providers.filter(provider => !provider.multi_instance);
        },
        
        getMultiInstanceProviders() {
            return this.providers.filter(provider => provider.multi_instance);
        },
        
        getProviderInstances(providerId) {
            return this.providerInstances[providerId] || [];
        },
        
        addProviderInstance(providerId) {
            const provider = this.providers.find(p => p.identifier === providerId);
            if (!provider) return;
            
            const instanceId = `${providerId}_${Date.now()}`;
            const newInstance = {
                id: instanceId,
                name: '',
                settings: {}
            };
            
            // Initialize with defaults
            provider.settings_schema.forEach(setting => {
                if (setting.default !== null && setting.default !== undefined) {
                    newInstance.settings[setting.key] = setting.default;
                } else {
                    newInstance.settings[setting.key] = '';
                }
            });
            
            // Open edit dialog for the new instance
            this.editingInstance = {
                providerId: providerId,
                providerName: provider.name,
                instanceId: instanceId,
                instance: newInstance,
                settings: { ...newInstance.settings },
                schema: provider.settings_schema,
                isNew: true,
                showAdvanced: false
            };
            this.instanceEditDialog = true;
        },
        
        editProviderInstance(providerId, instanceId) {
            const provider = this.providers.find(p => p.identifier === providerId);
            const instance = this.providerInstances[providerId]?.find(inst => inst.id === instanceId);
            
            if (!provider || !instance) return;
            
            this.editingInstance = {
                providerId: providerId,
                providerName: provider.name,
                instanceId: instanceId,
                instance: instance,
                settings: { ...instance.settings },
                schema: provider.settings_schema,
                isNew: false,
                showAdvanced: false
            };
            this.instanceEditDialog = true;
        },
        
        deleteProviderInstance(providerId, instanceId) {
            if (!this.providerInstances[providerId]) return;
            
            // Send delete request to backend
            this.sendRequest({
                action: 'delete_provider_instance',
                provider_id: providerId,
                instance_id: instanceId
            });
            
            // Remove from frontend immediately (optimistic update)
            const index = this.providerInstances[providerId].findIndex(instance => instance.id === instanceId);
            if (index !== -1) {
                this.providerInstances[providerId].splice(index, 1);
            }
        },
        
        saveInstanceEdit() {
            if (!this.editingInstance) return;
            
            const { providerId, instanceId, settings, isNew, instance } = this.editingInstance;
            
            // Update the instance settings
            instance.settings = { ...settings };
            instance.name = settings.instance_name || instanceId;
            
            if (isNew) {
                // Add to instances array
                if (!this.providerInstances[providerId]) {
                    this.providerInstances[providerId] = [];
                }
                this.providerInstances[providerId].push(instance);
            }
            
            // Save to backend
            this.sendRequest({
                action: 'save_provider_instance',
                provider_id: providerId,
                instance_id: instanceId,
                settings: settings
            });
            
            this.cancelInstanceEdit();
        },
        
        cancelInstanceEdit() {
            this.editingInstance = null;
            this.instanceEditDialog = false;
        },

    },
    watch: {
        tab(newTab) {
            if (newTab === 'providers' && this.providers.length === 0 && !this.loadingProviders) {
                this.requestProviders();
            }
        }
    },
    created() {
        this.registerMessageHandler(this.handleMessage);
    },

}

</script>

<style scoped></style>