from typing import List
from .base_provider import BaseProvider, ProviderSetting

class OpenAICompatibleProvider(BaseProvider):
    """Generic OpenAI-Compatible LiteLLM Provider for arbitrary endpoints"""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "OpenAI Compatible"
    
    @classmethod
    def get_provider_identifier(cls) -> str:
        return "openai_compatible"
    
    @classmethod
    def get_old_client_type(cls) -> str:
        return "openai_compat"
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="instance_name",
                label="Instance Name",
                type="text",
                required=True,
                description="Custom name for this provider instance (e.g., 'Local Ollama', 'Together AI')"
            ),
            ProviderSetting(
                key="api_base",
                label="API Base URL", 
                type="text",
                required=True,
                description="Base URL for the OpenAI-compatible API (e.g., http://localhost:1234/v1)"
            ),
            ProviderSetting(
                key="api_key",
                label="API Key",
                type="password",
                required=False,
                default="not-needed",
                description="API key (use 'not-needed' for local servers)"
            ),
            ProviderSetting(
                key="timeout",
                label="Request Timeout",
                type="number",
                required=False,
                default=60,
                description="Request timeout in seconds",
                advanced=True
            ),
            ProviderSetting(
                key="max_retries",
                label="Max Retries", 
                type="number",
                required=False,
                default=3,
                description="Maximum number of retry attempts",
                advanced=True
            )
        ]
    
    @classmethod
    def is_multi_instance(cls) -> bool:
        """Indicates this provider supports multiple instances"""
        return True