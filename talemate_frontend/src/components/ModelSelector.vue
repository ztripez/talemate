<template>
  <v-dialog v-model="dialog" scrollable max-width="1200px">
    <v-card>
      <v-card-title>
        <v-icon class="mr-1">mdi-robot</v-icon>
        Model Browser
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          size="small"
          @click="refreshModels"
          :disabled="loading"
          class="mr-2"
        >
          <v-icon :class="{ 'mdi-spin': loading }">mdi-refresh</v-icon>
          <v-tooltip activator="parent" location="bottom">Refresh model list</v-tooltip>
        </v-btn>
      </v-card-title>
      
      <v-card-text>
        <v-row>
          <v-col cols="12" class="pb-0">
            <v-text-field
              v-model="searchInput"
              @input="onSearchInput"
              @click:clear="onSearchClear"
              prepend-inner-icon="mdi-magnify"
              label="Search models..."
              clearable
              density="compact"
              variant="outlined"
              hide-details
            ></v-text-field>
          </v-col>
        </v-row>
        
        <v-row class="mt-1">
          <v-col cols="12" class="py-1">
            <div class="d-flex align-center gap-2">
              <span class="text-caption text-disabled">Filters:</span>
              <v-btn-toggle
                v-model="activeFilters"
                multiple
                density="compact"
                variant="text"
                divided
                color="primary"
              >
                <v-btn
                  value="vision"
                  size="x-small"
                >
                  <v-icon size="x-small" class="mr-1">mdi-eye-outline</v-icon>
                  <span class="text-caption">Vision</span>
                </v-btn>
                <v-btn
                  value="reasoning"
                  size="x-small"
                >
                  <v-icon size="x-small" class="mr-1">mdi-head-cog-outline</v-icon>
                  <span class="text-caption">Reasoning</span>
                </v-btn>
                <v-btn
                  value="function_calling"
                  size="x-small"
                >
                  <v-icon size="x-small" class="mr-1">mdi-function-variant</v-icon>
                  <span class="text-caption">Functions</span>
                </v-btn>
                <v-btn
                  value="web_search"
                  size="x-small"
                >
                  <v-icon size="x-small" class="mr-1">mdi-web</v-icon>
                  <span class="text-caption">Search</span>
                </v-btn>
              </v-btn-toggle>
              <v-spacer></v-spacer>
              <v-fade-transition>
                <v-progress-circular
                  v-if="filtering"
                  size="16"
                  width="2"
                  indeterminate
                  color="primary"
                  class="mr-2"
                ></v-progress-circular>
              </v-fade-transition>
              <v-fade-transition>
                <v-btn
                  v-if="activeFilters.length > 0"
                  size="x-small"
                  variant="text"
                  @click="activeFilters = []"
                >
                  Clear filters
                </v-btn>
              </v-fade-transition>
            </div>
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
                    <v-chip size="small" color="secondary" class="mr-2">
                      {{ getModelCount(group) }} models
                    </v-chip>
                  </div>
                </v-expansion-panel-title>
                
                <v-expansion-panel-text>
                  <!-- Handle providers with subgroups (nested structure) -->
                  <div v-if="group.has_subgroups && group.subgroups">
                    <v-expansion-panels v-model="expandedSubPanels[group.provider_id]" multiple>
                      <v-expansion-panel
                        v-for="(subgroup, subIndex) in group.subgroups"
                        :key="subgroup.group_id"
                        :value="subIndex"
                        elevation="1"
                        class="mb-1"
                      >
                        <v-expansion-panel-title>
                          <div class="d-flex align-center w-100">
                            <v-icon size="small" class="mr-2">{{ getSubProviderIcon(subgroup.group_name) }}</v-icon>
                            <span class="text-body-1">{{ subgroup.group_name }}</span>
                            <v-spacer></v-spacer>
                            <v-chip size="x-small" variant="tonal" class="mr-2">
                              {{ subgroup.models.length }} models
                            </v-chip>
                          </div>
                        </v-expansion-panel-title>
                        
                        <v-expansion-panel-text>
                          <v-list density="compact" class="pa-0">
                            <v-list-item
                              v-for="model in subgroup.models"
                              :key="model.full_name"
                              @click="selectModel(model, group)"
                              :ripple="true"
                              class="model-list-item mb-1"
                            >
                              <template v-slot:prepend>
                                <v-icon size="small">mdi-language-markdown-outline</v-icon>
                              </template>
                              
                              <v-list-item-title>
                                <span v-html="highlightSearchTerm(model.display_name || model.name)"></span>
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
                                <div v-else class="d-flex flex-wrap gap-1 mt-1">
                                  <v-chip 
                                    size="x-small" 
                                    variant="tonal"
                                    color="grey"
                                  >
                                    <v-icon start size="x-small">mdi-text</v-icon>
                                    Text
                                  </v-chip>
                                </div>
                              </v-list-item-subtitle>
                              
                              <template v-slot:append>
                                <v-icon size="small">mdi-chevron-right</v-icon>
                              </template>
                            </v-list-item>
                          </v-list>
                        </v-expansion-panel-text>
                      </v-expansion-panel>
                    </v-expansion-panels>
                  </div>
                  
                  <!-- Handle providers without subgroups (flat list) -->
                  <v-list v-else density="compact" class="pa-0">
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
                        <span v-html="highlightSearchTerm(model.display_name || model.name)"></span>
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
                        <div v-else class="d-flex flex-wrap gap-1 mt-1">
                          <v-chip 
                            size="x-small" 
                            variant="tonal"
                            color="grey"
                          >
                            <v-icon start size="x-small">mdi-text</v-icon>
                            Text
                          </v-chip>
                        </div>
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
          {{ editingConfig ? 'Edit' : 'Configure' }} Model
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
                label="Preset Name"
                density="compact"
                variant="outlined"
                placeholder="e.g., Creative Writing, Code Assistant"
                persistent-hint
                hint="Give this preset a memorable name"
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
          <v-btn variant="text" @click="cancelConfig">Cancel</v-btn>
          <v-btn variant="flat" color="primary" @click="saveModelConfig">{{ editingConfig ? 'Update' : 'Save' }} Preset</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script>
import { getParameterConfig, parameterRegistry } from './ModelParameterRegistry.js'

export default {
  name: 'ModelSelector',
  inject: ['getWebsocket', 'registerMessageHandler'],
  props: {
    modelValue: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue', 'modelSelected', 'notify', 'presetSaved'],
  data() {
    return {
      searchQuery: '',
      searchInput: '', // Separate input value for immediate updates
      modelGroups: [],
      loading: false,
      filtering: false, // Track filtering state
      error: null,
      hoveredModel: null,
      configDialog: false,
      selectedModel: null,
      selectedProvider: null,
      configName: '',
      modelConfig: {},
      chipInput: {},
      expandedPanels: [],
      expandedSubPanels: {}, // Track expanded state for subgroups
      editingConfig: null,
      activeFilters: [], // Track active capability filters
      filteredCache: null, // Cache filtered results
      filterTimeout: null // Debounce filtering
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
      // Return cached results if filtering is in progress
      if (this.filtering && this.filteredCache !== null) {
        return this.filteredCache
      }
      
      const hasSearchQuery = !!this.searchQuery
      const hasFilters = this.activeFilters.length > 0
      
      if (!hasSearchQuery && !hasFilters) {
        this.filteredCache = this.modelGroups
        return this.modelGroups
      }
      
      // If we have a cache, return it while new filtering happens
      if (this.filteredCache !== null) {
        return this.filteredCache
      }
      
      // Otherwise return original until filtering completes
      return this.modelGroups
    }
  },
  watch: {
    dialog(newVal) {
      if (newVal) {
        if (this.modelGroups.length === 0) {
          this.loadModels()
        } else {
          // Trigger filtering if we have search or filters
          if (this.searchQuery || this.activeFilters.length > 0) {
            this.performFiltering()
          }
          // Expand all panels when dialog opens
          this.expandedPanels = this.filteredModelGroups.map((_, index) => index)
        }
      }
    },
    searchQuery(newVal) {
      if (newVal) {
        // When searching, expand all panels and subpanels to show results
        this.expandAllPanels()
      }
      // Trigger filtering
      this.performFiltering()
    },
    activeFilters() {
      this.debouncedFilter()
      // When filters change, expand panels to show filtered results
      if (this.activeFilters.length > 0) {
        this.expandAllPanels()
      }
    }
  },
  methods: {
    async loadModels() {
      this.loading = true
      this.error = null
      
      try {
        // Request model data from backend with grouping for OpenRouter
        const ws = this.getWebsocket()
        ws.send(JSON.stringify({
          type: 'config',
          action: 'request_model_selector',
          group_by: 'provider'  // Request provider-based grouping
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
    
    // Add method to refresh model data
    refreshModelData() {
      this.loadModels()
    },
    
    // Method for the refresh button
    refreshModels() {
      // Clear search query and filters to show all models
      this.searchQuery = ''
      this.searchInput = ''
      this.activeFilters = []
      // Force reload of models
      this.loadModels()
    },
    
    onSearchInput() {
      // Clear existing timeout
      if (this.filterTimeout) {
        clearTimeout(this.filterTimeout)
      }
      
      // Set new timeout for debounced search
      this.filterTimeout = setTimeout(() => {
        this.searchQuery = this.searchInput
      }, 300)
    },
    
    onSearchClear() {
      this.searchInput = ''
      this.searchQuery = ''
      if (this.filterTimeout) {
        clearTimeout(this.filterTimeout)
      }
    },
    
    expandAllPanels() {
      // Expand all main panels
      this.expandedPanels = this.filteredModelGroups.map((_, index) => index)
      
      // Expand all subpanels for groups with subgroups
      this.filteredModelGroups.forEach(group => {
        if (group.has_subgroups && group.subgroups) {
          // In Vue 3, we can directly assign to reactive properties
          this.expandedSubPanels[group.provider_id] = group.subgroups.map((_, index) => index)
        }
      })
    },
    
    highlightSearchTerm(text) {
      if (!this.searchQuery || !text) {
        return text
      }
      
      const query = this.searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // Escape special regex chars
      const regex = new RegExp(`(${query})`, 'gi')
      return text.replace(regex, '<mark>$1</mark>')
    },
    
    debouncedFilter() {
      // Clear existing timeout
      if (this.filterTimeout) {
        clearTimeout(this.filterTimeout)
      }
      
      // Set new timeout
      this.filterTimeout = setTimeout(() => {
        this.performFiltering()
      }, 300) // 300ms debounce
    },
    
    async performFiltering() {
      // Don't filter if already filtering
      if (this.filtering) return
      
      this.filtering = true
      
      // Use requestAnimationFrame to ensure UI remains responsive
      await new Promise(resolve => requestAnimationFrame(resolve))
      
      const hasSearchQuery = !!this.searchQuery
      const hasFilters = this.activeFilters.length > 0
      
      if (!hasSearchQuery && !hasFilters) {
        this.filteredCache = this.modelGroups
        this.filtering = false
        return
      }
      
      const query = this.searchQuery ? this.searchQuery.toLowerCase() : ''
      
      // Process in chunks to prevent blocking
      const processGroups = async () => {
        const results = []
        
        for (let i = 0; i < this.modelGroups.length; i++) {
          const group = this.modelGroups[i]
          
          // Yield control back to browser more frequently for large lists
          if (i % 2 === 0) {
            await new Promise(resolve => {
              if ('requestIdleCallback' in window) {
                requestIdleCallback(resolve, { timeout: 16 })
              } else {
                setTimeout(resolve, 0)
              }
            })
          }
          
          if (group.has_subgroups && group.subgroups) {
            // Filter models within subgroups
            const filteredSubgroups = []
            
            for (const subgroup of group.subgroups) {
              const filteredModels = subgroup.models.filter(model => {
                // Apply search filter
                const matchesSearch = !hasSearchQuery || (
                  model.name.toLowerCase().includes(query) ||
                  model.full_name.toLowerCase().includes(query) ||
                  (model.display_name && model.display_name.toLowerCase().includes(query))
                )
                
                // Apply capability filters
                const matchesFilters = !hasFilters || this.activeFilters.every(filter => 
                  model.capabilities && model.capabilities[filter]
                )
                
                return matchesSearch && matchesFilters
              })
              
              if (filteredModels.length > 0) {
                filteredSubgroups.push({
                  ...subgroup,
                  models: filteredModels
                })
              }
            }
            
            // Add group if it has matching models
            if (filteredSubgroups.length > 0) {
              results.push({
                ...group,
                subgroups: filteredSubgroups
              })
            }
          } else if (group.models) {
            // Regular flat list filtering
            const filteredModels = group.models.filter(model => {
              // Apply search filter
              const matchesSearch = !hasSearchQuery || (
                model.name.toLowerCase().includes(query) ||
                model.full_name.toLowerCase().includes(query) ||
                (model.display_name && model.display_name.toLowerCase().includes(query))
              )
              
              // Apply capability filters
              const matchesFilters = !hasFilters || this.activeFilters.every(filter => 
                model.capabilities && model.capabilities[filter]
              )
              
              return matchesSearch && matchesFilters
            })
            
            if (filteredModels.length > 0) {
              results.push({
                ...group,
                models: filteredModels
              })
            }
          }
        }
        
        return results
      }
      
      try {
        this.filteredCache = await processGroups()
      } finally {
        this.filtering = false
      }
    },
    
    // Add method to handle provider-related messages
    handleProviderMessage(data) {
      // Listen for all provider CRUD events and refresh model data
      if (data.type === 'config') {
        if (data.action === 'provider_save_complete' ||
            data.action === 'provider_instance_delete_complete' ||
            data.action === 'provider_update_complete' ||
            data.action === 'provider_create_complete' ||
            data.action === 'providers_updated') {
          // Refresh model data when providers are created, updated, or deleted
          this.refreshModelData()
        }
      }
    },
    
    selectModel(model, group) {
      this.selectedModel = model
      this.selectedProvider = group
      
      // Simple default name - user should customize it
      this.configName = `${model.display_name || model.name} Config`
      
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
    
    async saveModelConfig() {
      try {
        const ws = this.getWebsocket()
        
        // Send save request with minimal data
        ws.send(JSON.stringify({
          type: 'config',
          action: 'save_model_config',
          config_id: this.editingConfig?.id,
          name: this.configName,
          model: {
            name: this.selectedModel.name,
            display_name: this.selectedModel.display_name,
            full_name: this.selectedModel.full_name,
            capabilities: this.selectedModel.capabilities
          },
          provider: {
            provider_id: this.selectedProvider.provider_id,
            provider_name: this.selectedProvider.provider_name
          },
          parameters: this.modelConfig,
          created_at: this.editingConfig?.created_at
        }))
        
        // Wait for response
        await this.waitForSaveResponse()
        
        // Emit the configuration for immediate use
        const config = {
          model: this.selectedModel,
          provider: this.selectedProvider,
          name: this.configName,
          parameters: this.modelConfig
        }
        
        this.$emit('modelSelected', config)
        this.configDialog = false
        this.editingConfig = null
        
        // Show success feedback
        this.$emit('notify', {
          message: `Preset "${this.configName}" saved successfully!`,
          type: 'success'
        })
        
        // Emit event to refresh preset listing
        this.$emit('presetSaved')
        
      } catch (err) {
        console.error('Failed to save model configuration:', err)
        this.$emit('notify', {
          message: `Failed to save configuration: ${err.message}`,
          type: 'error'
        })
      }
    },
    
    waitForSaveResponse() {
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Timeout waiting for save response'))
        }, 5000)
        
        const handler = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'config') {
              if (data.action === 'model_config_save_complete') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                resolve(data.data.config_id)
              } else if (data.action === 'model_config_save_error') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                reject(new Error(data.data.message || 'Failed to save'))
              }
            }
          } catch (e) {
            // Ignore parsing errors
          }
        }
        
        const ws = this.getWebsocket()
        ws.addEventListener('message', handler)
      })
    },
    
    close() {
      this.dialog = false
    },
    
    cancelConfig() {
      this.configDialog = false
      this.editingConfig = null
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
    
    getSubProviderIcon(providerName) {
      const iconMap = {
        'OpenAI': 'mdi-openid',
        'Anthropic': 'mdi-robot-happy',
        'Google': 'mdi-google',
        'Meta': 'mdi-facebook',
        'Mistral AI': 'mdi-weather-windy',
        'Cohere': 'mdi-circle-multiple',
        'DeepSeek': 'mdi-magnify-scan',
        'Microsoft': 'mdi-microsoft',
        'xAI': 'mdi-twitter',
        'NVIDIA': 'mdi-chip',
        'Perplexity': 'mdi-help-network',
        'Inflection': 'mdi-lightbulb',
        'Nous Research': 'mdi-school',
        'Qwen': 'mdi-alphabetical-variant'
      }
      return iconMap[providerName] || 'mdi-circle-outline'
    },
    
    getModelCount(group) {
      if (group.has_subgroups && group.subgroups) {
        // Sum models across all subgroups
        return group.subgroups.reduce((total, subgroup) => {
          return total + (subgroup.models ? subgroup.models.length : 0)
        }, 0)
      }
      return group.models ? group.models.length : 0
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
    },
    
    formatDate(dateString) {
      try {
        const date = new Date(dateString)
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
      } catch {
        return dateString
      }
    }
  },
  created() {
    // Register message handlers for websocket events
    this.registerMessageHandler(this.handleProviderMessage);
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

/* Spinning animation for refresh button */
.mdi-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Highlight search results */
::v-deep mark {
  background-color: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
  font-weight: 500;
  padding: 0;
  border-radius: 0;
  text-decoration: underline;
  text-decoration-color: rgba(var(--v-theme-primary), 0.3);
  text-underline-offset: 2px;
}
</style>