<template>
  <v-dialog v-model="dialog" scrollable max-width="1200px">
    <v-card>
      <v-card-title>
        <v-icon class="mr-1">mdi-robot</v-icon>
        Model Browser
      </v-card-title>
      
      <v-card-text>
        <v-row>
          <v-col cols="12" class="pb-0">
            <v-text-field
              v-model="searchQuery"
              prepend-inner-icon="mdi-magnify"
              label="Search models..."
              clearable
              density="compact"
              variant="outlined"
              hide-details
            ></v-text-field>
          </v-col>
        </v-row>
        
        <v-row v-if="loading" class="justify-center">
          <v-col cols="auto" class="text-center pa-8">
            <v-progress-circular indeterminate size="64" color="primary"></v-progress-circular>
            <div class="text-h6 mt-4">Discovering available models...</div>
          </v-col>
        </v-row>
        
        <v-row v-else-if="error" class="justify-center">
          <v-col cols="12" md="6" class="pa-4">
            <v-alert type="error" variant="elevated" prominent>
              <v-alert-title>Error Loading Models</v-alert-title>
              {{ error }}
            </v-alert>
          </v-col>
        </v-row>
        
        <v-row v-else class="mt-4">
          <v-col cols="12">
            <v-expansion-panels v-model="expandedPanels" multiple>
              <v-expansion-panel
                v-for="(group, index) in filteredModelGroups"
                :key="group.provider_id"
                :value="index"
                elevation="2"
                class="mb-2"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center w-100">
                    <v-icon class="mr-2">{{ getProviderIcon(group.provider_name) }}</v-icon>
                    <span class="text-h6">{{ group.provider_name }}</span>
                    <v-spacer></v-spacer>
                    <v-chip size="small" color="secondary" class="mr-2">{{ group.models.length }} models</v-chip>
                  </div>
                </v-expansion-panel-title>
                
                <v-expansion-panel-text>
                  <v-list density="compact" class="pa-0">
                    <v-list-item
                      v-for="model in group.models"
                      :key="model.full_name"
                      @click="selectModel(model, group)"
                      :ripple="true"
                      class="model-list-item mb-1"
                    >
                      <template v-slot:prepend>
                        <v-icon size="small">mdi-language-markdown-outline</v-icon>
                      </template>
                      
                      <v-list-item-title>
                        {{ model.display_name || model.name }}
                      </v-list-item-title>
                      
                      <v-list-item-subtitle>
                        <div v-if="hasCapabilities(model)" class="d-flex flex-wrap gap-1 mt-1">
                          <v-chip 
                            v-if="model.capabilities.vision" 
                            size="x-small" 
                            variant="tonal"
                          >
                            <v-icon start size="x-small">mdi-eye</v-icon>
                            Vision
                          </v-chip>
                          <v-chip 
                            v-if="model.capabilities.reasoning" 
                            size="x-small" 
                            variant="tonal"
                          >
                            <v-icon start size="x-small">mdi-brain</v-icon>
                            Reasoning
                          </v-chip>
                          <v-chip 
                            v-if="model.capabilities.function_calling" 
                            size="x-small" 
                            variant="tonal"
                          >
                            <v-icon start size="x-small">mdi-function</v-icon>
                            Functions
                          </v-chip>
                          <v-chip 
                            v-if="model.capabilities.web_search" 
                            size="x-small" 
                            variant="tonal"
                          >
                            <v-icon start size="x-small">mdi-web</v-icon>
                            Search
                          </v-chip>
                        </div>
                        <span v-else class="text-caption text-grey">
                          Standard text model
                        </span>
                      </v-list-item-subtitle>
                      
                      <template v-slot:append>
                        <v-icon size="small">mdi-chevron-right</v-icon>
                      </template>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
    
    <!-- Model Configuration Dialog -->
    <v-dialog v-model="configDialog" max-width="800px">
      <v-card>
        <v-card-title>
          <v-icon class="mr-1">mdi-cog</v-icon>
          Configure Model
        </v-card-title>
        
        <v-card-text v-if="selectedModel" class="pa-4">
          <v-alert color="white" variant="text" icon="mdi-robot" density="compact" class="mb-4">
            <v-alert-title>{{ selectedModel.display_name || selectedModel.name }}</v-alert-title>
            <div class="text-grey">
              {{ selectedProvider.provider_name }} • {{ selectedModel.name }}
            </div>
          </v-alert>
          
          <v-divider class="mb-4"></v-divider>
          
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="configName"
                label="Configuration Name"
                density="compact"
                variant="outlined"
                placeholder="e.g., Creative Writing, Code Assistant"
                persistent-hint
                hint="Give this configuration a memorable name"
              ></v-text-field>
            </v-col>
          </v-row>
          
          <!-- Primary Controls (Sliders) -->
          <div v-if="getParametersByType('slider').length > 0">
            <h4 class="text-subtitle-2 text-grey mb-3 mt-4">
              <v-icon size="small" class="mr-1">mdi-tune</v-icon>
              Primary Controls
            </h4>
            <v-row>
              <v-col 
                v-for="param in getParametersByType('slider')" 
                :key="param"
                cols="12"
                class="mb-3"
              >
                <div class="d-flex align-center mb-2">
                  <span class="text-body-2 mr-2">{{ getParamConfig(param).label }}</span>
                  <v-spacer></v-spacer>
                  <v-chip size="small" variant="tonal">{{ modelConfig[param] }}</v-chip>
                </div>
                <v-slider
                  v-model="modelConfig[param]"
                  :min="getParamConfig(param).min"
                  :max="getParamConfig(param).max"
                  :step="getParamConfig(param).step"
                  :hint="getParamConfig(param).hint"
                  persistent-hint
                  color="primary"
                ></v-slider>
              </v-col>
            </v-row>
          </div>
          
          <!-- Generation Settings -->
          <div v-if="getParametersByCategory('generation').length > 0">
            <h4 class="text-subtitle-2 text-grey mb-3 mt-4">
              <v-icon size="small" class="mr-1">mdi-text-box-outline</v-icon>
              Generation Settings
            </h4>
            <v-row>
              <v-col 
                v-for="param in getParametersByCategory('generation')" 
                :key="param"
                cols="6"
                class="mb-2"
              >
                <v-text-field
                  v-if="getParamConfig(param).type === 'number'"
                  v-model.number="modelConfig[param]"
                  type="number"
                  :label="getParamConfig(param).label"
                  :hint="getParamConfig(param).hint"
                  :min="getParamConfig(param).min"
                  :max="getParamConfig(param).max"
                  density="compact"
                  variant="outlined"
                  persistent-hint
                ></v-text-field>
                
                <v-select
                  v-else-if="getParamConfig(param).type === 'select'"
                  v-model="modelConfig[param]"
                  :label="getParamConfig(param).label"
                  :hint="getParamConfig(param).hint"
                  :items="getParamConfig(param).options"
                  density="compact"
                  variant="outlined"
                  persistent-hint
                  hide-details="auto"
                ></v-select>
              </v-col>
            </v-row>
          </div>
          
          <!-- Advanced Settings -->
          <v-expansion-panels v-if="hasAdvancedSettings()" class="mt-4">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon size="small" class="mr-2">mdi-cog-outline</v-icon>
                Advanced Settings
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-row class="mt-2">
                  <v-col 
                    v-for="param in getAdvancedParameters()" 
                    :key="param"
                    :cols="getAdvancedParamCols(param)"
                    class="mb-2"
                  >
                    <!-- Switch parameters -->
                    <v-switch
                      v-if="getParamConfig(param).type === 'switch'"
                      v-model="modelConfig[param]"
                      :label="getParamConfig(param).label"
                      :hint="getParamConfig(param).hint"
                      density="compact"
                      color="primary"
                      persistent-hint
                    ></v-switch>
                    
                    <!-- JSON parameters -->
                    <v-textarea
                      v-else-if="getParamConfig(param).type === 'json'"
                      :modelValue="getJsonString(modelConfig[param])"
                      @update:modelValue="updateJsonParam(param, $event)"
                      :label="getParamConfig(param).label"
                      :hint="getParamConfig(param).hint"
                      density="compact"
                      variant="outlined"
                      persistent-hint
                      rows="3"
                      :rules="[validateJson]"
                    ></v-textarea>
                    
                    <!-- Chips parameters (for arrays like stop sequences) -->
                    <div v-else-if="getParamConfig(param).type === 'chips'">
                      <v-label class="text-body-2 mb-2">{{ getParamConfig(param).label }}</v-label>
                      <v-chip-group
                        v-model="modelConfig[param]"
                        column
                        multiple
                      >
                        <v-chip
                          v-for="(chip, index) in modelConfig[param] || []"
                          :key="index"
                          closable
                          @click:close="removeChip(param, index)"
                        >
                          {{ chip }}
                        </v-chip>
                      </v-chip-group>
                      <v-text-field
                        v-model="chipInput[param]"
                        :hint="getParamConfig(param).hint"
                        density="compact"
                        variant="outlined"
                        persistent-hint
                        @keyup.enter="addChip(param)"
                        placeholder="Press enter to add"
                      ></v-text-field>
                    </div>
                    
                    <!-- Default text parameters -->
                    <v-text-field
                      v-else
                      v-model="modelConfig[param]"
                      :label="getParamConfig(param).label"
                      :hint="getParamConfig(param).hint"
                      density="compact"
                      variant="outlined"
                      persistent-hint
                    ></v-text-field>
                  </v-col>
                </v-row>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
          
          <!-- Unknown Parameters -->
          <v-expansion-panels v-if="getUnknownParameters().length > 0" class="mt-2">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon size="small" class="mr-2">mdi-help-circle-outline</v-icon>
                Additional Parameters ({{ getUnknownParameters().length }})
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-row class="mt-2">
                  <v-col 
                    v-for="param in getUnknownParameters()" 
                    :key="param"
                    cols="6"
                    class="mb-2"
                  >
                    <v-text-field
                      v-model="modelConfig[param]"
                      :label="getParamConfig(param).label"
                      :hint="getParamConfig(param).hint"
                      density="compact"
                      variant="outlined"
                      persistent-hint
                    ></v-text-field>
                  </v-col>
                </v-row>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
        
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="configDialog = false">Cancel</v-btn>
          <v-btn variant="flat" color="primary" @click="saveModelConfig">Save Configuration</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script>
import { getParameterConfig, parameterRegistry } from './ModelParameterRegistry.js'

export default {
  name: 'ModelSelector',
  inject: ['getWebsocket'],
  props: {
    modelValue: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue', 'modelSelected'],
  data() {
    return {
      searchQuery: '',
      modelGroups: [],
      loading: false,
      error: null,
      hoveredModel: null,
      configDialog: false,
      selectedModel: null,
      selectedProvider: null,
      configName: '',
      modelConfig: {},
      chipInput: {},
      expandedPanels: []
    }
  },
  computed: {
    dialog: {
      get() {
        return this.modelValue
      },
      set(value) {
        this.$emit('update:modelValue', value)
      }
    },
    filteredModelGroups() {
      if (!this.searchQuery) {
        return this.modelGroups
      }
      
      const query = this.searchQuery.toLowerCase()
      return this.modelGroups.map(group => ({
        ...group,
        models: group.models.filter(model => 
          model.name.toLowerCase().includes(query) ||
          model.full_name.toLowerCase().includes(query)
        )
      })).filter(group => group.models.length > 0)
    }
  },
  watch: {
    dialog(newVal) {
      if (newVal) {
        if (this.modelGroups.length === 0) {
          this.loadModels()
        } else {
          // Expand all panels when dialog opens
          this.expandedPanels = this.filteredModelGroups.map((_, index) => index)
        }
      }
    }
  },
  methods: {
    async loadModels() {
      this.loading = true
      this.error = null
      
      try {
        // Request model data from backend
        const ws = this.getWebsocket()
        ws.send(JSON.stringify({
          type: 'config',
          action: 'request_model_selector'
        }))
        
        // Wait for response
        await this.waitForModelData()
        
      } catch (err) {
        this.error = 'Failed to load models: ' + err.message
      } finally {
        this.loading = false
      }
    },
    
    waitForModelData() {
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Timeout waiting for model data'))
        }, 10000)
        
        const handler = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'config') {
              if (data.action === 'model_selector_data') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                this.modelGroups = data.data.model_groups || []
                // Expand all panels by default
                this.expandedPanels = this.modelGroups.map((_, index) => index)
                resolve()
              } else if (data.action === 'model_selector_error') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                reject(new Error(data.data.message || 'Unknown error'))
              }
            }
          } catch (e) {
            // Ignore parsing errors for non-JSON messages
          }
        }
        
        const ws = this.getWebsocket()
        ws.addEventListener('message', handler)
      })
    },
    
    selectModel(model, group) {
      this.selectedModel = model
      this.selectedProvider = group
      this.configName = `${model.name} Config`
      // Initialize model config with defaults from registry
      this.modelConfig = {}
      this.chipInput = {}
      model.parameters.forEach(param => {
        const config = getParameterConfig(param)
        this.modelConfig[param] = config.default
        if (config.type === 'chips') {
          this.modelConfig[param] = config.default || []
          this.chipInput[param] = ''
        }
      })
      this.configDialog = true
    },
    
    saveModelConfig() {
      const config = {
        model: this.selectedModel,
        provider: this.selectedProvider,
        name: this.configName,
        parameters: this.modelConfig
      }
      
      this.$emit('modelSelected', config)
      this.configDialog = false
      this.close()
    },
    
    close() {
      this.dialog = false
    },
    
    getProviderIcon(providerName) {
      const iconMap = {
        'OpenRouter': 'mdi-router',
        'OpenAI': 'mdi-openid',
        'Anthropic': 'mdi-robot-happy',
        'Manual Configuration': 'mdi-cog',
        'OpenAI Compatible': 'mdi-api'
      }
      return iconMap[providerName] || 'mdi-cloud'
    },
    
    hasCapabilities(model) {
      return model.capabilities && (
        model.capabilities.vision ||
        model.capabilities.reasoning ||
        model.capabilities.function_calling ||
        model.capabilities.web_search
      )
    },
    
    // Use the parameter registry
    getParamConfig(param) {
      return getParameterConfig(param)
    },
    
    // Parameter categorization
    getParametersByType(type) {
      return this.selectedModel.parameters.filter(param => 
        getParameterConfig(param).type === type
      )
    },
    
    getParametersByCategory(category) {
      const generationParams = ['max_tokens', 'max_output_tokens', 'n', 'best_of', 'response_format']
      
      if (category === 'generation') {
        return this.selectedModel.parameters.filter(param => 
          generationParams.includes(param) && getParameterConfig(param).type !== 'slider'
        )
      }
      return []
    },
    
    getAdvancedParameters() {
      const primaryParams = ['temperature', 'top_p', 'top_k', 'frequency_penalty', 'presence_penalty', 'repetition_penalty']
      const generationParams = ['max_tokens', 'max_output_tokens', 'n', 'best_of', 'response_format']
      const knownParams = [...primaryParams, ...generationParams]
      
      return this.selectedModel.parameters.filter(param => {
        const isKnown = parameterRegistry.hasOwnProperty(param)
        return isKnown && !knownParams.includes(param)
      })
    },
    
    getUnknownParameters() {
      return this.selectedModel.parameters.filter(param => 
        !parameterRegistry.hasOwnProperty(param)
      )
    },
    
    hasAdvancedSettings() {
      return this.getAdvancedParameters().length > 0
    },
    
    getAdvancedParamCols(param) {
      const config = getParameterConfig(param)
      if (config.type === 'switch') return 6
      if (config.type === 'json' || config.type === 'chips') return 12
      return 6
    },
    
    // Chip management for array parameters
    addChip(param) {
      if (!this.chipInput[param]) return
      if (!this.modelConfig[param]) {
        this.modelConfig[param] = []
      }
      this.modelConfig[param].push(this.chipInput[param])
      this.chipInput[param] = ''
    },
    
    removeChip(param, index) {
      this.modelConfig[param].splice(index, 1)
    },
    
    // JSON parameter handling
    getJsonString(value) {
      if (typeof value === 'object') {
        return JSON.stringify(value, null, 2)
      }
      return value || '{}'
    },
    
    updateJsonParam(param, value) {
      try {
        this.modelConfig[param] = JSON.parse(value)
      } catch (e) {
        // Keep as string if invalid JSON
        this.modelConfig[param] = value
      }
    },
    
    validateJson(value) {
      if (!value || value === '{}') return true
      try {
        JSON.parse(value)
        return true
      } catch (e) {
        return 'Invalid JSON format'
      }
    }
  }
}
</script>

<style scoped>
.model-list-item {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.model-list-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.26);
}
</style>