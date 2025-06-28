from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import litellm

@dataclass
class ProviderSetting:
    """Represents a single provider setting that can be configured in the frontend"""
    key: str
    label: str
    type: str  # "text", "password", "number", "boolean", "select"
    required: bool = True
    default: Any = None
    description: str = ""
    options: Optional[List[str]] = None  # For select type
    advanced: bool = False  # Whether this setting should be hidden behind advanced toggle
    hidden: bool = False  # Whether this setting should be completely hidden

@dataclass
class LiteLLMProviderConfig:
    provider_identifier: str
    settings: Dict[str, Any] = field(default_factory=dict)

class BaseProvider(ABC):
    """Base class for all LiteLLM providers"""
    
    def __init__(self):
        self._config: Optional[LiteLLMProviderConfig] = None
    
    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """Return the human-readable name of this provider"""
        pass
    
    @classmethod
    @abstractmethod
    def get_provider_identifier(cls) -> str:
        """Return the litellm provider identifier"""
        pass
    
    @classmethod
    @abstractmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        """Return the settings schema for frontend configuration"""
        pass
    
    @classmethod
    def is_multi_instance(cls) -> bool:
        """Return whether this provider supports multiple instances"""
        return False
    
    def set_config(self, config: LiteLLMProviderConfig):
        """Set the provider configuration"""
        self._config = config
    
    @property
    def config(self) -> LiteLLMProviderConfig:
        if not self._config:
            raise Exception("Provider not configured")
        return self._config
    
    def _build_litellm_params(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """Build parameters for litellm call"""
        full_model_name = f"{self.get_provider_identifier()}/{model_name}"
        
        # Get supported parameters for this provider/model
        try:
            supported_params = set(self.get_model_parameters(full_model_name))
            # Always include core parameters that LiteLLM expects
            supported_params.update(['model', 'messages', 'api_key', 'api_base', 'api_version', 'organization'])
        except Exception:
            # Fallback to common parameters if we can't get the supported list
            supported_params = {
                'model', 'messages', 'temperature', 'max_tokens', 'top_p', 'frequency_penalty', 
                'presence_penalty', 'stop', 'stream', 'n', 'logprobs', 'top_logprobs',
                'api_key', 'api_base', 'api_version', 'organization'
            }
        
        # Filter kwargs to only include supported parameters with meaningful values
        filtered_kwargs = {}
        for key, value in kwargs.items():
            # Skip if parameter not supported
            if key not in supported_params:
                continue
            # Skip None values and empty strings
            if value is None or value == '':
                continue
            # Skip empty collections
            if isinstance(value, (list, dict)) and not value:
                continue
            # Skip default/invalid values for specific parameters
            if key == 'logit_bias' and (not value or value == {}):
                continue
            # Skip meaningless default values that cause API errors
            if key == 'response_format' and value == 'text':
                continue
            if key == 'tool_choice' and value == 'auto' and 'tools' not in kwargs:
                continue
            if key == 'n' and value == 1:
                continue
            if key == 'stream' and value is False:
                continue
            # Skip parameters with empty string values that are meant to be objects
            if key in ['tools', 'functions', 'stream_options', 'modalities', 'web_search_options'] and value == '':
                continue
            
            filtered_kwargs[key] = value
        
        params = {
            "model": full_model_name,
            **filtered_kwargs
        }
        
        # Add provider-specific settings (only the standard LiteLLM ones)
        for key, value in self.config.settings.items():
            if key in ['api_key', 'api_base', 'api_version', 'organization'] and value:
                params[key] = value
        
        return params

    
    def get_available_models(self, settings: Dict[str, Any] = None) -> List[str]:
        """Get available models for this provider using LiteLLM"""
        try:
            # Use LiteLLM to get models for this provider
            import litellm
            
            # Try different methods to get models
            try:
                models = litellm.get_valid_models(custom_llm_provider=self.get_provider_identifier(),check_provider_endpoint=True)
                if models:
                    return models
            except:
                pass
                
            # Alternative method - check if litellm has model list functions
            try:
                if hasattr(litellm, 'model_list'):
                    all_models = litellm.model_list
                    provider_id = self.get_provider_identifier()
                    # Filter models for this provider
                    provider_models = [m for m in all_models if m.startswith(f"{provider_id}/")]
                    if provider_models:
                        return [m.split("/", 1)[1] for m in provider_models]  # Remove prefix
            except:
                pass
                
            # Final fallback - return empty list
            return []
            
        except Exception as e:
            # Fallback to empty list if LiteLLM can't fetch models
            return []
    
    def format_model_name(self, model_name: str, settings: Dict[str, Any] = None) -> str:
        """Format model name for LiteLLM - override in subclasses if needed"""
        return f"{self.get_provider_identifier()}/{model_name}"
    
    def get_models_with_capabilities(self, settings: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get models with capabilities for this provider"""
        models = self.get_available_models(settings)
        enhanced_models = []
        
        for model in models:
            model_name = model if isinstance(model, str) else model.get("name", "unknown")
            
            # Clean up the model name - remove any provider prefixes
            clean_name = model_name
            if '/' in clean_name:
                # Remove provider prefix(es) - keep only the last part
                clean_name = clean_name.split('/')[-1]
            
            # Format model name for LiteLLM API calls
            # If model already has provider prefix, don't add another one
            if model_name.startswith(f"{self.get_provider_identifier()}/"):
                full_model_name = model_name
            else:
                full_model_name = self.format_model_name(clean_name, settings)
            
            enhanced_models.append({
                "name": clean_name,
                "display_name": self.format_display_name(clean_name),
                "full_name": full_model_name,
                "capabilities": self.get_model_capabilities(full_model_name),
                "parameters": self.get_model_parameters(full_model_name)
            })
        
        return enhanced_models
    
    def format_display_name(self, model_name: str) -> str:
        """Format model name for display - make it more readable"""
        # Handle common model name patterns
        name = model_name
        
        # Replace common separators with spaces
        name = name.replace('-', ' ').replace('_', ' ')
        
        # Handle version numbers
        import re
        # Replace patterns like "r1 0528" with "R1 (05-28)"
        name = re.sub(r'r(\d+)\s+(\d{4})', lambda m: f'R{m.group(1)} ({m.group(2)[:2]}-{m.group(2)[2:]})', name)
        
        # Capitalize words properly
        words = name.split()
        formatted_words = []
        for word in words:
            if word.upper() in ['GPT', 'AI', 'LLM', 'API', 'XL', 'XXL']:
                formatted_words.append(word.upper())
            elif word.lower() in ['v1', 'v2', 'v3', 'v4']:
                formatted_words.append(word.lower())
            elif len(word) > 1:
                formatted_words.append(word.capitalize())
            else:
                formatted_words.append(word)
        
        return ' '.join(formatted_words)
    
    def get_model_capabilities(self, model_name: str) -> Dict[str, bool]:
        """Get model capabilities using LiteLLM SDK"""
        try:
            import litellm
            capabilities = {}
            
            # Try to get capabilities, but handle missing functions gracefully
            try:
                capabilities["vision"] = litellm.supports_vision(model=model_name)
            except (AttributeError, Exception):
                capabilities["vision"] = False
                
            try:
                capabilities["reasoning"] = litellm.supports_reasoning(model=model_name) 
            except (AttributeError, Exception):
                capabilities["reasoning"] = False
                
            try:
                capabilities["function_calling"] = litellm.supports_function_calling(model=model_name)
            except (AttributeError, Exception):
                capabilities["function_calling"] = False
                
            try:
                capabilities["web_search"] = litellm.supports_web_search(model=model_name)
            except (AttributeError, Exception):
                capabilities["web_search"] = False
                
            return capabilities
        except Exception:
            return {
                "vision": False,
                "reasoning": False, 
                "function_calling": False,
                "web_search": False
            }
    
    def get_model_parameters(self, model_name: str) -> List[str]:
        """Get supported parameters for a model using LiteLLM SDK"""
        try:
            params = litellm.get_supported_openai_params(model=model_name, custom_llm_provider=self.get_provider_identifier())
            return params if params else ["temperature", "max_tokens", "top_p"]
        except (AttributeError, Exception):
            return ["temperature", "max_tokens", "top_p"]


