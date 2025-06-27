
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

# Export main classes
__all__ = [
    "BaseProvider", 
    "ProviderSetting", 
    "LiteLLMProviderConfig",
    "ProviderRegistry",
    "registry",
]