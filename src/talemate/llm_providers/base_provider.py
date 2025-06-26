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
        params = {
            "model": f"{self.get_provider_identifier()}/{model_name}",
            **kwargs
        }
        
        # Add provider-specific settings
        for key, value in self.config.settings.items():
            if key == "api_key":
                params["api_key"] = value
            elif key == "api_base":
                params["api_base"] = value
            elif key == "api_version":
                params["api_version"] = value
            elif key == "organization":
                params["organization"] = value
            else:
                params[key] = value
        
        return params
    
    async def acompletion(self, model_name: str, messages: List[Dict[str, Any]], **kwargs):
        """Make an async completion call"""
        params = self._build_litellm_params(model_name, messages=messages, **kwargs)
        return await litellm.acompletion(**params)
    
    async def get_available_models(self) -> List[str]:
        """Get available models for this provider"""
        try:
            return litellm.utils.get_valid_models(
                custom_llm_provider=self.get_provider_identifier()
            )
        except Exception:
            return []


