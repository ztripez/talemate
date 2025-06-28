
import os
import importlib
import inspect
from pathlib import Path
import litellm
from .base_provider import BaseProvider, ProviderSetting, LiteLLMProviderConfig
from .provider_registry import registry, ProviderRegistry

litellm.set_verbose = True
litellm.drop_params = True  # Set globally as well
# Auto-discover and register all providers
current_dir = Path(__file__).parent
for file in current_dir.glob("*.py"):
    if file.name.startswith("_") or file.name in ["base_provider.py", "provider_registry.py"]:
        continue
    
    module_name = file.stem
    try:
        module = importlib.import_module(f".{module_name}", package=__name__)
        
        # Find all BaseProvider subclasses in the module
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseProvider) and 
                obj != BaseProvider and
                obj.__module__ == module.__name__):
                registry.register_provider(obj)
    except Exception as e:
        print(f"Failed to load provider from {module_name}: {e}")

# Auto-register custom LiteLLM providers
def register_custom_litellm_providers():
    """
    Automatically discover and register any custom LiteLLM providers.
    Looks for classes that inherit from litellm.llms.custom_llm.CustomLLM
    and have a provider identifier attribute.
    """
    from litellm.llms.custom_llm import CustomLLM
    from litellm.types.utils import LlmProviders
    from enum import Enum
    
    registered_providers = []
    
    # Scan all loaded modules for CustomLLM subclasses
    for module_name, module in sys.modules.items():
        if not module_name.startswith('talemate.llm_providers.'):
            continue
            
        try:
            for name, obj in inspect.getmembers(module):
                # Check if it's a CustomLLM subclass
                if (inspect.isclass(obj) and
                    issubclass(obj, CustomLLM) and
                    obj != CustomLLM and
                    hasattr(module, '_identifier_')):
                    
                    provider_id = module._identifier_
                    
                    # Skip if already registered
                    if any(p.get('provider') == provider_id for p in litellm.custom_provider_map):
                        continue
                    
                    # Create handler instance without base_url - api_base should be passed dynamically
                    handler = obj()
                    
                    # Register with LiteLLM
                    litellm.custom_provider_map.append({
                        "provider": provider_id,
                        "custom_handler": handler
                    })
                    
                    registered_providers.append(provider_id)
                    print(f"Registered custom LiteLLM provider: {provider_id}")
                    
        except Exception as e:
            # Skip modules that can't be inspected
            continue
    
    # Patch LiteLLM's provider enum for all registered providers
    if registered_providers:
        # Get current enum members
        members = {k: v.value for k, v in LlmProviders.__members__.items()}
        
        # Add new providers
        for provider_id in registered_providers:
            if provider_id not in members:
                members[provider_id] = provider_id
        
        # Create patched enum
        PatchedProviders = Enum("LlmProviders", members)
        
        # Patch both import locations
        import litellm.types.utils as _types
        import litellm.utils as _utils
        
        _types.LlmProviders = PatchedProviders
        _utils.LlmProviders = PatchedProviders
        
        # Refresh LiteLLM's internal caches
        litellm.utils.custom_llm_setup()
        
        # Initialize models_by_provider for new providers
        if not hasattr(litellm, 'models_by_provider'):
            litellm.models_by_provider = {}
            
        for provider_id in registered_providers:
            if provider_id not in litellm.models_by_provider:
                litellm.models_by_provider[provider_id] = []

# Import sys for module inspection
import sys

# Register all custom LiteLLM providers
try:
    register_custom_litellm_providers()
except Exception as e:
    print(f"Failed to auto-register custom LiteLLM providers: {e}")

# Export main classes
__all__ = [
    "BaseProvider", 
    "ProviderSetting", 
    "LiteLLMProviderConfig",
    "ProviderRegistry",
    "registry",
]