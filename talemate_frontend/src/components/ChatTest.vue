<template>
  <v-dialog v-model="dialog" max-width="1200" persistent>
    <template v-slot:activator="{ props }">
      <v-btn v-bind="props" icon="mdi-chat" title="Test Chat" />
    </template>

    <v-card>
      <v-card-title class="d-flex align-center">
        <span>Chat Test (Debug Mode)</span>
        <v-spacer></v-spacer>
        <v-btn icon="mdi-close" variant="text" @click="dialog = false"></v-btn>
      </v-card-title>

      <v-divider></v-divider>

      <!-- Model Selection and Configuration -->
      <v-card-text>
        <v-row>
          <v-col cols="6">
            <v-select
              v-model="selectedConfig"
              :items="savedConfigs"
              :loading="loadingConfigs"
              item-title="name"
              item-value="id"
              label="Select Model Configuration"
              variant="outlined"
              density="compact"
              clearable
              @update:model-value="onConfigSelected"
            >
              <template v-slot:item="{ props, item }">
                <v-list-item v-bind="props" :title="item.raw.name" :subtitle="`${item.raw.provider.provider_name} - ${item.raw.model.display_name}`" />
              </template>
              <template v-slot:selection="{ item }">
                <span>{{ item.raw.name }} ({{ item.raw.provider.provider_name }})</span>
              </template>
            </v-select>
          </v-col>
          <v-col cols="6" class="d-flex align-center justify-space-between">
            <v-chip v-if="currentConfig" color="success" size="small">
              <v-icon start size="small">mdi-check</v-icon>
              Configuration loaded - modify parameters in Model Config tab
            </v-chip>
            <v-switch
              v-model="enableStreaming"
              label="Streaming"
              density="compact"
              hide-details
              color="primary"
            ></v-switch>
          </v-col>
        </v-row>

        <v-row>
          <!-- Chat Messages Column -->
          <v-col :cols="showDebugInfo ? 7 : 12">
            <v-card variant="outlined" class="mb-4" style="height: 400px; overflow-y: auto;">
              <v-card-text>
                <v-list density="compact">
                  <v-list-item v-for="(message, index) in messages" :key="index" :class="message.role === 'user' ? 'text-right' : ''">
                    <v-chip 
                      :color="getRoleColor(message.role)" 
                      class="mb-2"
                      size="small"
                    >
                      <v-icon start size="x-small">{{ getRoleIcon(message.role) }}</v-icon>
                      {{ getRoleLabel(message.role) }}
                    </v-chip>
                    <div class="message-content" :class="`${message.role}-message`">
                      {{ message.content }}
                      <span v-if="message.isStreaming" class="streaming-cursor">▊</span>
                    </div>
                  </v-list-item>
                  <v-progress-linear v-if="isGenerating" indeterminate color="primary" class="mt-2"></v-progress-linear>
                </v-list>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- Debug Info Column -->
          <v-col v-if="showDebugInfo" cols="5">
            <v-card variant="outlined" style="height: 400px;">
              <v-tabs v-model="debugTab" density="compact">
                <v-tab value="api">API</v-tab>
                <v-tab value="config">Model Config</v-tab>
              </v-tabs>
              <v-divider></v-divider>
              
              <v-window v-model="debugTab">
                <!-- API Tab -->
                <v-window-item value="api">
                  <v-card-text style="height: 340px; overflow-y: auto;">
                    <div v-if="lastApiCall">
                      <div class="mb-4">
                        <div class="text-subtitle-2 mb-2">Last API Request</div>
                        <v-card variant="tonal" density="compact">
                          <v-card-text>
                            <pre class="debug-pre">{{ JSON.stringify(lastApiCall.request, null, 2) }}</pre>
                          </v-card-text>
                        </v-card>
                      </div>
                      
                      <div v-if="lastApiCall.response" class="mb-4">
                        <div class="text-subtitle-2 mb-2">API Response</div>
                        <v-card variant="tonal" density="compact">
                          <v-card-text>
                            <pre class="debug-pre">{{ JSON.stringify(lastApiCall.response, null, 2) }}</pre>
                          </v-card-text>
                        </v-card>
                      </div>

                      <div v-if="lastApiCall.error" class="mb-4">
                        <div class="text-subtitle-2 mb-2 text-error">Error</div>
                        <v-card variant="tonal" color="error" density="compact">
                          <v-card-text>
                            <pre class="debug-pre">{{ lastApiCall.error }}</pre>
                          </v-card-text>
                        </v-card>
                      </div>

                      <div v-if="lastApiCall.timing" class="mb-4">
                        <div class="text-subtitle-2 mb-2">Timing</div>
                        <v-list density="compact">
                          <v-list-item>
                            <template v-slot:prepend>
                              <v-icon size="small">mdi-clock</v-icon>
                            </template>
                            <v-list-item-title>Duration: {{ lastApiCall.timing.duration }}ms</v-list-item-title>
                          </v-list-item>
                          <v-list-item>
                            <template v-slot:prepend>
                              <v-icon size="small">mdi-calendar</v-icon>
                            </template>
                            <v-list-item-title>Time: {{ new Date(lastApiCall.timing.timestamp).toLocaleTimeString() }}</v-list-item-title>
                          </v-list-item>
                        </v-list>
                      </div>
                    </div>
                    <v-alert v-else type="info" variant="text" density="compact">
                      Send a message to see debug information
                    </v-alert>
                  </v-card-text>
                </v-window-item>
                
                <!-- Model Config Tab -->
                <v-window-item value="config">
                  <v-card-text style="height: 340px; overflow-y: auto;">
                    <div v-if="currentConfig && testParameters">
                      <!-- Primary Controls (Sliders) -->
                      <div v-if="getParametersByType('slider').length > 0">
                        <h4 class="text-subtitle-2 text-grey mb-2">
                          <v-icon size="small" class="mr-1">mdi-tune</v-icon>
                          Primary Controls
                        </h4>
                        <div v-for="param in getParametersByType('slider')" :key="param" class="mb-3">
                          <div class="d-flex align-center mb-1">
                            <span class="text-caption">{{ getParamConfig(param).label }}</span>
                            <v-spacer></v-spacer>
                            <v-chip size="x-small" variant="tonal">{{ testParameters[param] }}</v-chip>
                          </div>
                          <v-slider
                            v-model="testParameters[param]"
                            :min="getParamConfig(param).min"
                            :max="getParamConfig(param).max"
                            :step="getParamConfig(param).step"
                            :hint="getParamConfig(param).hint"
                            density="compact"
                            color="primary"
                            hide-details
                          ></v-slider>
                        </div>
                      </div>
                      
                      <!-- Basic Parameters -->
                      <div v-if="getParametersByType('number').length > 0 || getParametersByType('text').length > 0" class="mt-3">
                        <h4 class="text-subtitle-2 text-grey mb-2">
                          <v-icon size="small" class="mr-1">mdi-format-list-bulleted</v-icon>
                          Basic Parameters
                        </h4>
                        <div v-for="param in [...getParametersByType('number'), ...getParametersByType('text')]" :key="param" class="mb-2">
                          <v-text-field
                            v-if="getParamConfig(param).type === 'number'"
                            v-model.number="testParameters[param]"
                            :label="getParamConfig(param).label"
                            :hint="getParamConfig(param).hint"
                            :min="getParamConfig(param).min"
                            :max="getParamConfig(param).max"
                            type="number"
                            density="compact"
                            variant="outlined"
                            hide-details
                          ></v-text-field>
                          
                          <v-text-field
                            v-else
                            v-model="testParameters[param]"
                            :label="getParamConfig(param).label"
                            :hint="getParamConfig(param).hint"
                            density="compact"
                            variant="outlined"
                            hide-details
                          ></v-text-field>
                        </div>
                      </div>
                      
                      <!-- Advanced Settings -->
                      <v-expansion-panels v-if="getOtherParameters().length > 0" class="mt-3">
                        <v-expansion-panel>
                          <v-expansion-panel-title class="py-2">
                            <v-icon size="small" class="mr-2">mdi-cog-outline</v-icon>
                            <span class="text-caption">Advanced Settings ({{ getOtherParameters().length }})</span>
                          </v-expansion-panel-title>
                          <v-expansion-panel-text>
                            <div v-for="param in getOtherParameters()" :key="param" class="mb-2">
                              <!-- Switches -->
                              <v-switch
                                v-if="getParamConfig(param).type === 'switch'"
                                v-model="testParameters[param]"
                                :label="getParamConfig(param).label"
                                density="compact"
                                color="primary"
                                hide-details
                              ></v-switch>
                              
                              <!-- Select -->
                              <v-select
                                v-else-if="getParamConfig(param).type === 'select'"
                                v-model="testParameters[param]"
                                :label="getParamConfig(param).label"
                                :items="getParamConfig(param).options"
                                density="compact"
                                variant="outlined"
                                hide-details
                              ></v-select>
                              
                              <!-- Chips -->
                              <div v-else-if="getParamConfig(param).type === 'chips'">
                                <label class="text-caption text-grey-darken-1">{{ getParamConfig(param).label }}</label>
                                <v-chip-group
                                  v-model="testParameters[param]"
                                  column
                                  multiple
                                >
                                  <v-chip
                                    v-for="(chip, index) in testParameters[param] || []"
                                    :key="index"
                                    size="small"
                                    closable
                                    @click:close="removeChip(param, index)"
                                  >
                                    {{ chip }}
                                  </v-chip>
                                </v-chip-group>
                                <v-text-field
                                  v-model="chipInput[param]"
                                  density="compact"
                                  variant="outlined"
                                  hide-details
                                  @keyup.enter="addChip(param)"
                                  placeholder="Press enter to add"
                                ></v-text-field>
                              </div>
                              
                              <!-- JSON parameters -->
                              <v-textarea
                                v-else-if="getParamConfig(param).type === 'json'"
                                :modelValue="getJsonString(testParameters[param])"
                                @update:modelValue="updateJsonParam(param, $event)"
                                :label="getParamConfig(param).label"
                                :hint="getParamConfig(param).hint"
                                density="compact"
                                variant="outlined"
                                hide-details
                                rows="2"
                                :rules="[validateJson]"
                              ></v-textarea>
                              
                              <!-- Default text -->
                              <v-text-field
                                v-else
                                v-model="testParameters[param]"
                                :label="getParamConfig(param).label"
                                density="compact"
                                variant="outlined"
                                hide-details
                              ></v-text-field>
                            </div>
                          </v-expansion-panel-text>
                        </v-expansion-panel>
                      </v-expansion-panels>
                      
                      <!-- Action Buttons -->
                      <div class="mt-3 d-flex justify-space-between">
                        <div>
                          <v-btn size="small" variant="text" @click="resetParameters" class="mr-1">
                            <v-icon start size="small">mdi-restore</v-icon>
                            Reset to Saved
                          </v-btn>
                          <v-btn size="small" variant="text" @click="resetToDefaults">
                            <v-icon start size="small">mdi-backup-restore</v-icon>
                            Reset to Defaults
                          </v-btn>
                        </div>
                        <v-btn 
                          size="small" 
                          variant="tonal" 
                          color="primary" 
                          @click="updateConfiguration"
                          :disabled="!hasParameterChanges"
                        >
                          <v-icon start size="small">mdi-content-save</v-icon>
                          Update Config
                        </v-btn>
                      </div>
                    </div>
                    <v-alert v-else type="info" variant="text" density="compact">
                      Select a model configuration to edit parameters
                    </v-alert>
                  </v-card-text>
                </v-window-item>
              </v-window>
            </v-card>
          </v-col>
        </v-row>

        <!-- Input -->
        <v-row>
          <v-col cols="3">
            <v-select
              v-model="messageRole"
              :items="['user', 'assistant', 'system']"
              label="Role"
              variant="outlined"
              density="compact"
            ></v-select>
          </v-col>
          <v-col cols="9">
            <v-text-field
              v-model="userInput"
              label="Type your message..."
              variant="outlined"
              density="compact"
              append-inner-icon="mdi-send"
              @keyup.enter="sendMessage"
              @click:append-inner="sendMessage"
              :disabled="!selectedConfig || isGenerating"
            ></v-text-field>
          </v-col>
        </v-row>
      </v-card-text>

      <v-card-actions>
        <v-btn @click="clearChat" :disabled="messages.length === 0">Clear Chat</v-btn>
        <v-btn 
          @click="redoLastMessage" 
          :disabled="!canRedoLastMessage"
          :title="canRedoLastMessage ? 'Regenerate last response with current parameters' : 'No assistant message to redo'"
        >
          <v-icon start>mdi-refresh</v-icon>
          Redo Last
        </v-btn>
        <v-btn @click="showDebugInfo = !showDebugInfo" :color="showDebugInfo ? 'primary' : ''">
          <v-icon>{{ showDebugInfo ? 'mdi-eye-off' : 'mdi-eye' }}</v-icon>
          Debug Info
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn color="primary" @click="dialog = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { getParameterConfig } from './ModelParameterRegistry.js'

export default {
  name: 'ChatTest',
  inject: ['getWebsocket'],
  data() {
    return {
      dialog: false,
      selectedConfig: null,
      savedConfigs: [],
      loadingConfigs: false,
      messages: [],
      userInput: '',
      messageRole: 'user',
      isGenerating: false,
      currentConfig: null,
      showDebugInfo: true,
      lastApiCall: null,
      debugTab: 'api',
      testParameters: {},
      chipInput: {},
      enableStreaming: false
    }
  },
  watch: {
    dialog(val) {
      if (val) {
        this.loadSavedConfigs()
      }
    }
  },
  computed: {
    hasParameterChanges() {
      if (!this.currentConfig || !this.testParameters) {
        return false
      }
      
      // Check if any test parameter differs from saved parameter
      const savedParams = this.currentConfig.parameters || {}
      const testParams = this.testParameters || {}
      
      // Check all keys from both objects
      const allKeys = new Set([...Object.keys(savedParams), ...Object.keys(testParams)])
      
      for (const key of allKeys) {
        if (savedParams[key] !== testParams[key]) {
          return true
        }
      }
      
      return false
    },
    
    canRedoLastMessage() {
      // Can redo if there's at least one assistant message and we're not currently generating
      return this.messages.length >= 2 && 
             this.messages[this.messages.length - 1].role === 'assistant' && 
             !this.isGenerating &&
             this.currentConfig
    }
  },
  methods: {
    async loadSavedConfigs() {
      this.loadingConfigs = true
      try {
        const ws = this.getWebsocket()
        
        // Request saved configs
        ws.send(JSON.stringify({
          type: 'config',
          action: 'request_model_configs'
        }))
        
        // Wait for response
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Timeout loading configs'))
          }, 5000)
          
          const handler = (event) => {
            try {
              const data = JSON.parse(event.data)
              if (data.type === 'config' && data.action === 'model_configs_data') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                this.savedConfigs = data.data.configs || []
                console.log('Loaded configs in ChatTest:', this.savedConfigs)
                resolve()
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
          
          ws.addEventListener('message', handler)
        })
      } catch (err) {
        console.error('Failed to load configs:', err)
      } finally {
        this.loadingConfigs = false
      }
    },

    onConfigSelected(configId) {
      const config = this.savedConfigs.find(c => c.id === configId)
      if (config) {
        this.currentConfig = config
        // Initialize test parameters with saved config values
        this.testParameters = { ...config.parameters }
        this.chipInput = {}
        
        // For KoboldCpp, add all supported parameters
        if (config.provider && config.provider.provider_name === 'KoboldCpp') {
          // KoboldCpp specific parameters
          const koboldParams = [
            'rep_pen', 'rep_pen_range', 'typical_p', 'tfs_z', 'top_a', 'top_k',
            'mirostat', 'mirostat_tau', 'mirostat_eta', 'min_p', 'xtc_threshold',
            'xtc_probability', 'dynatemp_range', 'dynatemp_exponent',
            'banned_tokens', 'sampler_priority', 'sampler_order', 'sampler_seed',
            'presence_penalty', 'frequency_penalty', 'logit_bias',
            'use_default_badwordsids'
          ]
          
          // Standard parameters
          const standardParams = ['temperature', 'max_tokens', 'top_p']
          
          // Combine all parameters
          const allParams = [...new Set([...koboldParams, ...standardParams, ...Object.keys(config.parameters || {})])]
          
          // Set the parameters list on the model
          if (!config.model.parameters) {
            config.model.parameters = allParams
          }
          
          // Initialize missing parameters with defaults
          allParams.forEach(param => {
            if (!(param in this.testParameters)) {
              const paramConfig = this.getParamConfig(param)
              this.testParameters[param] = paramConfig.default !== undefined ? paramConfig.default : null
            }
            // Ensure JSON parameters are objects
            if (this.getParamConfig(param).type === 'json' && typeof this.testParameters[param] === 'string') {
              try {
                this.testParameters[param] = JSON.parse(this.testParameters[param])
              } catch (e) {
                this.testParameters[param] = {}
              }
            }
          })
        } else {
          // For other providers, use saved parameters
          if (!config.model.parameters && config.parameters) {
            config.model.parameters = Object.keys(config.parameters)
          }
        }
        
        // Initialize chip inputs for chip-type parameters
        if (config.model.parameters) {
          config.model.parameters.forEach(param => {
            const paramConfig = this.getParamConfig(param)
            if (paramConfig.type === 'chips' && !this.chipInput[param]) {
              this.chipInput[param] = ''
            }
          })
        }
        
        console.log('Selected config:', config)
      }
    },
    

    async sendMessage() {
      if (!this.userInput.trim() || !this.currentConfig || this.isGenerating) {
        return
      }

      const message = this.userInput.trim()
      this.userInput = ''
      this.messages.push({ role: this.messageRole, content: message })
      
      // Only set isGenerating if it's a user message (expecting a response)
      if (this.messageRole === 'user') {
        this.isGenerating = true
      }

      // Initialize debug info
      const startTime = Date.now()
      // Create parameters with streaming setting
      const requestParameters = {
        ...this.testParameters,
        stream: this.enableStreaming
      }
      
      this.lastApiCall = {
        request: {
          config_id: this.currentConfig.id,
          model: this.currentConfig.model,
          provider: this.currentConfig.provider,
          parameters: requestParameters,
          messages: this.messages,
          streaming: this.enableStreaming
        },
        response: null,
        error: null,
        timing: {
          timestamp: startTime,
          duration: null
        }
      }

      try {
        const ws = this.getWebsocket()
        
        // Send chat request with test parameters including streaming
        const requestPayload = {
          type: 'chat_test',
          action: 'generate',
          config_id: this.currentConfig.id,
          messages: this.messages,
          parameters: requestParameters  // Include the test parameters with streaming
        }
        
        ws.send(JSON.stringify(requestPayload))

        // Wait for response
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Generation timeout'))
          }, 60000) // 60 second timeout

          const handler = (event) => {
            try {
              const data = JSON.parse(event.data)
              if (data.type === 'chat_test') {
                if (data.action === 'response') {
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  // Update debug info with response
                  this.lastApiCall.response = {
                    content: data.content,
                    debug: data.debug,
                    raw: data
                  }
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  
                  // Check if we need to handle streaming
                  if (this.enableStreaming && this.messages[this.messages.length - 1]?.role === 'assistant' && 
                      this.messages[this.messages.length - 1]?.isStreaming) {
                    // Append to existing streaming message
                    this.messages[this.messages.length - 1].content += data.content
                  } else {
                    // Add new message
                    this.messages.push({ role: 'assistant', content: data.content })
                  }
                  resolve()
                } else if (data.action === 'error') {
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  // Update debug info with error
                  this.lastApiCall.error = data.message || 'Generation failed'
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  
                  reject(new Error(data.message || 'Generation failed'))
                } else if (data.action === 'stream_chunk') {
                  // Handle streaming chunk
                  if (!this.messages[this.messages.length - 1]?.isStreaming) {
                    // Add new streaming message
                    this.messages.push({ 
                      role: 'assistant', 
                      content: data.content || '',
                      isStreaming: true 
                    })
                  } else {
                    // Append to existing streaming message
                    this.messages[this.messages.length - 1].content += data.content || ''
                  }
                } else if (data.action === 'stream_end') {
                  // Mark streaming as complete
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  if (this.messages[this.messages.length - 1]?.isStreaming) {
                    this.messages[this.messages.length - 1].isStreaming = false
                  }
                  
                  // Update debug info with final response data
                  if (data.debug) {
                    this.lastApiCall.response = {
                      content: data.debug.full_content,
                      debug: data.debug,
                      streaming: true
                    }
                  }
                  
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  resolve()
                } else if (data.action === 'debug_info') {
                  // Handle debug info from backend
                  if (this.lastApiCall) {
                    this.lastApiCall.debug = data.debug
                  }
                }
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }

          ws.addEventListener('message', handler)
        })
      } catch (err) {
        console.error('Failed to generate response:', err)
        
        // Update debug info with error
        if (this.lastApiCall) {
          this.lastApiCall.error = err.message
          this.lastApiCall.timing.duration = Date.now() - startTime
        }
        
        this.$emit('notify', {
          message: `Failed to generate response: ${err.message}`,
          type: 'error'
        })
      } finally {
        this.isGenerating = false
      }
    },

    clearChat() {
      this.messages = []
      this.lastApiCall = null
    },
    
    async redoLastMessage() {
      if (!this.canRedoLastMessage) {
        return
      }
      
      // Remove the last assistant message
      this.messages.pop()
      
      // Find the messages to send (everything except the removed assistant message)
      const messagesToSend = [...this.messages]
      
      // Set generating state
      this.isGenerating = true
      
      // Initialize debug info
      const startTime = Date.now()
      // Create parameters with streaming setting
      const requestParameters = {
        ...this.testParameters,
        stream: this.enableStreaming
      }
      
      this.lastApiCall = {
        request: {
          config_id: this.currentConfig.id,
          model: this.currentConfig.model,
          provider: this.currentConfig.provider,
          parameters: requestParameters,
          messages: messagesToSend,
          note: 'Regenerated with updated parameters',
          streaming: this.enableStreaming
        },
        response: null,
        error: null,
        timing: {
          timestamp: startTime,
          duration: null
        }
      }
      
      try {
        const ws = this.getWebsocket()
        
        // Send chat request with current test parameters including streaming
        const requestPayload = {
          type: 'chat_test',
          action: 'generate',
          config_id: this.currentConfig.id,
          messages: messagesToSend,
          parameters: requestParameters  // Include the current test parameters with streaming
        }
        
        ws.send(JSON.stringify(requestPayload))
        
        // Wait for response
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Generation timeout'))
          }, 60000) // 60 second timeout
          
          const handler = (event) => {
            try {
              const data = JSON.parse(event.data)
              if (data.type === 'chat_test') {
                if (data.action === 'response') {
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  // Update debug info with response
                  this.lastApiCall.response = {
                    content: data.content,
                    debug: data.debug,
                    raw: data
                  }
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  
                  // Check if we need to handle streaming
                  if (this.enableStreaming && this.messages[this.messages.length - 1]?.role === 'assistant' && 
                      this.messages[this.messages.length - 1]?.isStreaming) {
                    // Append to existing streaming message
                    this.messages[this.messages.length - 1].content += data.content
                  } else {
                    // Add new message
                    this.messages.push({ role: 'assistant', content: data.content })
                  }
                  resolve()
                } else if (data.action === 'error') {
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  // Update debug info with error
                  this.lastApiCall.error = data.message || 'Generation failed'
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  
                  reject(new Error(data.message || 'Generation failed'))
                } else if (data.action === 'stream_chunk') {
                  // Handle streaming chunk
                  if (!this.messages[this.messages.length - 1]?.isStreaming) {
                    // Add new streaming message
                    this.messages.push({ 
                      role: 'assistant', 
                      content: data.content || '',
                      isStreaming: true 
                    })
                  } else {
                    // Append to existing streaming message
                    this.messages[this.messages.length - 1].content += data.content || ''
                  }
                } else if (data.action === 'stream_end') {
                  // Mark streaming as complete
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  if (this.messages[this.messages.length - 1]?.isStreaming) {
                    this.messages[this.messages.length - 1].isStreaming = false
                  }
                  
                  // Update debug info with final response data
                  if (data.debug) {
                    this.lastApiCall.response = {
                      content: data.debug.full_content,
                      debug: data.debug,
                      streaming: true
                    }
                  }
                  
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  resolve()
                } else if (data.action === 'debug_info') {
                  // Handle debug info from backend
                  if (this.lastApiCall) {
                    this.lastApiCall.debug = data.debug
                  }
                }
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
          
          ws.addEventListener('message', handler)
        })
      } catch (err) {
        console.error('Failed to regenerate response:', err)
        
        // Update debug info with error
        if (this.lastApiCall) {
          this.lastApiCall.error = err.message
          this.lastApiCall.timing.duration = Date.now() - startTime
        }
        
        this.$emit('notify', {
          message: `Failed to regenerate response: ${err.message}`,
          type: 'error'
        })
      } finally {
        this.isGenerating = false
      }
    },
    
    formatCapabilityName(key) {
      const names = {
        vision: 'Vision',
        reasoning: 'Reasoning',
        function_calling: 'Function Calling',
        web_search: 'Web Search'
      }
      return names[key] || key.split('_').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ')
    },
    
    getRoleColor(role) {
      const colors = {
        user: 'primary',
        assistant: 'success',
        system: 'warning'
      }
      return colors[role] || 'grey'
    },
    
    getRoleIcon(role) {
      const icons = {
        user: 'mdi-account',
        assistant: 'mdi-robot',
        system: 'mdi-cog'
      }
      return icons[role] || 'mdi-message'
    },
    
    getRoleLabel(role) {
      const labels = {
        user: 'User',
        assistant: 'Assistant',
        system: 'System'
      }
      return labels[role] || role
    },
    
    // Parameter configuration methods
    getParamConfig(param) {
      return getParameterConfig(param)
    },
    
    getParametersByType(type) {
      if (!this.currentConfig || !this.currentConfig.model.parameters) {
        return []
      }
      return this.currentConfig.model.parameters.filter(param => {
        const config = getParameterConfig(param)
        return config.type === type
      })
    },
    
    getOtherParameters() {
      if (!this.currentConfig || !this.currentConfig.model.parameters) {
        return []
      }
      return this.currentConfig.model.parameters.filter(param => {
        const config = getParameterConfig(param)
        return !['slider', 'number', 'text'].includes(config.type)
      })
    },
    
    resetParameters() {
      if (this.currentConfig) {
        this.testParameters = { ...this.currentConfig.parameters }
      }
    },
    
    resetToDefaults() {
      if (this.currentConfig && this.currentConfig.model && this.currentConfig.model.parameters) {
        // Reset all parameters to their defaults from the registry
        this.currentConfig.model.parameters.forEach(param => {
          const paramConfig = this.getParamConfig(param)
          if (paramConfig.default !== undefined) {
            this.testParameters[param] = paramConfig.default
          } else {
            // If no default is defined, use reasonable defaults based on type
            switch (paramConfig.type) {
              case 'number':
              case 'slider':
                this.testParameters[param] = 0
                break
              case 'switch':
                this.testParameters[param] = false
                break
              case 'chips':
                this.testParameters[param] = []
                break
              case 'json':
                this.testParameters[param] = {}
                break
              case 'select':
                this.testParameters[param] = paramConfig.options && paramConfig.options[0] || ''
                break
              default:
                this.testParameters[param] = ''
            }
          }
        })
        
        this.$emit('notify', {
          message: 'Parameters reset to defaults',
          type: 'info'
        })
      }
    },
    
    addChip(param) {
      if (!this.chipInput[param] || !this.chipInput[param].trim()) {
        return
      }
      if (!this.testParameters[param]) {
        this.testParameters[param] = []
      }
      this.testParameters[param].push(this.chipInput[param].trim())
      this.chipInput[param] = ''
    },
    
    removeChip(param, index) {
      if (this.testParameters[param] && Array.isArray(this.testParameters[param])) {
        this.testParameters[param].splice(index, 1)
      }
    },
    
    // JSON parameter handling
    getJsonString(value) {
      if (typeof value === 'object' && value !== null) {
        return JSON.stringify(value, null, 2)
      }
      return value || '{}'
    },
    
    updateJsonParam(param, value) {
      try {
        this.testParameters[param] = JSON.parse(value)
      } catch (e) {
        // Keep as string if invalid JSON
        this.testParameters[param] = value
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
    
    async updateConfiguration() {
      if (!this.currentConfig || !this.hasParameterChanges) {
        return
      }
      
      try {
        const ws = this.getWebsocket()
        
        // Prepare update payload with the test parameters
        const updatePayload = {
          type: 'config',
          action: 'save_model_config',
          config_id: this.currentConfig.id,
          name: this.currentConfig.name,
          model: this.currentConfig.model,
          provider: this.currentConfig.provider,
          parameters: this.testParameters,
          created_at: this.currentConfig.created_at
        }
        
        ws.send(JSON.stringify(updatePayload))
        
        // Wait for response
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('Timeout saving configuration'))
          }, 5000)
          
          const handler = (event) => {
            try {
              const data = JSON.parse(event.data)
              if (data.type === 'config' && data.action === 'model_config_save_complete') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                
                // Update the current config with new parameters
                this.currentConfig.parameters = { ...this.testParameters }
                
                // Update the saved config in the list
                const configIndex = this.savedConfigs.findIndex(c => c.id === this.currentConfig.id)
                if (configIndex !== -1) {
                  this.savedConfigs[configIndex].parameters = { ...this.testParameters }
                }
                
                this.$emit('notify', {
                  message: 'Configuration updated successfully',
                  type: 'success'
                })
                
                resolve()
              } else if (data.type === 'config' && data.action === 'model_config_save_error') {
                clearTimeout(timeout)
                ws.removeEventListener('message', handler)
                reject(new Error(data.data.message || 'Failed to save configuration'))
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
          
          ws.addEventListener('message', handler)
        })
      } catch (err) {
        console.error('Failed to update configuration:', err)
        this.$emit('notify', {
          message: `Failed to update configuration: ${err.message}`,
          type: 'error'
        })
      }
    }
  }
}
</script>

<style scoped>
.message-content {
  white-space: pre-wrap;
  word-wrap: break-word;
  margin-top: 8px;
}

.user-message {
  background-color: rgba(33, 150, 243, 0.1);
  padding: 8px 12px;
  border-radius: 8px;
  margin-left: 20%;
}

.assistant-message {
  background-color: rgba(76, 175, 80, 0.1);
  padding: 8px 12px;
  border-radius: 8px;
  margin-right: 20%;
}

.system-message {
  background-color: rgba(255, 152, 0, 0.1);
  padding: 8px 12px;
  border-radius: 8px;
  margin: 0 10%;
  font-style: italic;
}

.debug-pre {
  font-size: 11px;
  line-height: 1.4;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.streaming-cursor {
  animation: blink 1s infinite;
  color: rgba(33, 150, 243, 0.8);
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>