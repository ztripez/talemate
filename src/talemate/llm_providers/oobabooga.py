from typing import List, Dict, Any
import httpx
from .base_provider import BaseProvider, ProviderSetting


class OobaboogaProvider(BaseProvider):
    """Oobabooga Text Generation WebUI LiteLLM Provider"""

    @classmethod
    def get_provider_name(cls) -> str:
        return "Oobabooga"

    @classmethod
    def get_provider_identifier(cls) -> str:
        return "oobabooga"
    
    @classmethod
    def get_old_client_type(cls) -> str:
        return "textgenwebui"
    
    @classmethod
    def is_multi_instance(cls) -> bool:
        """Oobabooga supports multiple instances (different servers)"""
        return True
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="api_base",
                label="API Base URL",
                type="text",
                required=True,
                default="http://127.0.0.1:5000",
                description="Oobabooga base URL (e.g., http://localhost:5000)",
            ),
            ProviderSetting(
                key="api_key",
                label="API Key",
                type="password",
                required=False,
                default="",
                description="API key if authentication is enabled",
            ),
        ]
    
    def format_model_name(self, model_name: str, settings: Dict[str, Any] = None) -> str:
        """Format model name for LiteLLM - Oobabooga uses OpenAI format"""
        return f"openai/{model_name}"
    
    def _build_litellm_params(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """Build parameters for litellm call"""
        # Get the base URL
        base_url = self.config.settings.get("api_base", "http://127.0.0.1:5000")
        
        # Build params for OpenAI-compatible endpoint
        params = {
            "model": self.format_model_name(model_name),
            "api_base": f"{base_url.rstrip('/')}/v1",
            **kwargs  # Pass all parameters directly - they'll be forwarded
        }
        
        # Add messages if provided
        if 'messages' in kwargs:
            params['messages'] = kwargs['messages']
        
        # Add API key if configured, otherwise use dummy key
        api_key = self.config.settings.get("api_key")
        if api_key:
            params["api_key"] = api_key
        else:
            params["api_key"] = "sk-1111"  # Oobabooga requires a key even if not used
        
        return params
    
    def get_model_parameters(self, model_name: str) -> List[str]:
        """Return Oobabooga-specific parameters that can be used"""
        return [
            # Standard OpenAI parameters
            "temperature",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "stream",
            "seed",
            # Oobabooga-specific parameters (will be passed through)
            "top_k",
            "min_p",
            "repetition_penalty",
            "repetition_penalty_range",
            "do_sample",
            "skip_special_tokens",
            "xtc_threshold",
            "xtc_probability",
            "dry_multiplier",
            "dry_base",
            "dry_allowed_length",
            "dry_sequence_breakers",
            "smoothing_factor",
            "smoothing_curve",
            "typical_p",
            "tfs_z",
            "top_a",
            "mirostat",
            "mirostat_tau",
            "mirostat_eta",
            "dynatemp_range",
            "dynatemp_exponent",
            "ban_eos_token",
            "add_bos_token",
            "truncation_length",
            "custom_stopping_strings",
            "stopping_strings",
            "guidance_scale",
            "negative_prompt",
            "penalty_alpha",
            "epsilon_cutoff",
            "eta_cutoff",
            "encoder_repetition_penalty",
            "no_repeat_ngram_size",
        ]
    
    async def get_available_models(self, settings: Dict[str, Any] = None) -> List[str]:
        """Get available models from Oobabooga API"""
        import httpx
        
        if not settings:
            return ["oobabooga-model"]
            
        base_url = settings.get("api_base", "http://127.0.0.1:5000")
        api_key = settings.get("api_key", "")
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            # Oobabooga has /v1/internal/model/info endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url.rstrip('/')}/v1/internal/model/info",
                    headers=headers,
                    timeout=5.0
                )
                if response.status_code == 200:
                    model_info = response.json()
                    model_name = model_info.get("model_name", "oobabooga-model")
                    if model_name == "None":
                        model_name = "oobabooga-model"
                    return [model_name]
        except:
            pass
            
        # Fallback to generic name if API call fails
        return ["oobabooga-model"]