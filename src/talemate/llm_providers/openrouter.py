from typing import List, Dict, Any
from collections import defaultdict
from .base_provider import BaseProvider, ProviderSetting

class OpenRouterProvider(BaseProvider):
    """OpenRouter LiteLLM Provider"""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "OpenRouter"
    
    @classmethod
    def get_provider_identifier(cls) -> str:
        return "openrouter"
    
    @classmethod
    def get_old_client_type(cls) -> str:
        return "openrouter"
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="api_key",
                label="API Key",
                type="password",
                required=True,
                description="Your OpenRouter API key"
            ),
            ProviderSetting(
                key="api_base",
                label="API Base URL",
                type="text",
                required=False,
                default="https://openrouter.ai/api/v1",
                description="OpenRouter API base URL",
                advanced=True
            ),
            ProviderSetting(
                key="site_url",
                label="Site URL",
                type="text",
                required=False,
                description="Your site URL for OpenRouter referrer tracking",
                hidden=True
            ),
            ProviderSetting(
                key="app_name",
                label="App Name",
                type="text",
                required=False,
                description="Your app name for OpenRouter referrer tracking",
                hidden=True
            )
        ]
    
    def format_model_name(self, model_name: str, settings: Dict[str, Any] = None) -> str:
        """Format model name for LiteLLM - OpenRouter requires openrouter/ prefix"""
        # If the model name already has the openrouter prefix, return as-is
        if model_name.startswith("openrouter/"):
            return model_name
        # Otherwise, add the openrouter prefix
        return f"openrouter/{model_name}"
    
    def format_display_name(self, model_name: str) -> str:
        """Format model name for display - remove provider prefix for cleaner display in groups"""
        # Since we're grouping by provider, we don't need to show provider in each model name
        if '/' in model_name:
            # Extract just the model part
            _, model_part = model_name.split('/', 1)
            # Format the model part using parent's method
            return super().format_display_name(model_part)
        else:
            # Fallback to parent's formatting
            return super().format_display_name(model_name)
    
    def get_available_models(self, settings: Dict[str, Any] = None) -> List[str]:
        """Get available models for OpenRouter - fetch from API with auth"""
        try:
            import httpx
            import asyncio
            
            # Get API key from settings
            api_key = settings.get("api_key") if settings else None
            if not api_key:
                # No API key provided, return empty list
                return []
            
            # Fetch directly from OpenRouter API
            async def fetch_models():
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://openrouter.ai/api/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return [model.get("id") for model in data.get("data", []) if model.get("id")]
                    # API call failed (bad key, etc), return empty list
                    return []
            
            # Run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                models = loop.run_until_complete(fetch_models())
                return models
            finally:
                loop.close()
                
        except Exception as e:
            # Any error means we couldn't fetch models, return empty list
            return []
    
    def get_models_with_capabilities(self, settings: Dict[str, Any] = None, group_by: str = None) -> List[Dict[str, Any]]:
        """Get models with capabilities - preserve provider prefix for display"""
        models = self.get_available_models(settings)
        enhanced_models = []
        
        for model in models:
            model_name = model if isinstance(model, str) else model.get("name", "unknown")
            
            # For OpenRouter, we want to preserve the provider prefix for display
            # but still extract the clean name for the "name" field
            clean_name = model_name
            provider_prefix = None
            if '/' in clean_name:
                # Extract provider prefix and model name
                parts = clean_name.split('/', 1)
                provider_prefix = parts[0]
                clean_name = parts[1]
            
            # Format the full model name for LiteLLM API calls
            full_model_name = f"openrouter/{model_name}"
            
            enhanced_model = {
                "name": clean_name,
                "display_name": self.format_display_name(model_name),  # Pass full name with prefix
                "full_name": full_model_name,
                "capabilities": self.get_model_capabilities(full_model_name),
                "parameters": self.get_model_parameters(full_model_name),
                "_original_name": model_name,  # Preserve original name for grouping
                "_provider_prefix": provider_prefix  # Store provider prefix for grouping
            }
            enhanced_models.append(enhanced_model)
        
        # Apply grouping if requested
        if group_by:
            return self.group_models(enhanced_models, group_by)
        
        return enhanced_models
    
    def group_models(self, models: List[Dict[str, Any]], group_by: str) -> Dict[str, Any]:
        """Group OpenRouter models by provider into nested structure"""
        if group_by == "provider":
            # Group models by their provider prefix
            groups = defaultdict(list)
            
            for model in models:
                provider = model.get("_provider_prefix", "Unknown")
                # Map provider IDs to display names
                provider_map = {
                    'openai': 'OpenAI',
                    'anthropic': 'Anthropic',
                    'meta-llama': 'Meta',
                    'google': 'Google',
                    'mistralai': 'Mistral AI',
                    'cohere': 'Cohere',
                    'deepseek': 'DeepSeek',
                    'nousresearch': 'Nous Research',
                    'perplexity': 'Perplexity',
                    'qwen': 'Qwen',
                    'microsoft': 'Microsoft',
                    'x-ai': 'xAI',
                    'nvidia': 'NVIDIA',
                    'inflection': 'Inflection',
                    'sao10k': 'Sao10K',
                    'liquid': 'Liquid',
                    'cognitivecomputations': 'Cognitive Computations'
                }
                provider_display = provider_map.get(provider, provider.replace('-', ' ').title())
                
                # Remove internal fields before adding to group
                model_copy = {k: v for k, v in model.items() if not k.startswith('_')}
                groups[provider_display].append(model_copy)
            
            # Convert to nested structure with sub-groups
            sub_groups = []
            for provider_name, provider_models in sorted(groups.items()):
                # Sort models within each group
                sorted_models = sorted(provider_models, key=lambda m: m.get("display_name", m.get("name", "")).lower())
                sub_groups.append({
                    "group_name": provider_name,
                    "group_id": provider_name.lower().replace(' ', '_'),
                    "models": sorted_models,
                    "model_count": len(sorted_models)
                })
            
            # Return nested structure
            return {
                "has_subgroups": True,
                "subgroups": sub_groups
            }
        
        # For other group_by values, return indicator that this is a flat list
        return {"has_subgroups": False}
    
    def get_model_context_size(self, model_name: str) -> int | None:
        """Get context size directly from OpenRouter API"""
        try:
            import requests
            import structlog
            
            log = structlog.get_logger("talemate.llm_providers.openrouter")
            
            api_key = self._config.settings.get("api_key") if self._config else None
            if not api_key:
                log.warning("No API key available for OpenRouter context size lookup")
                return None
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            log.info(f"Fetching OpenRouter models to find context size for {model_name}")
            
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                models_data = response.json()
                models = models_data.get("data", [])
                
                # Look for our model
                log.info(f"Looking for model '{model_name}' in {len(models)} OpenRouter models")
                
                for model in models:
                    model_id = model.get("id", "")
                    if model_id == model_name:
                        context_length = model.get("context_length")
                        if context_length:
                            log.info(f"Found OpenRouter context size for {model_name}: {context_length}")
                            return int(context_length)
                        else:
                            log.warning(f"OpenRouter model {model_name} has no context_length field")
                            return None
                
                log.warning(f"Model {model_name} not found in OpenRouter models list")
                return None
            else:
                log.error(f"OpenRouter API request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            import structlog
            log = structlog.get_logger("talemate.llm_providers.openrouter")
            log.error(f"Failed to fetch OpenRouter context size: {e}")
            return None
    
