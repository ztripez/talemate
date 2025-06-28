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
    parameters: Dict[str, Any] = pydantic.Field(default_factory=dict)


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

    async def handle_get_model_parameters(self, data):
        """Handle request for model's supported parameters"""
        log.info("Getting model parameters", data=data)
        try:
            provider_id = data.get("provider_id")
            model_name = data.get("model_name")
            
            log.info("Received parameter request", provider_id=provider_id, model_name=model_name)
            
            if not provider_id or not model_name:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": "Provider ID and model name are required"
                })
                return
            
            # Load config to get provider settings
            config = load_config()
            provider_settings = config.get("litellm_providers", {}).get(provider_id, {})
            
            log.info("Provider settings", provider_id=provider_id, settings=provider_settings)
            
            if not provider_settings:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider {provider_id} not found"
                })
                return
            
            # Get the actual provider ID from settings
            base_provider_id = provider_settings.get("provider_id")
            if not base_provider_id:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider settings missing provider_id"
                })
                return
            
            log.info("Base provider ID", base_provider_id=base_provider_id)
            
            # Get provider class
            provider_class = provider_registry._providers.get(base_provider_id)
            if not provider_class:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider {base_provider_id} not found in registry"
                })
                return
            
            # Create provider instance and get model parameters
            provider = provider_class()
            formatted_model = provider.format_model_name(model_name, provider_settings)
            parameters = provider.get_model_parameters(formatted_model)
            
            log.info("Fetched model parameters", 
                     provider=base_provider_id, 
                     model=model_name,
                     formatted_model=formatted_model,
                     parameters_count=len(parameters),
                     parameters=parameters[:5])  # Log first 5 parameters
            
            # Send response
            self.websocket_handler.queue_put({
                "type": "chat_test",
                "action": "model_parameters",
                "parameters": parameters
            })
            
        except Exception as e:
            log.error("Failed to get model parameters", error=str(e), traceback=True)
            self.websocket_handler.queue_put({
                "type": "chat_test",
                "action": "error",
                "message": f"Failed to get model parameters: {str(e)}"
            })
    
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
            
            # Get provider instance ID and settings
            instance_id = model_config["provider"]["provider_id"]
            provider_settings = config.get("litellm_providers", {}).get(instance_id, {})
            
            if not provider_settings:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider {instance_id} not found"
                })
                return
            
            # Get the actual provider ID from settings
            base_provider_id = provider_settings.get("provider_id")
            if not base_provider_id:
                self.websocket_handler.queue_put({
                    "type": "chat_test",
                    "action": "error",
                    "message": f"Provider settings missing provider_id for instance {instance_id}"
                })
                return
            
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
            # Use test parameters from request if provided, otherwise fall back to saved parameters
            parameters = payload.parameters if payload.parameters else model_config.get("parameters", {})
            
            # Pass all parameters - let the provider handle filtering
            clean_params = parameters
            
            # Send debug info about the request
            self.websocket_handler.queue_put({
                "type": "chat_test",
                "action": "debug_info",
                "debug": {
                    "provider": {
                        "id": instance_id,
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
            log.info("Making completion call", model=model_name, provider=base_provider_id, streaming=clean_params.get("stream", False))
            
            # Check if streaming is requested
            if clean_params.get("stream", False):
                # Handle streaming response
                full_content = ""
                response_metadata = {}
                
                try:
                    # Call provider with streaming
                    response = await provider.acompletion(
                        model_name=model_name,
                        messages=payload.messages,
                        **clean_params
                    )
                    
                    # Check if we got a streaming response or a regular response
                    if hasattr(response, '__aiter__'):
                        # It's a streaming response
                        async for chunk in response:
                            # Extract chunk content
                            if hasattr(chunk, 'choices') and chunk.choices:
                                delta = chunk.choices[0].delta
                                if hasattr(delta, 'content') and delta.content:
                                    chunk_content = delta.content
                                    full_content += chunk_content
                                    
                                    # Send streaming chunk to frontend
                                    self.websocket_handler.queue_put({
                                        "type": "chat_test",
                                        "action": "stream_chunk",
                                        "content": chunk_content
                                    })
                            
                            # Store metadata from last chunk
                            if hasattr(chunk, 'model'):
                                response_metadata['model'] = chunk.model
                            if hasattr(chunk, 'usage'):
                                response_metadata['usage'] = chunk.usage.dict() if chunk.usage else None
                        
                        # Send stream end signal
                        self.websocket_handler.queue_put({
                            "type": "chat_test",
                            "action": "stream_end",
                            "debug": {
                                "model": response_metadata.get('model'),
                                "usage": response_metadata.get('usage'),
                                "full_content": full_content,
                                "finish_reason": "stop"
                            }
                        })
                    else:
                        # Got a non-streaming response (fallback from provider)
                        content = response.choices[0].message.content
                        self.websocket_handler.queue_put({
                            "type": "chat_test",
                            "action": "response",
                            "content": content,
                            "debug": {
                                "model": response.model if hasattr(response, 'model') else None,
                                "usage": response.usage.dict() if hasattr(response, 'usage') and response.usage else None,
                                "note": "Streaming not supported, used non-streaming response"
                            }
                        })
                    
                except Exception as e:
                    log.error("Streaming failed", error=str(e))
                    # Fall back to non-streaming
                    response = await provider.acompletion(
                        model_name=model_name,
                        messages=payload.messages,
                        **{k: v for k, v in clean_params.items() if k != 'stream'}
                    )
                    content = response.choices[0].message.content
                    self.websocket_handler.queue_put({
                        "type": "chat_test",
                        "action": "response",
                        "content": content,
                        "debug": {
                            "model": response.model if hasattr(response, 'model') else None,
                            "usage": response.usage.dict() if hasattr(response, 'usage') and response.usage else None,
                            "note": "Fell back to non-streaming due to error"
                        }
                    })
            else:
                # Non-streaming response
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