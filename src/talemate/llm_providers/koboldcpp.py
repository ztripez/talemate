from typing import List, Dict, Any
from .base_provider import BaseProvider, ProviderSetting


class KoboldCppProvider(BaseProvider):
    """KoboldCpp LiteLLM Provider - Supports native KoboldCpp API"""

    @classmethod
    def get_provider_name(cls) -> str:
        return "KoboldCpp"

    @classmethod
    def get_provider_identifier(cls) -> str:
        return "koboldcpp"  # Unique identifier for KoboldCpp
    
    @classmethod
    def is_multi_instance(cls) -> bool:
        """KoboldCpp supports multiple instances (different servers)"""
        return True
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="api_base",
                label="API Base URL",
                type="text",
                required=True,
                default="http://127.0.0.1:5001/api/extra/generate",
                description="KoboldCpp native API endpoint (e.g., http://localhost:5001/api/extra/generate)",
            ),
        ]
    
    def format_model_name(self, model_name: str, settings: Dict[str, Any] = None) -> str:
        """Format model name for LiteLLM - KoboldCpp uses custom/ prefix"""
        return f"custom/{model_name}"
    
    def _build_litellm_params(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """Build parameters for litellm call - passes all kwargs directly for native API support"""
        params = {
            "model": self.format_model_name(model_name),
            "api_base": self.config.settings.get("api_base"),
            **kwargs  # Pass all additional parameters directly
        }
        
        return params
    
    def get_model_parameters(self, model_name: str) -> List[str]:
        """Return KoboldCpp-specific parameters that can be used"""
        return [
            # Standard parameters
            "temperature",
            "max_tokens",
            "top_p",
            "stop",
            "stream",
            # KoboldCpp-specific parameters
            "rep_pen",
            "rep_pen_range",
            "typical_p",
            "tfs_z",
            "top_a",
            "top_k",
            "mirostat",
            "mirostat_tau",
            "mirostat_eta",
            "min_p",
            "xtc_threshold",
            "xtc_probability",
            "dynatemp_range",
            "dynatemp_exponent",
            "banned_tokens",
            "sampler_priority",
            "sampler_order",
            "sampler_seed",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "use_default_badwordsids",
        ]
    
    def get_available_models(self, settings: Dict[str, Any] = None) -> List[str]:
        """Get available models from KoboldCpp API"""
        import requests
        
        if not settings:
            return ["koboldcpp-model"]
            
        api_base = settings.get("api_base", "http://127.0.0.1:5001/api/extra/generate")
        # Extract base URL from the generate endpoint
        base_url = api_base.replace("/api/extra/generate", "")
        
        try:
            # KoboldCpp has /api/v1/model endpoint to get current model info
            response = requests.get(f"{base_url}/api/v1/model", timeout=5)
            if response.status_code == 200:
                model_info = response.json()
                # The result contains the model name
                model_name = model_info.get("result", "koboldcpp-model")
                return [model_name]
        except:
            pass
            
        # Fallback to generic name if API call fails
        return ["koboldcpp-model"]