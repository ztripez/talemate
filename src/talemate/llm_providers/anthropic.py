from typing import List
from .base_provider import BaseProvider, ProviderSetting

class AnthropicProvider(BaseProvider):
    """Anthropic LiteLLM Provider"""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "Anthropic"
    
    @classmethod
    def get_provider_identifier(cls) -> str:
        return "anthropic"
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="api_key",
                label="API Key",
                type="password",
                required=True,
                description="Your Anthropic API key"
            ),
            ProviderSetting(
                key="api_base",
                label="API Base URL",
                type="text",
                required=False,
                default="https://api.anthropic.com",
                description="Anthropic API base URL",
                advanced=True
            ),
            ProviderSetting(
                key="max_tokens",
                label="Max Tokens",
                type="number",
                required=False,
                default=4096,
                description="Maximum tokens for responses",
                advanced=True
            )
        ]