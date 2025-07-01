<template>
  <v-list-subheader class="text-uppercase"><v-icon>mdi-tune-variant</v-icon>
    Model Presets
    <v-btn @click="hideDisabled = !hideDisabled" size="x-small" v-if="numDisabledPresets > 0">
      <template v-slot:prepend>
        <v-icon>{{ hideDisabled ? 'mdi-eye' : 'mdi-eye-off' }}</v-icon>
      </template>
      {{ hideDisabled ? 'Show disabled' : 'Hide disabled' }} ({{ numDisabledPresets }})
    </v-btn>
  </v-list-subheader>
  <div v-if="isConnected()">
    <div v-for="(preset, index) in state.presets" :key="index">
      <v-list density="compact" v-if="preset.status !== 'disabled' || !hideDisabled">
        <v-list-item>
          <v-list-item-title>
            <v-progress-circular v-if="preset.status === 'busy'" indeterminate="disable-shrink" color="primary"
              size="14"></v-progress-circular>
            
            <v-icon v-else-if="preset.status == 'warning'" color="orange" size="14">mdi-checkbox-blank-circle</v-icon>
            <v-icon v-else-if="preset.status == 'error'" color="red-darken-1" size="14">mdi-checkbox-blank-circle</v-icon>
            <v-btn v-else-if="preset.status == 'disabled'" size="x-small" class="mr-1" variant="tonal" density="comfortable" rounded="sm" @click.stop="togglePreset(preset)" icon="mdi-power-standby"></v-btn>

            <!-- preset status icon -->
            <v-icon v-else color="green" size="14">mdi-checkbox-blank-circle</v-icon>

            <!-- preset name-->
            <span :class="preset.status == 'disabled' ? 'text-grey-darken-2 ml-1' : 'ml-1'"> {{ preset.name }}</span>

            <!-- request information -->
            <AIClientRequestInformation :requestInformation="preset.request_information" />
          </v-list-item-title>
          <div v-if="preset.enabled">
  
            <v-list-item-subtitle class="text-caption" v-if="preset.data.error_action != null">
              <v-btn class="mt-1 mb-1" variant="tonal" :prepend-icon="preset.data.error_action.icon" size="x-small" color="warning" @click.stop="callErrorAction(preset, preset.data.error_action)">
                {{ preset.data.error_action.title }}
              </v-btn>
            </v-list-item-subtitle> 
            <v-list-item-subtitle class="text-caption mb-2">
              {{ preset.model_name }}
            </v-list-item-subtitle>
            <v-list-item-title class="text-caption">
              <div class="d-flex flex-wrap align-center">
                <!-- provider name -->
                <v-chip label size="x-small" color="primary" variant="tonal" class="mb-1 mr-1" prepend-icon="mdi-cloud-outline">{{ preset.data?.provider_name || preset.type }}</v-chip>
                <!-- max context size -->
                <v-chip label size="x-small" color="grey" variant="tonal" class="mb-1 mr-1" prepend-icon="mdi-text-box">{{ preset.data?.max_context_size || preset.max_token_length }}</v-chip>
                <!-- embeddings -->
                <v-chip v-if="preset.embeddings_model_name" label size="x-small" color="grey" variant="tonal" class="mb-1 mr-1" prepend-icon="mdi-cube-unfolded">{{ preset.embeddings_model_name }}</v-chip>
                <!-- override base url -->
                <v-chip  v-if="preset.data.override_base_url" label size="x-small" color="grey" variant="tonal" class="mb-1 mr-1" prepend-icon="mdi-api">{{ preset.data.override_base_url }}</v-chip>
                <!-- rate limit -->
                <v-chip v-if="preset.rate_limit" label size="x-small" color="grey" variant="tonal" class="mb-1 mr-1" prepend-icon="mdi-speedometer">{{ preset.rate_limit }}/min</v-chip>
                <v-menu density="compact">
                  <template v-slot:activator="{ props }">
                    <v-chip v-bind="props" label size="x-small" color="highlight1" variant="tonal" class="mb-1 mr-1" prepend-icon="mdi-tune">{{ preset.preset_group || "Default" }}</v-chip>
                  </template>

                  <v-list density="compact">
                    <v-list-item prepend-icon="mdi-pencil" @click="openAppConfig('presets', 'inference', preset.preset_group)">
                      <v-list-item-title>Edit {{ preset.preset_group || "Default" }} Parameters</v-list-item-title>
                    </v-list-item>
                    <v-list-item prepend-icon="mdi-tune" v-for="presetOption in availablePresets" :key="presetOption.value" @click="preset.preset_group = presetOption.value; savePresetDelayed(preset)">
                      <v-list-item-title>{{ presetOption.title }}</v-list-item-title>
                      <v-list-item-subtitle>Assign this preset</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-menu>

                <!-- data format -->
                <v-chip v-if="preset.data_format" label size="x-small" color="grey" variant="tonal" class="mb-1" prepend-icon="mdi-code-json">{{ preset.data_format.toUpperCase() }}</v-chip>
              </div>
            </v-list-item-title>
            <div density="compact">
              <v-slider
                hide-details
                v-model="preset.max_token_length"
                :min="1024"
                :max="128000"
                :step="1024"
                @update:modelValue="updatePresetMaxTokenLength(preset, $event)"
                @click.stop
                density="compact"
              ></v-slider>
            </div>
            <v-list-item-subtitle class="text-center">
  
              <!-- LLM prompt template warning -->
              <v-tooltip text="Could not determine LLM prompt template for this model. Using default. You can pick a template manually in the client options and new templates can be added in ./templates/llm-prompt" v-if="preset.status === 'idle' && preset.data && !preset.data.has_prompt_template && preset.data.meta.requires_prompt_template" max-width="200">
                <template v-slot:activator="{ props }">
                  <v-icon x-size="14" class="mr-1" v-bind="props" color="orange">mdi-alert</v-icon>
                </template>
              </v-tooltip>
  
              <!-- coercion status -->
              <v-tooltip :text="(preset.data?.double_coercion || preset.double_coercion) ? ('Coercion active: ' + (preset.data?.double_coercion || preset.double_coercion)) : 'No coercion set'" max-width="200">
                <template v-slot:activator="{ props }">
                  <v-icon x-size="14" class="mr-1" v-bind="props" :color="(preset.data?.double_coercion || preset.double_coercion) ? 'primary' : 'grey'">mdi-account-lock-open</v-icon>
                </template>
              </v-tooltip>
  
              <!-- disable/enable -->
              <v-tooltip :text="preset.enabled ? 'Disable':'Enable'">
                <template v-slot:activator="{ props }">
                  <v-btn size="x-small" class="mr-1" v-bind="props" variant="tonal" density="comfortable" rounded="sm" @click.stop="togglePreset(preset)" icon="mdi-power-standby"></v-btn>
                </template>
              </v-tooltip>
  
              <!-- edit preset button -->
              <v-tooltip text="Edit preset">
                <template v-slot:activator="{ props }">
                  <v-btn size="x-small" class="mr-1" v-bind="props" variant="tonal" density="comfortable" rounded="sm" @click.stop="editPreset(index)" icon="mdi-cogs"></v-btn>
  
                </template>
              </v-tooltip>
  
              <!-- assign to all agents button -->
              <v-tooltip text="Assign to all agents">
                <template v-slot:activator="{ props }">
                  <v-btn size="x-small" class="mr-1" v-bind="props" variant="tonal" density="comfortable" rounded="sm" @click.stop="assignPresetToAllAgents(index)" icon="mdi-transit-connection-variant"></v-btn>
                </template>
              </v-tooltip>
              
              <!-- delete the preset button -->
              <v-tooltip text="Delete preset">
                <template v-slot:activator="{ props }">
                  <v-btn size="x-small" class="mr-1" v-bind="props" variant="tonal" density="comfortable" rounded="sm" @click.stop="deletePreset(index)" icon="mdi-close-thick"></v-btn>
                </template>
              </v-tooltip>
              
            </v-list-item-subtitle>
          </div>
        </v-list-item>
      </v-list>
    </div>

    <ClientModal 
      :dialog="state.dialog" 
      :formTitle="state.formTitle" 
      :immutable-config="immutableConfig"
      :available-presets="availablePresets"
      @save="savePreset" 
      @error="propagateError" 
      @update:dialog="updateDialog">
    </ClientModal>
    <v-alert type="warning" variant="tonal" v-if="state.presets.length === 0">You have no model presets configured. Add one.</v-alert>
    <v-btn @click="openModal" elevation="0" prepend-icon="mdi-plus-box">Add Model Preset</v-btn>
  </div>
</template>
  
<script>
import ClientModal from './ClientModal.vue';
import AIClientRequestInformation from './AIClientRequestInformation.vue';

export default {
  props: {
    immutableConfig: Object,
  },
  components: {
    ClientModal,
    AIClientRequestInformation,
  },
  data() {
    return {
      saveDelayTimeout: null,
      clientStatusCheck: null,
      hideDisabled: true,
      clientImmutable: {},
      state: {
        presets: [],
        dialog: false,
        currentClient: {
          name: '',
          type: '',
          api_url: '',
          model_name: '',
          max_token_length: 8192,
          double_coercion: null,
          rate_limit: null,
          data_format: null,
          data: {
            has_prompt_template: false,
          }
        }, // Add a new field to store the model name
        formTitle: ''
      }
    }
  },
  computed: {
    availablePresets() {
      let items = [{ title: 'Default', value: '' }]
      if(!this.immutableConfig || !this.immutableConfig.presets) {
        return items;
      }
      const inferenceGroups = this.immutableConfig.presets.inference_groups;
      if(!inferenceGroups || !Object.keys(inferenceGroups).length) {
        return items;
      }
      
      for (const [key, value] of Object.entries(inferenceGroups)) {
        items.push({
          title: value.name,
          value: key,
        });
      }

      // sort by name
      items.sort((a, b) => a.title.localeCompare(b.title));

      return items;
    },
    visiblePresets: function() {
      return this.state.presets.filter(preset => !this.hideDisabled || preset.status !== 'disabled');
    },
    numDisabledPresets: function() {
      return this.state.presets.filter(preset => preset.status === 'disabled').length;
    }
  },
  inject: [
    'getWebsocket',
    'registerMessageHandler',
    'isConnected',
    'getAgents',
    'openAppConfig',
  ],
  provide() {
    return {
      state: this.state
    };
  },
  emits: [
    'model-presets-updated',
    'client-assigned',
    'open-app-config',
    'open-model-browser',
    'save',
    'error',
  ],
  methods: {

    callErrorAction(client, action) {
      if(action.action_name === 'openAppConfig') {
        this.$emit('open-app-config', ...action.arguments);
      }
    },

    configurationRequired() {
      if(this.state.presets.length === 0) {
        return true;
      }

      // cycle through presets and check if any are status 'error' or 'warning'
      for (let i = 0; i < this.state.presets.length; i++) {
        if (this.state.presets[i].status === 'error' || this.state.presets[i].status === 'warning') {
          return true;
        }
      }

      return false;
    },
    getActive() {
      return this.state.presets.find(a => a.status === 'busy');      
    },
    openModal() {
      // Open the model browser instead of the old client form
      this.$emit('open-model-browser');
    },
    propagateError(error) {
      this.$emit('error', error);
    },

    updatePresetMaxTokenLength(preset, newValue) {
      preset.max_token_length = newValue;
      
      // Also update the data field
      if (preset.config_id && preset.data) {
        preset.data.max_context_size = newValue;
      }
      
      this.savePresetDelayed(preset);
    },

    updateModelConfigContextSize(configId, maxContextSize) {
      this.getWebsocket().send(JSON.stringify({
        type: 'update_model_config_context_size',
        config: {
          config_id: configId,
          max_context_size: maxContextSize
        }
      }));
    },

    updateModelPreset(client) {
      // Debug: Log what we're about to send to backend
      console.log('updateModelPreset - client object:', client);
      console.log('updateModelPreset - double_coercion value:', client.double_coercion);
      
      // Ensure system_prompts is an object, not a string
      let systemPrompts = client.system_prompts;
      if (typeof systemPrompts === 'string') {
        // If it's a string, convert it to an empty object
        systemPrompts = {};
      } else if (!systemPrompts || typeof systemPrompts !== 'object') {
        // If it's null/undefined or not an object, use empty object
        systemPrompts = {};
      }
      
      // Send model preset update to backend
      const payload = {
        type: 'config',
        action: 'update_model_preset',
        config_id: client.config_id,
        double_coercion: client.double_coercion,
        max_context_size: client.max_token_length,
        system_prompts: systemPrompts,
        enabled: client.enabled
      };
      
      console.log('updateModelPreset - sending payload:', payload);
      this.getWebsocket().send(JSON.stringify(payload));
    },

    savePresetDelayed(preset) {
      preset.dirty = true;
      if (this.saveDelayTimeout) {
        clearTimeout(this.saveDelayTimeout);
      }
      this.saveDelayTimeout = setTimeout(() => {
        this.savePreset(preset);
        preset.dirty = false;
      }, 500);
    },

    savePreset(preset) {
      // Debug: Log the coercion value being saved
      console.log('Saving preset - double_coercion:', preset.double_coercion);
      
      const index = this.state.presets.findIndex(p => p.config_id === preset.config_id);
      if (index === -1) {
        this.state.presets.push(preset);
      } else {
        this.state.presets[index] = preset;
      }
      this.state.dialog = false; // Close the dialog after saving the preset
      
      // Clear dirty flag to allow backend updates to be received
      preset.dirty = false;
      
      // Send update to backend
      this.updateModelPreset(preset);
      this.$emit('model-presets-updated', this.state.presets);
    },
    editPreset(index) {
      console.log('editPreset called - index:', index);
      console.log('editPreset - preset in array:', this.state.presets[index]);
      console.log('editPreset - preset coercion value:', this.state.presets[index].double_coercion);
      
      this.state.currentClient = { ...this.state.presets[index] };
      // Ensure compatibility fields for ClientModal
      this.state.currentClient.can_be_coerced = true; // Model presets can always be coerced
      
      // Debug: Log the initial coercion value after copy
      console.log('Editing preset - after copy double_coercion:', this.state.currentClient.double_coercion);
      console.log('Editing preset - full currentClient object:', this.state.currentClient);
      
      this.state.formTitle = 'Edit Model Preset';
      this.state.dialog = true;
    },
    deletePreset(index) {
      if (window.confirm('Are you sure you want to delete this preset?')) {
        this.clientImmutable[this.state.presets[index].name] = true;
        this.state.presets.splice(index, 1);
        this.$emit('model-presets-updated', this.state.presets);
      }
    },
    assignPresetToAllAgents(index) {
      let agents = this.getAgents();
      let preset = this.state.presets[index];

      this.savePreset(preset);

      for (let i = 0; i < agents.length; i++) {
        agents[i].client = preset.name;
        console.log("Assigning preset", preset.name, "to agent", agents[i].name);
      }
      this.$emit('client-assigned', agents);
    },

    togglePreset(preset) {
      console.log("Toggling preset", preset.enabled, "to", !preset.enabled)
      this.clientImmutable[preset.name] = true;
      preset.enabled = !preset.enabled;
      if(preset.enabled) {
        preset.status = 'warning';
      } else {
        preset.status = 'disabled';
      }
      this.savePreset(preset);
    },

    updateDialog(newVal) {
      this.state.dialog = newVal;
    },
    handleMessage(data) {
      // Handle model_preset_status message type
      if (data.type === 'model_preset_status') {
        
        if(this.clientImmutable[data.name]) {
          console.log("Ignoring model_preset_status message for immutable preset", data.name)
          delete this.clientImmutable[data.name]
          return;
        }

        // Find the preset with the given config_id
        const preset = this.state.presets.find(preset => preset.config_id === data.config_id);

        if (preset && !preset.dirty) {
          // Debug: Log what we're updating
          console.log('Updating preset from backend response:', {
            config_id: data.config_id,
            old_coercion: preset.double_coercion,
            new_coercion: data.data.double_coercion,
            preset_dirty: preset.dirty
          });
          
          // Update the model preset information
          preset.name = data.name;  // Human-readable display name
          preset.config_id = data.config_id;  // UUID for backend operations
          preset.model_name = data.model_name;
          preset.model = data.model_name;
          preset.type = data.message; // provider name
          preset.status = data.status;
          preset.enabled = data.data.enabled;
          preset.max_token_length = data.data.max_context_size || 8192;
          preset.double_coercion = data.data.double_coercion;
          preset.system_prompts = data.data.system_prompts || {};
          
          // Debug: Confirm the update
          console.log('Preset updated - new coercion:', preset.double_coercion);
          preset.data = {
            ...data.data,
            // For backward compatibility with existing template checks
            meta: data.data.meta || { extra_fields: {}, defaults: {} },
            has_prompt_template: true, // ModelPresets always have templates
            enabled: data.data.enabled,
          };
          // Ensure compatibility fields for ClientModal
          preset.can_be_coerced = true; // Model presets can always be coerced
          preset.preset_group = "";
          preset.request_information = null;

        } else if(!preset) {
          console.log("Adding new model preset", data);

          this.state.presets.push({ 
            name: data.name,  // Human-readable display name
            config_id: data.config_id,  // UUID for backend operations
            model_name: data.model_name, 
            model: data.model_name,
            type: data.message, // provider name
            status: data.status,
            enabled: data.data.enabled,
            max_token_length: data.data.max_context_size || 8192,
            double_coercion: data.data.double_coercion,
            system_prompts: data.data.system_prompts || {},
            data: {
              ...data.data,
              // For backward compatibility with existing template checks
              meta: data.data.meta || { extra_fields: {}, defaults: {} },
              has_prompt_template: true, // ModelPresets always have templates
              enabled: data.data.enabled,
            },
            // Ensure compatibility fields for ClientModal
            can_be_coerced: true, // Model presets can always be coerced
            preset_group: "",
            request_information: null,
          });

          // sort the presets by name
          this.state.presets.sort((a, b) => (a.name > b.name) ? 1 : -1);
        }

        return;
      }

    }
  },
  created() {
    this.registerMessageHandler(this.handleMessage);
  },
}
</script>
<style scoped>
.hidden {
  display: none !important;
}
</style>