import pydantic
import structlog
import os

from talemate import VERSION
from talemate.client.model_prompts import model_prompt
from talemate.client.registry import CLIENT_CLASSES
from talemate.config import Config as AppConfigData
from talemate.config import load_config, save_config
from talemate.emit import emit
from talemate.instance import emit_clients_status, get_client
from talemate.llm_providers import registry as provider_registry

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
        
        # Add saved settings to each provider
        for provider in providers:
            provider_id = provider["identifier"]
            if provider["multi_instance"]:
                # For multi-instance providers, load all instances
                provider["instances"] = []
                for key, settings in saved_settings.items():
                    if key.startswith(f"{provider_id}_"):
                        instance_id = key
                        provider["instances"].append({
                            "id": instance_id,
                            "name": settings.get("instance_name", instance_id),
                            "settings": settings
                        })
            else:
                # For single-instance providers, load direct settings
                if provider_id in saved_settings:
                    provider["saved_settings"] = saved_settings[provider_id]
                else:
                    provider["saved_settings"] = {}
        
        self.websocket_handler.queue_put({
            "type": "config",
            "action": "litellm_providers",
            "data": providers,
        })
    
    async def handle_save_provider_settings(self, data):
        """Save LiteLLM provider settings"""
        provider_id = data.get("provider_id")
        settings = data.get("settings", {})
        
        log.info("Saving provider settings", provider_id=provider_id, settings=settings)
        
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
            
            # Save provider settings
            current_config["litellm_providers"][provider_id] = settings
            
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
        """Save multi-instance provider settings"""
        provider_id = data.get("provider_id")
        instance_id = data.get("instance_id")
        settings = data.get("settings", {})
        
        log.info("Saving provider instance", provider_id=provider_id, instance_id=instance_id, settings=settings)
        
        if not provider_id or not instance_id:
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_instance_save_error",
                "data": {"message": "Provider ID and Instance ID are required"},
            })
            return
        
        try:
            # Load current config
            current_config = load_config()
            
            # Initialize litellm_providers section if it doesn't exist
            if "litellm_providers" not in current_config:
                current_config["litellm_providers"] = {}
            
            # Save instance settings with the instance ID as key
            current_config["litellm_providers"][instance_id] = settings
            
            # Save config to file
            save_config(current_config)
            
            # Update websocket handler config
            self.websocket_handler.config = current_config
            
            # Send success response
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_instance_save_complete",
                "data": {
                    "provider_id": provider_id,
                    "instance_id": instance_id,
                    "message": "Provider instance saved successfully"
                },
            })
            
            # Send updated app config
            self.websocket_handler.queue_put({
                "type": "app_config",
                "data": current_config,
                "version": VERSION
            })
            
        except Exception as e:
            log.error("Failed to save provider instance", error=str(e))
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_instance_save_error",
                "data": {"message": f"Failed to save instance: {str(e)}"},
            })
    
    async def handle_delete_provider_instance(self, data):
        """Delete multi-instance provider settings"""
        provider_id = data.get("provider_id")
        instance_id = data.get("instance_id")
        
        log.info("Deleting provider instance", provider_id=provider_id, instance_id=instance_id)
        
        if not provider_id or not instance_id:
            self.websocket_handler.queue_put({
                "type": "config",
                "action": "provider_instance_delete_error",
                "data": {"message": "Provider ID and Instance ID are required"},
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
                        "provider_id": provider_id,
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