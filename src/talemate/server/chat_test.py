import pydantic
import structlog
from typing import List, Dict, Any
from talemate.config import load_config
from talemate.llm_providers import registry as provider_registry
import litellm

log = structlog.get_logger("talemate.server.chat_test")


class ChatTestPayload(pydantic.BaseModel):
    config_id: str
    messages: List[Dict[str, str]]


class ChatTestPlugin:
    router = "chat_test"

    def __init__(self, websocket_handler):
        self.websocket_handler = websocket_handler

    async def handle(self, data: dict):
        log.info("Chat test action", action=data.get("action"))

        fn = getattr(self, f"handle_{data.get('action')}", None)

        if fn is None:
            return

        await fn(data)

    async def handle_generate(self, data):
        """Handle chat generation request"""
        try:
            payload = ChatTestPayload(**data)
            
            # Load config to get the model configuration
            config = load_config()
            model_configs = config.get("model_configs", {})
            
            model_config = model_configs.get(payload.config_id)
            if not model_config:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": "Model configuration not found"
                })
                return
            
            # Get provider settings
            provider_id = model_config["provider"]["provider_id"]
            provider_settings = config.get("litellm_providers", {}).get(provider_id, {})
            
            if not provider_settings:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider {provider_id} not configured"
                })
                return
            
            # Extract base provider ID for multi-instance providers
            if "_" in provider_id:
                base_provider_id = provider_id.split("_")[0]
            else:
                base_provider_id = provider_id
            
            # Get provider class
            provider_class = provider_registry._providers.get(base_provider_id)
            if not provider_class:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider {base_provider_id} not found"
                })
                return
            
            # Create provider instance
            provider = provider_class()
            from talemate.llm_providers.base_provider import LiteLLMProviderConfig
            provider_config = LiteLLMProviderConfig(
                provider_identifier=base_provider_id,
                settings=provider_settings
            )
            provider.set_config(provider_config)
            
            # Build completion parameters
            model_name = model_config["model"]["name"]
            parameters = model_config.get("parameters", {})
            
            # Pass all parameters - let the provider handle filtering
            clean_params = parameters
            
            # Send debug info about the request
            self.websocket_handler.queue_put({
                "type": "chat_test",
                "action": "debug_info",
                "debug": {
                    "provider": {
                        "id": provider_id,
                        "base_id": base_provider_id,
                        "settings": provider_settings
                    },
                    "model": {
                        "name": model_name,
                        "full_name": model_config["model"].get("full_name", model_name),
                        "display_name": model_config["model"].get("display_name", model_name)
                    },
                    "parameters_sent": clean_params,
                    "formatted_model": provider.format_model_name(model_name)
                }
            })
            
            # Make the completion call
            log.info("Making completion call", model=model_name, provider=base_provider_id)
            
            response = await provider.acompletion(
                model_name=model_name,
                messages=payload.messages,
                **clean_params
            )
            
            # Extract response content and metadata
            content = response.choices[0].message.content
            
            # Build response debug info
            response_debug = {
                "model": response.model if hasattr(response, 'model') else None,
                "usage": response.usage.dict() if hasattr(response, 'usage') and response.usage else None,
                "finish_reason": response.choices[0].finish_reason if response.choices else None,
                "response_metadata": {}
            }
            
            # Add any additional metadata
            if hasattr(response, '_response_ms'):
                response_debug["response_metadata"]["response_time_ms"] = response._response_ms
            
            # Send response back with debug info
            self.websocket_handler.queue_put({
                "type": "chat_test",
                "action": "response",
                "content": content,
                "debug": response_debug
            })
            
        except Exception as e:
            log.error("Chat generation failed", error=str(e))
            self.websocket_handler.queue_put({
                "type": "chat_test",
                "action": "error",
                "message": f"Generation failed: {str(e)}"
            })