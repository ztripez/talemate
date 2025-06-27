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

      <!-- Model Selection -->
      <v-card-text>
        <v-row>
          <v-col cols="12">
            <v-select
              v-model="selectedConfig"
              :items="savedConfigs"
              :loading="loadingConfigs"
              item-title="name"
              item-value="id"
              label="Select Model Configuration"
              variant="outlined"
              density="compact"
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
        </v-row>

        <v-row>
          <!-- Chat Messages Column -->
          <v-col :cols="showDebugInfo ? 7 : 12">
            <v-card variant="outlined" class="mb-4" style="height: 400px; overflow-y: auto;">
              <v-card-text>
                <v-list density="compact">
                  <v-list-item v-for="(message, index) in messages" :key="index" :class="message.role === 'user' ? 'text-right' : ''">
                    <v-chip :color="message.role === 'user' ? 'primary' : 'secondary'" class="mb-2">
                      {{ message.role === 'user' ? 'You' : 'Assistant' }}
                    </v-chip>
                    <div class="message-content" :class="message.role === 'user' ? 'user-message' : 'assistant-message'">
                      {{ message.content }}
                    </div>
                  </v-list-item>
                  <v-progress-linear v-if="isGenerating" indeterminate color="primary" class="mt-2"></v-progress-linear>
                </v-list>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- Debug Info Column -->
          <v-col v-if="showDebugInfo" cols="5">
            <v-card variant="outlined" style="height: 400px; overflow-y: auto;">
              <v-card-title class="text-h6">Debug Info</v-card-title>
              <v-divider></v-divider>
              <v-card-text>
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
            </v-card>
          </v-col>
        </v-row>

        <!-- Input -->
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
      </v-card-text>

      <v-card-actions>
        <v-btn @click="clearChat" :disabled="messages.length === 0">Clear Chat</v-btn>
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
      isGenerating: false,
      currentConfig: null,
      showDebugInfo: true,
      lastApiCall: null
    }
  },
  watch: {
    dialog(val) {
      if (val) {
        this.loadSavedConfigs()
      }
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
        console.log('Selected config:', config)
      }
    },

    async sendMessage() {
      if (!this.userInput.trim() || !this.currentConfig || this.isGenerating) {
        return
      }

      const message = this.userInput.trim()
      this.userInput = ''
      this.messages.push({ role: 'user', content: message })
      this.isGenerating = true

      // Initialize debug info
      const startTime = Date.now()
      this.lastApiCall = {
        request: {
          config_id: this.currentConfig.id,
          model: this.currentConfig.model,
          provider: this.currentConfig.provider,
          parameters: this.currentConfig.parameters,
          messages: this.messages
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
        
        // Send chat request
        const requestPayload = {
          type: 'chat_test',
          action: 'generate',
          config_id: this.currentConfig.id,
          messages: this.messages
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
                  
                  this.messages.push({ role: 'assistant', content: data.content })
                  resolve()
                } else if (data.action === 'error') {
                  clearTimeout(timeout)
                  ws.removeEventListener('message', handler)
                  
                  // Update debug info with error
                  this.lastApiCall.error = data.message || 'Generation failed'
                  this.lastApiCall.timing.duration = Date.now() - startTime
                  
                  reject(new Error(data.message || 'Generation failed'))
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

.debug-pre {
  font-size: 11px;
  line-height: 1.4;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}
</style>