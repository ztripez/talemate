from typing import Dict, List, Type, Optional, Any
from .base_provider import BaseProvider, LiteLLMProviderConfig, ProviderSetting
import litellm

class ProviderRegistry:
    """Registry for managing LiteLLM providers"""
    
    def __init__(self):
        self._providers: Dict[str, Type[BaseProvider]] = {}
        self._instances: Dict[str, BaseProvider] = {}
    
    def register_provider(self, provider_class: Type[BaseProvider]):
        """Register a provider class"""
        identifier = provider_class.get_provider_identifier()
        self._providers[identifier] = provider_class
    
    def get_available_providers(self) -> List[Dict[str, any]]:
        """Get list of available providers with their metadata"""
        providers = []
        for identifier, provider_class in self._providers.items():
            providers.append({
                "identifier": identifier,
                "name": provider_class.get_provider_name(),
                "multi_instance": provider_class.is_multi_instance(),
                "settings_schema": [
                    {
                        "key": setting.key,
                        "label": setting.label,
                        "type": setting.type,
                        "required": setting.required,
                        "default": setting.default,
                        "description": setting.description,
                        "options": setting.options,
                        "advanced": setting.advanced,
                        "hidden": setting.hidden
                    }
                    for setting in provider_class.get_settings_schema()
                ]
            })
        return providers
    
    def create_provider_instance(self, identifier: str, settings: Dict[str, any]) -> BaseProvider:
        """Create and configure a provider instance"""
        if identifier not in self._providers:
            raise ValueError(f"Unknown provider: {identifier}")
        
        provider_class = self._providers[identifier]
        instance = provider_class()
        
        config = LiteLLMProviderConfig(
            provider_identifier=identifier,
            settings=settings
        )
        instance.set_config(config)
        
        # Cache the instance
        self._instances[identifier] = instance
        
        return instance
    
    def get_provider_instance(self, identifier: str) -> Optional[BaseProvider]:
        """Get cached provider instance"""
        return self._instances.get(identifier)
    
    def get_provider_settings_schema(self, identifier: str) -> List[ProviderSetting]:
        """Get settings schema for a specific provider"""
        if identifier not in self._providers:
            raise ValueError(f"Unknown provider: {identifier}")
        
        return self._providers[identifier].get_settings_schema()
# Global registry instance
registry = ProviderRegistry()