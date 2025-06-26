from typing import List, Dict, Any
from .base_provider import BaseProvider, ProviderSetting

class OpenAIProvider(BaseProvider):
    """OpenAI LiteLLM Provider"""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "OpenAI"
    
    @classmethod
    def get_provider_identifier(cls) -> str:
        return "openai"
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="api_key",
                label="API Key",
                type="password",
                required=True,
                description="Your OpenAI API key"
            ),
            ProviderSetting(
                key="api_base",
                label="API Base URL",
                type="text",
                required=False,
                default="https://api.openai.com/v1",
                description="OpenAI API base URL",
                advanced=True
            ),
            ProviderSetting(
                key="organization",
                label="Organization ID",
                type="text",
                required=False,
                description="Your OpenAI organization ID",
                advanced=True
            ),
            ProviderSetting(
                key="api_version",
                label="API Version",
                type="text",
                required=False,
                description="API version to use",
                advanced=True
            )
        ]
    
    def format_model_name(self, model_name: str, settings: Dict[str, Any] = None) -> str:
        """OpenAI models don't need prefix"""
        return model_name