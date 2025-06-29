from typing import Dict, Any
from dataclasses import dataclass, field
import structlog

log = structlog.get_logger("talemate.model_preset")

@dataclass
class ModelConfig:
    """Represents the structured model configuration data"""
    config_id: str
    provider_name: str
    model_name: str
    model_full_name: str
    provider_instance_id: str
    capabilities: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    max_context_size: int | None = None  # User-configured context size override
    
    @classmethod
    def from_config_data(cls, config_id: str, model_config_data: Dict[str, Any]) -> 'ModelConfig':
        """Create ModelConfig from raw model config data"""
        # Extract provider info from the nested structure
        provider_info = model_config_data.get("provider", {})
        provider_name = provider_info.get("provider_name", "")
        
        # Extract model info
        model_info = model_config_data.get("model", {})
        model_name = model_info.get("name", "")
        full_name = model_info.get("full_name", "")
        
        # Extract instance ID (this is stored as provider_id in model config)
        instance_id = provider_info.get("provider_id", "")
        
        # Extract capabilities and parameters
        capabilities = model_info.get("capabilities", {})
        parameters = model_config_data.get("parameters", {})
        
        # Extract user-configured context size override
        max_context_size = model_info.get("max_context_size") or parameters.get("max_context_size")
        if max_context_size:
            max_context_size = int(max_context_size)
        
        # Debug: Log model info to see available fields (only on creation)
        log.debug(f"Model info for {model_name}: {model_info}")
        log.debug(f"Capabilities: {capabilities}")
        log.debug(f"Parameters: {parameters}")
        log.debug(f"Max context size override: {max_context_size}")
        
        return cls(
            config_id=config_id,
            provider_name=provider_name,
            model_name=model_name,
            model_full_name=full_name,
            provider_instance_id=instance_id,
            capabilities=capabilities,
            parameters=parameters,
            max_context_size=max_context_size
        )

@dataclass
class ModelPreset:
    """
    Bridge between new LiteLLM providers and old client system.
    Represents a configured model that can provide both new and old client interfaces.
    Now serves as the primary interface for agent LLM access.
    """
    model_config: ModelConfig
    
    def __post_init__(self):
        self._provider_instance = None
        self._old_client = None
        self._scene_config = None  # Cache scene config for consistent provider access
    
    @classmethod
    def from_model_config(cls, config_id: str, model_config_data: Dict[str, Any]) -> 'ModelPreset':
        """Create ModelPreset from model config data"""
        model_config = ModelConfig.from_config_data(config_id, model_config_data)
        return cls(model_config=model_config)
    
    def get_provider_instance(self, config):
        """Get or create the LiteLLM provider instance"""
        if self._provider_instance is None:
            from talemate.llm_providers import registry
            
            # Get provider settings using instance ID
            litellm_providers = getattr(config, "litellm_providers", {})
            provider_settings = litellm_providers.get(self.model_config.provider_instance_id, {})
            if not provider_settings:
                log.warning(f"Provider settings not found for instance: {self.model_config.provider_instance_id}")
                return None
            
            # Get the actual provider type from settings
            base_provider_id = provider_settings.get("provider_id")
            if not base_provider_id:
                log.warning(f"Provider settings missing provider_id for instance: {self.model_config.provider_instance_id}")
                return None
            
            # Get the provider class using the actual provider type
            provider_class = registry.get_provider(base_provider_id)
            if not provider_class:
                log.warning(f"Unknown provider type: {self.model_config.provider_name} (id: {base_provider_id})")
                return None
            
            # Create provider instance and configure it
            provider_instance = provider_class()
            from talemate.llm_providers.base_provider import LiteLLMProviderConfig
            provider_config = LiteLLMProviderConfig(
                provider_identifier=base_provider_id,
                settings=provider_settings
            )
            provider_instance.set_config(provider_config)
            
            self._provider_instance = provider_instance
        
        return self._provider_instance
    
    def get_old_client(self, config, name: str | None = None):
        """Get or create the old client instance"""
        if self._old_client is None:
            provider_instance = self.get_provider_instance(config)
            if not provider_instance:
                return None
            
            from talemate.client import registry
            
            client_type = provider_instance.get_old_client_type()
            client_class = registry.get_client_class(client_type)
            
            if not client_class:
                log.error(f"No client class found for type: {client_type}")
                return None
            
            # Create a user-friendly client name
            if name:
                client_name = name
            elif self.model_config.model_name:
                client_name = f"{self.model_config.provider_name} - {self.model_config.model_name}"
            else:
                client_name = f"{self.model_config.provider_name} - {self.model_config.config_id}"
            
            # Extract settings from the provider config
            settings = provider_instance._config.settings if provider_instance._config else {}
            
            # Validate model name for OpenRouter
            if self.model_config.provider_name.lower() == "openrouter":
                # Ensure model name has proper format for OpenRouter
                model_name = self.model_config.model_name
                if not model_name.startswith(('openai/', 'anthropic/', 'google/', 'deepseek/', 'meta-llama/', 'mistralai/', 'cohere/')):
                    # If it's a bare model name like "deepseek-r1-0528", try to fix it
                    if 'deepseek' in model_name.lower():
                        if 'r1' in model_name.lower():
                            self.model_config.model_name = "deepseek/deepseek-r1"
                            log.warning(f"Fixed invalid OpenRouter model name: {model_name} -> deepseek/deepseek-r1")
                        else:
                            self.model_config.model_name = "deepseek/deepseek-chat"
                            log.warning(f"Fixed invalid OpenRouter model name: {model_name} -> deepseek/deepseek-chat")
            
            # Create kwargs for the client
            # Get context size with priority: model config override > config clients section > provider detection > none
            max_tokens = None
            
            # First priority: Check for user-configured context size override in model config
            if self.model_config.max_context_size:
                max_tokens = self.model_config.max_context_size
                log.info(f"Using model config context size override for {self.model_config.model_name}: {max_tokens}")
            else:
                # Second priority: Check config clients section for saved user preference
                clients_config = getattr(config, 'clients', {})
                client_config = clients_config.get(client_name) if hasattr(clients_config, 'get') else getattr(clients_config, client_name, None)
                if client_config and hasattr(client_config, 'max_token_length') and client_config.max_token_length:
                    max_tokens = client_config.max_token_length
                    log.info(f"Using config client context size for {self.model_config.model_name}: {max_tokens}")
                
                if not max_tokens:
                    # Third priority: Get from provider detection
                    provider_instance = self.get_provider_instance(config)
                    if provider_instance:
                        max_tokens = provider_instance.get_model_context_size(self.model_config.model_name)
                        
                        if max_tokens:
                            log.info(f"Using provider detected context size for {self.model_config.model_name}: {max_tokens}")
                        else:
                            log.warning(f"Provider could not detect context size for {self.model_config.model_name}")
                    else:
                        log.error(f"Could not get provider instance for context size detection")
            
            client_kwargs = {
                "name": client_name,
                "enabled": True,
                "model_name": self.model_config.model_name,
                "model_config_id": self.model_config.config_id,  # Link to model config for frontend
            }
            
            # Only set max_token_length if we actually detected a value
            if max_tokens:
                client_kwargs["max_token_length"] = max_tokens
                log.info(f"Creating client with detected max_token_length: {max_tokens}")
            else:
                log.info(f"Creating client without max_token_length - will use client defaults")
            
            # Add API key if available
            if "api_key" in settings:
                client_kwargs["api_key"] = settings["api_key"]
            
            # Add API base/URL if available
            if "api_base" in settings:
                client_kwargs["api_url"] = settings["api_base"]
            elif "base_url" in settings:
                client_kwargs["api_url"] = settings["base_url"]
            
            # Create the client instance
            try:
                client = client_class(**client_kwargs)
                
                # Add reference to this ModelPreset so the client can access providers
                client.model_preset = self
                
                # Register the client in the global registry so it appears in frontend
                # Use client_name as the key to match what client status emissions use
                import talemate.instance as instance
                instance.set_client(client_name, client)
                
                self._old_client = client
                log.info(
                    "Created old client from ModelPreset",
                    client_name=client_name,
                    client_type=client_type,
                    model=self.model_config.model_name,
                )
                
            except Exception as e:
                log.error(f"Failed to create client for {client_name}: {e}")
                return None
        
        return self._old_client
    
    def set_scene_config(self, config):
        """Set the scene config for consistent provider/client access"""
        self._scene_config = config
    
    def get_provider(self, config=None):
        """Get provider instance for agents - simplified interface"""
        if config is None:
            config = self._scene_config
        if config is None:
            log.warning("No scene config available for provider access")
            return None
        return self.get_provider_instance(config)
    
    def get_client(self, config=None, name: str | None = None):
        """Get old client instance for agents - simplified interface"""
        if config is None:
            config = self._scene_config
        if config is None:
            log.warning("No scene config available for client access")
            return None
        return self.get_old_client(config, name)
    
    @property
    def model_name(self):
        """Quick access to model name"""
        return self.model_config.model_name
    
    @property
    def provider_name(self):
        """Quick access to provider name"""
        return self.model_config.provider_name
    
    @property
    def config_id(self):
        """Quick access to config ID"""
        return self.model_config.config_id
    
    async def request_clean(self, uid: str, vars: dict, response_model=None, **kwargs):
        """Request using clean prompt system with instructor for structured output"""
        from talemate.llm_providers.prompt_handler import CleanPrompt
        
        provider = self.get_provider()
        if not provider:
            raise RuntimeError("No provider available")
            
        # Parse UID
        agent_type, prompt_name = uid.split(".", 1) if "." in uid else ("", uid)
        
        # Create clean prompt
        prompt = CleanPrompt(
            uid=uid,
            agent_type=agent_type,
            name=prompt_name,
            vars=vars
        )
        
        # Render prompt text
        prompt_text = prompt.render()
        
        # Get system message from client
        kind = kwargs.get('kind', 'create')
        client = self.get_client()
        system_message = ""
        if client:
            system_message = client.get_system_message(kind)
        
        # Build messages for LiteLLM
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt_text}
        ]
        
        # Get generation parameters
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 512)
        
        # Generate with instructor
        response = await provider.generate(
            messages=messages,
            model_name=self.model_name,
            response_model=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response
    
    def to_client_dict(self, config, name: str | None = None):
        """Convert to the old client dictionary format expected by websocket_server"""
        client = self.get_old_client(config, name)
        if not client:
            return None
        
        provider_instance = self.get_provider_instance(config)
        if not provider_instance:
            return None
        
        return {
            "client": client,
            "name": client.name,
            "type": provider_instance.get_old_client_type(),
            "enabled": True,
            "model_preset": self,  # Add ModelPreset reference for agent access
        }