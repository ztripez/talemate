import pydantic
import structlog
import os
import datetime

from talemate import VERSION
from talemate.client.model_prompts import model_prompt
from talemate.client.registry import CLIENT_CLASSES
from talemate.config import Config as AppConfigData
from talemate.config import load_config, save_config
from talemate.emit import emit
from talemate.instance import emit_clients_status, get_client
from talemate.llm_providers import registry as provider_registry
import litellm

log = structlog.get_logger("talemate.server.config")


class ConfigPayload(pydantic.BaseModel):
    config: AppConfigData


class DefaultCharacterPayload(pydantic.BaseModel):
    name: str
    gender: str
    description: str
    color: str = "#3362bb"


class SetLLMTemplatePayload(pydantic.BaseModel):
    template_file: str
    model: str


class DetermineLLMTemplatePayload(pydantic.BaseModel):
    model: str


class ToggleClientPayload(pydantic.BaseModel):
    name: str
    state: bool


class DeleteScenePayload(pydantic.BaseModel):
    path: str

class ConfigPlugin:
    router = "config"

    def __init__(self, websocket_handler):
        self.websocket_handler = websocket_handler

    async def handle(self, data: dict):
        log.info("Config action", action=data.get("action"))

        fn = getattr(self, f"handle_{data.get('action')}", None)

        if fn is None:
            return

        await fn(data)

    async def handle_save(self, data):
        app_config_data = ConfigPayload(**data)
        current_config = load_config()

        current_config.update(app_config_data.dict().get("config"))

        save_config(current_config)

        self.websocket_handler.config = current_config
        self.websocket_handler.queue_put(
            {"type": "app_config", "data": load_config(), "version": VERSION}
        )
        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "save_complete",
            }
        )

    async def handle_save_default_character(self, data):
        log.info("Saving default character", data=data["data"])

        payload = DefaultCharacterPayload(**data["data"])

        current_config = load_config()

        current_config["game"]["default_player_character"] = payload.model_dump()

        log.info(
            "Saving default character",
            character=current_config["game"]["default_player_character"],
        )

        save_config(current_config)

        self.websocket_handler.config = current_config
        self.websocket_handler.queue_put(
            {"type": "app_config", "data": load_config(), "version": VERSION}
        )
        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "save_default_character_complete",
            }
        )

    async def handle_request_std_llm_templates(self, data):
        log.info("Requesting standard LLM templates")

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "std_llm_templates",
                "data": {
                    "templates": model_prompt.std_templates,
                },
            }
        )

    async def handle_set_llm_template(self, data):
        payload = SetLLMTemplatePayload(**data["data"])

        copied_to = model_prompt.create_user_override(
            payload.template_file, payload.model
        )

        log.info(
            "Copied template",
            copied_to=copied_to,
            template=payload.template_file,
            model=payload.model,
        )

        prompt_template_example, prompt_template_file = model_prompt(
            payload.model, "sysmsg", "prompt<|BOT|>{LLM coercion}"
        )

        log.info(
            "Prompt template example",
            prompt_template_example=prompt_template_example,
            prompt_template_file=prompt_template_file,
        )

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "set_llm_template_complete",
                "data": {
                    "prompt_template_example": prompt_template_example,
                    "has_prompt_template": True if prompt_template_example else False,
                    "template_file": prompt_template_file,
                },
            }
        )

    async def handle_determine_llm_template(self, data):
        payload = DetermineLLMTemplatePayload(**data["data"])

        log.info("Determining LLM template", model=payload.model)

        template = model_prompt.query_hf_for_prompt_template_suggestion(payload.model)

        log.info("Template suggestion", template=template)

        if not template:
            emit("status", message="No template found for model", status="warning")
        else:
            await self.handle_set_llm_template(
                {
                    "data": {
                        "template_file": template,
                        "model": payload.model,
                    }
                }
            )

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "determine_llm_template_complete",
                "data": {
                    "template": template,
                },
            }
        )

    async def handle_request_client_types(self, data):
        log.info("Requesting client types")

        clients = {
            client_type: CLIENT_CLASSES[client_type].Meta().model_dump()
            for client_type in CLIENT_CLASSES
        }

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "client_types",
                "data": clients,
            }
        )

    async def handle_toggle_client(self, data):
        payload = ToggleClientPayload(**data)

        log.info("Toggling client", name=payload.name, state=payload.state)
        client = get_client(payload.name)

        client.enabled = payload.state

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "toggle_client_complete",
                "data": {
                    "name": payload.name,
                    "state": payload.state,
                },
            }
        )

        await emit_clients_status()


    async def handle_remove_scene_from_recents(self, data):
        payload = DeleteScenePayload(**data)

        log.info("Removing scene from recents", path=payload.path)

        current_config = load_config(as_model=True)

        for recent_scene in list(current_config.recent_scenes.scenes):
            if recent_scene.path == payload.path:
                current_config.recent_scenes.scenes.remove(recent_scene)

        save_config(current_config)

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "remove_scene_from_recents_complete",
                "data": {
                    "path": payload.path,
                },
            }
        )
        
        self.websocket_handler.queue_put(
            {"type": "app_config", "data": load_config(), "version": VERSION}
        )
        
    async def handle_delete_scene(self, data):
        payload = DeleteScenePayload(**data)

        log.info("Deleting scene", path=payload.path)

        # remove the file
        try:
            os.remove(payload.path)
        except FileNotFoundError:
            log.warning("File not found", path=payload.path)

        self.websocket_handler.queue_put(
            {
                "type": "config",
                "action": "delete_scene_complete",
                "data": {
                    "path": payload.path,
                },
            }
        )

        self.websocket_handler.queue_put(
            {"type": "app_config", "data": load_config(), "version": VERSION}
        )

    async def handle_request_litellm_providers(self, data):
        """Handle request for available LiteLLM providers"""
        log.info("Requesting LiteLLM providers")
        
        providers = provider_registry.get_available_providers()
        
        # Load existing saved settings from config
        current_config = load_config()  # This returns a dict by default
        saved_settings = current_config.get("litellm_providers", {})
        
        # Add saved settings to each provider - all providers are multi-instance
        for provider in providers:
            provider_id = provider["identifier"]
            provider["instances"] = []
            
            # Load all instances for this provider
            for instance_uid, settings in saved_settings.items():
                # Check if this instance belongs to this provider
                if settings.get("provider_id") == provider_id:
                    provider["instances"].append({
                        "id": instance_uid,
                        "name": settings.get("instance_name", instance_uid),
                        "settings": settings
                    })
        
        self.websocket_handler.queue_put({
            "type": "config",
            "action": "litellm_providers",
            "data": providers,
        })
    
    async def handle_save_provider_settings(self, data):
        """Save LiteLLM provider settings - all providers are treated as multi-instance"""
        provider_id = data.get("provider_id")
        instance_id = data.get("instance_id")
        settings = data.get("settings", {})
        
        log.info("Saving provider settings", provider_id=provider_id, instance_id=instance_id, settings=settings)
        
        if not provider_id:
            self.websocket_handler.queue_put({
                "type": "config", 
                "action": "provider_save_error",
                "data": {"message": "Provider ID is required"},
            })
            return
        
        try:
            # Load current config
            current_config = load_config()
            
            # Initialize litellm_providers section if it doesn't exist
            if "litellm_providers" not in current_config:
                current_config["litellm_providers"] = {}
            
            # Generate new UUID if not provided
            if not instance_id:
                import uuid
                instance_id = str(uuid.uuid4())
            
            # Add provider_id to settings
            settings["provider_id"] = provider_id
            
            # Save instance settings with the UID as key
            current_config["litellm_providers"][instance_id] = settings
            
            # Save config to file
            save_config(current_config)
            
            # Update websocket handler config
            self.websocket_handler.config = current_config
            
            # Send success response
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_save_complete", 
                "data": {
                    "provider_id": provider_id,
                    "instance_id": instance_id,
                    "message": "Provider settings saved successfully"
                },
            })
            
            # Send updated app config
            self.websocket_handler.queue_put({
                "type": "app_config", 
                "data": current_config, 
                "version": VERSION
            })
            
        except Exception as e:
            log.error("Failed to save provider settings", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_save_error",
                "data": {"message": f"Failed to save settings: {str(e)}"},
            })
    
    async def handle_save_provider_instance(self, data):
        """Save provider instance settings - delegates to handle_save_provider_settings"""
        # All providers are multi-instance, so delegate to the unified handler
        await self.handle_save_provider_settings(data)
            
    
    async def handle_delete_provider_instance(self, data):
        """Delete provider instance settings"""
        instance_id = data.get("instance_id")
        
        log.info("Deleting provider instance", instance_id=instance_id)
        
        if not instance_id:
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_instance_delete_error",
                "data": {"message": "Instance ID is required"},
            })
            return
        
        try:
            # Load current config
            current_config = load_config()
            
            # Remove instance from config
            if "litellm_providers" in current_config and instance_id in current_config["litellm_providers"]:
                del current_config["litellm_providers"][instance_id]
                
                # Save config to file
                save_config(current_config)
                
                # Update websocket handler config
                self.websocket_handler.config = current_config
                
                # Send success response
                self.websocket_handler.queue_put({
                    "type": "config",
                    "action": "provider_instance_delete_complete",
                    "data": {
                        "instance_id": instance_id,
                        "message": "Provider instance deleted successfully"
                    },
                })
                
                # Send updated app config
                self.websocket_handler.queue_put({
                    "type": "app_config",
                    "data": current_config,
                    "version": VERSION
                })
            else:
                self.websocket_handler.queue_put({
                    "type": "config",
                    "action": "provider_instance_delete_error",
                    "data": {"message": "Instance not found"},
                })
            
        except Exception as e:
            log.error("Failed to delete provider instance", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_instance_delete_error",
                "data": {"message": f"Failed to delete instance: {str(e)}"},
            })
    
    async def handle_request_model_selector(self, data):
        """Handle request for model selector with provider grouping and capabilities"""
        log.info("Requesting model selector information")
        
        try:
            # Load current config to get configured providers
            current_config = load_config()
            saved_providers = current_config.get("litellm_providers", {})
            
            model_groups = []
            
            # Process each configured provider instance
            for instance_id, settings in saved_providers.items():
                # Get the provider ID from settings
                provider_id = settings.get("provider_id")
                
                if not provider_id:
                    log.warning("Skipping instance without provider_id", instance_id=instance_id)
                    continue
                
                # Get the human-readable provider name from the registry
                provider_class = provider_registry._providers.get(provider_id)
                if provider_class:
                    provider_name = provider_class.get_provider_name()
                    # Create provider instance to get models with capabilities
                    provider_instance = provider_class()
                    models = provider_instance.get_models_with_capabilities(settings)
                else:
                    # Fallback to instance name if provider not found
                    provider_name = settings.get("instance_name", instance_id)
                    models = []
                
                if models:
                    # Sort models by display name within each provider
                    sorted_models = sorted(models, key=lambda m: m.get("display_name", m.get("name", "")).lower())
                    
                    model_groups.append({
                        "provider_id": instance_id,
                        "provider_name": provider_name,
                        "models": sorted_models
                    })
            
            # Sort provider groups by provider name
            sorted_model_groups = sorted(model_groups, key=lambda g: g.get("provider_name", "").lower())
            
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_selector_data",
                "data": {
                    "model_groups": sorted_model_groups
                },
            })
            
        except Exception as e:
            log.error("Failed to get model selector data", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_selector_error",
                "data": {"message": f"Failed to get model data: {str(e)}"},
            })
    
    async def _validate_model_parameters(self, provider_id: str, model_name: str, parameters: dict) -> dict:
        """Validate model parameters against what the provider supports"""
        try:
            # Get provider settings from config
            current_config = load_config()
            saved_providers = current_config.get("litellm_providers", {})
            provider_settings = saved_providers.get(provider_id, {})
            
            # Get provider settings to find the actual provider ID
            provider_settings = saved_providers.get(provider_id, {})
            base_provider_id = provider_settings.get("provider_id")
            
            if not base_provider_id:
                log.warning("Provider settings missing provider_id", instance_id=provider_id)
                return parameters
            
            # Get provider class from registry
            provider_class = provider_registry._providers.get(base_provider_id)
            if not provider_class:
                log.warning("Provider not found in registry", provider_id=base_provider_id)
                return parameters
            
            # Create provider instance and get supported parameters
            provider_instance = provider_class()
            formatted_model = provider_instance.format_model_name(model_name, provider_settings)
            supported_params = provider_instance.get_model_parameters(formatted_model)
            
            # Filter parameters to only include supported ones
            validated_params = {}
            invalid_params = []
            
            for key, value in parameters.items():
                if key in supported_params:
                    validated_params[key] = value
                else:
                    invalid_params.append(key)
            
            # Log validation results
            if invalid_params:
                log.warning(
                    "Removed unsupported parameters", 
                    provider=provider_id,
                    model=model_name,
                    invalid_params=invalid_params,
                    supported_params=supported_params
                )
            
            log.info(
                "Parameter validation complete",
                provider=provider_id,
                model=model_name,
                original_count=len(parameters),
                validated_count=len(validated_params)
            )
            
            return validated_params
            
        except Exception as e:
            log.error("Failed to validate model parameters", error=str(e))
            return parameters  # Graceful fallback

    async def handle_save_model_config(self, data):
        """Handle saving a model configuration"""
        log.info("Saving model configuration", data=data)
        
        try:
            # Load current config
            current_config = load_config()
            
            # Initialize model_configs section if it doesn't exist
            if "model_configs" not in current_config:
                current_config["model_configs"] = {}
            
            # Create unique config ID
            import uuid
            config_id = data.get("config_id") or str(uuid.uuid4())
            
            # Validate parameters against model's supported parameters
            parameters = data.get("parameters", {})
            
            # Extract provider instance ID and model name from nested structure
            provider_data = data.get("provider", {})
            model_data = data.get("model", {})
            
            provider_id = provider_data.get("provider_id")
            model_name = model_data.get("name")
            
            if provider_id and model_name and parameters:
                validated_parameters = await self._validate_model_parameters(
                    provider_id, model_name, parameters
                )
            else:
                validated_parameters = parameters
            
            # Save model configuration
            current_config["model_configs"][config_id] = {
                "id": config_id,
                "name": data.get("name"),
                "model": model_data,
                "provider": provider_data,
                "parameters": validated_parameters,
                "created_at": data.get("created_at") or str(datetime.datetime.now()),
                "updated_at": str(datetime.datetime.now())
            }
            
            log.info("Model config to save", config_id=config_id, configs_count=len(current_config.get("model_configs", {})))
            
            # Save config to file
            save_config(current_config)
            
            # Update websocket handler config
            self.websocket_handler.config = current_config
            
            # Send success response
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_config_save_complete",
                "data": {
                    "config_id": config_id,
                    "message": "Model configuration saved successfully"
                },
            })
            
            # Send updated app config
            self.websocket_handler.queue_put({
                "type": "app_config",
                "data": current_config,
                "version": VERSION
            })
            
        except Exception as e:
            log.error("Failed to save model configuration", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_config_save_error",
                "data": {"message": f"Failed to save configuration: {str(e)}"},
            })
    
    async def handle_delete_model_config(self, data):
        """Handle deleting a model configuration"""
        config_id = data.get("config_id")
        provider_id = data.get("provider_id")  # Optional, for better logging
        log.info("Deleting model configuration", config_id=config_id, provider_id=provider_id)
        
        if not config_id:
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_config_delete_error",
                "data": {"message": "Configuration ID is required"},
            })
            return
        
        try:
            # Load current config
            current_config = load_config()
            
            # Check if config exists
            if "model_configs" not in current_config or config_id not in current_config["model_configs"]:
                self.websocket_handler.queue_put({
                    "type": "config",
                    "action": "model_config_delete_error",
                    "data": {"message": "Configuration not found"},
                })
                return
            
            # Log configuration details before deletion
            config_to_delete = current_config["model_configs"][config_id]
            log.info(
                "Deleting model configuration details",
                config_id=config_id,
                name=config_to_delete.get("name"),
                provider=config_to_delete.get("provider", {}).get("provider_id"),
                model=config_to_delete.get("model", {}).get("name")
            )
            
            # Delete configuration
            del current_config["model_configs"][config_id]
            
            # Save config to file
            save_config(current_config)
            
            # Update websocket handler config
            self.websocket_handler.config = current_config
            
            # Send success response
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_config_delete_complete",
                "data": {
                    "config_id": config_id,
                    "message": "Model configuration deleted successfully"
                },
            })
            
            # Send updated app config
            self.websocket_handler.queue_put({
                "type": "app_config",
                "data": current_config,
                "version": VERSION
            })
            
        except Exception as e:
            log.error("Failed to delete model configuration", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_config_delete_error",
                "data": {"message": f"Failed to delete configuration: {str(e)}"},
            })
    
    async def handle_request_model_configs(self, data):
        """Handle request for saved model configurations"""
        log.info("Requesting model configurations")
        
        try:
            # Load current config
            current_config = load_config()
            model_configs = current_config.get("model_configs", {})
            
            # Convert to list format
            configs_list = list(model_configs.values())
            
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_configs_data",
                "data": {
                    "configs": configs_list
                },
            })
            
        except Exception as e:
            log.error("Failed to get model configurations", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "model_configs_error",
                "data": {"message": f"Failed to get configurations: {str(e)}"},
            })