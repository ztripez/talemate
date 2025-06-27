from typing import List, Dict, Any
import httpx
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
                default="http://127.0.0.1:5001",
                description="KoboldCpp base URL (e.g., http://localhost:5001)",
            ),
        ]
    
    def format_model_name(self, model_name: str, settings: Dict[str, Any] = None) -> str:
        """Format model name for LiteLLM - KoboldCpp uses custom/koboldcpp"""
        # KoboldCpp doesn't use model-specific names with litellm
        # It always uses the generic custom/koboldcpp identifier
        return "custom/koboldcpp"
    
    def _build_litellm_params(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """Build parameters for litellm call - match the working client implementation"""
        # Get the base URL
        base_url = self.config.settings.get("api_base", "http://127.0.0.1:5001")
        
        # Construct the generation endpoint - KoboldCpp native API uses /api/extra/generate
        api_url = f"{base_url.rstrip('/')}/api/extra/generate"
        
        # Build params exactly like the working client
        params = {
            "model": "custom/koboldcpp",
            "api_base": api_url,
            **kwargs  # Pass all parameters directly
        }
        
        # Add messages if provided
        if 'messages' in kwargs:
            params['messages'] = kwargs['messages']
        
        # Add API key if configured
        api_key = self.config.settings.get("api_key")
        if api_key:
            params["api_key"] = api_key
        
        return params

    async def acompletion(self, model_name: str, messages: List[Dict[str, Any]], **kwargs):
        """Make a completion call to KoboldCpp API"""
        import httpx
        import json
        import time
        
        # Get the base URL
        base_url = self.config.settings.get("api_base", "http://127.0.0.1:5001")
        
        # Convert messages to prompt format for KoboldCpp
        prompt = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"{content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"
        
        # Add "Assistant: " to prompt the model to respond
        if messages and messages[-1].get("role") == "user":
            prompt += "Assistant: "
        
        # Build parameters for KoboldCpp unified API
        params = {
            "prompt": prompt.strip(),
        }
        
        # Map parameters to KoboldCpp API format
        if "max_tokens" in kwargs:
            params["max_length"] = kwargs["max_tokens"]
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            params["top_k"] = kwargs["top_k"]
        if "rep_pen" in kwargs:
            params["rep_pen"] = kwargs["rep_pen"]
        if "rep_pen_range" in kwargs:
            params["rep_pen_range"] = kwargs["rep_pen_range"]
        if "stop" in kwargs and kwargs["stop"]:
            params["stop_sequence"] = kwargs["stop"]
            
        # Add other KoboldCpp-specific parameters
        kobold_params = ["typical_p", "tfs_z", "top_a", "min_p", "mirostat", "mirostat_tau", 
                        "mirostat_eta", "dynatemp_range", "dynatemp_exponent", "xtc_threshold",
                        "xtc_probability", "sampler_order", "sampler_seed", "ban_eos_token",
                        "dry_multiplier", "dry_base", "dry_allowed_length", "dry_sequence_breakers",
                        "smoothing_factor", "use_default_badwordsids"]
        
        for key in kobold_params:
            if key in kwargs and kwargs[key] is not None and kwargs[key] != "":
                params[key] = kwargs[key]
        
        # Make the request
        headers = {"Content-Type": "application/json"}
        if self.config.settings.get("api_key"):
            headers["Authorization"] = f"Bearer {self.config.settings.get('api_key')}"
        
        api_url = f"{base_url.rstrip('/')}/api/v1/generate"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=params,
                headers=headers,
                timeout=300.0  # 5 minute timeout for generation
            )
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            generated_text = result.get("results", [{}])[0].get("text", "")
        
        # Build a response object that matches litellm's format
        from litellm import ModelResponse, Choices, Message
        return ModelResponse(
            id=f"koboldcpp-{int(time.time())}",
            choices=[Choices(
                finish_reason="stop",
                index=0,
                message=Message(
                    content=generated_text,
                    role="assistant"
                )
            )],
            created=int(time.time()),
            model="custom/koboldcpp",
            object="chat.completion"
        )
    
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
            
        base_url = settings.get("api_base", "http://127.0.0.1:5001")
        
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