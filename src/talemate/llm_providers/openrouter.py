from typing import List
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