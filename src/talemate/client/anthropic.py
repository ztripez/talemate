import pydantic
import structlog
import litellm
from litellm import acompletion, ModelResponse
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    APIError
)

from talemate.client.base import ClientBase, ErrorAction, CommonDefaults, ExtraField
from talemate.client.registry import register
from talemate.client.remote import (
    EndpointOverride,
    EndpointOverrideMixin,
    endpoint_override_extra_fields,
)
from talemate.config import Client as BaseClientConfig
from talemate.config import load_config
from talemate.emit import emit
from talemate.emit.signals import handlers

__all__ = [
    "AnthropicClient",
]
log = structlog.get_logger("talemate")

# Edit this to add new models / remove old models
SUPPORTED_MODELS = [
    "claude-3-haiku-20240307",
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-7-sonnet-latest",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
]


class Defaults(EndpointOverride, CommonDefaults, pydantic.BaseModel):
    max_token_length: int = 16384
    model: str = "claude-3-5-sonnet-latest"
    double_coercion: str = None

class ClientConfig(EndpointOverride, BaseClientConfig):
    pass


@register()
class AnthropicClient(EndpointOverrideMixin, ClientBase):
    """
    Anthropic client for generating text.
    """

    client_type = "anthropic"
    conversation_retries = 0
    auto_break_repetition_enabled = False
    # TODO: make this configurable?
    decensor_enabled = False
    config_cls = ClientConfig

    class Meta(ClientBase.Meta):
        name_prefix: str = "Anthropic"
        title: str = "Anthropic"
        manual_model: bool = True
        manual_model_choices: list[str] = SUPPORTED_MODELS
        requires_prompt_template: bool = False
        defaults: Defaults = Defaults()
        extra_fields: dict[str, ExtraField] = endpoint_override_extra_fields()

    def __init__(self, model="claude-3-5-sonnet-latest", **kwargs):
        self.model_name = model
        self.api_key_status = None
        self._reconfigure_endpoint_override(**kwargs)
        self.config = load_config()
        super().__init__(**kwargs)

        handlers["config_saved"].connect(self.on_config_saved)

    @property
    def can_be_coerced(self) -> bool:
        return True

    @property
    def anthropic_api_key(self):
        return self.config.get("anthropic", {}).get("api_key")

    @property
    def supported_parameters(self):
        return [
            "temperature",
            "top_p",
            "top_k",
            "max_tokens",
        ]

    def emit_status(self, processing: bool = None):
        error_action = None
        if processing is not None:
            self.processing = processing

        if self.anthropic_api_key:
            status = "busy" if self.processing else "idle"
            model_name = self.model_name
        else:
            status = "error"
            model_name = "No API key set"
            error_action = ErrorAction(
                title="Set API Key",
                action_name="openAppConfig",
                icon="mdi-key-variant",
                arguments=[
                    "application",
                    "anthropic_api",
                ],
            )

        if not self.model_name:
            status = "error"
            model_name = "No model loaded"

        self.current_status = status

        data={
            "error_action": error_action.model_dump() if error_action else None,
            "double_coercion": self.double_coercion,
            "meta": self.Meta().model_dump(),
            "enabled": self.enabled,
        }
        data.update(self._common_status_data()) 
        emit(
            "client_status",
            message=self.client_type,
            id=self.name,
            details=model_name,
            status=status if self.enabled else "disabled",
            data=data,
        )

    def set_client(self, max_token_length: int = None):
        if not self.anthropic_api_key and not self.endpoint_override_base_url_configured:
            log.error("No anthropic API key set")
            if self.api_key_status:
                self.api_key_status = False
                emit("request_client_status")
                emit("request_agent_status")
            return

        if not self.model_name:
            self.model_name = "claude-3-opus-20240229"

        if max_token_length and not isinstance(max_token_length, int):
            max_token_length = int(max_token_length)

        model = self.model_name

        # Configure LiteLLM for Anthropic
        if self.api_key:
            litellm.api_key = self.api_key
        if self.base_url:
            litellm.api_base = self.base_url

        self.max_token_length = max_token_length or 16384

        if not self.api_key_status:
            if self.api_key_status is False:
                emit("request_client_status")
                emit("request_agent_status")
            self.api_key_status = True

        log.info(
            "anthropic set client",
            max_token_length=self.max_token_length,
            provided_max_token_length=max_token_length,
            model=model,
        )

    def reconfigure(self, **kwargs):
        if kwargs.get("model"):
            self.model_name = kwargs["model"]
            self.set_client(kwargs.get("max_token_length"))

        if "enabled" in kwargs:
            self.enabled = bool(kwargs["enabled"])
            
        if "double_coercion" in kwargs:
            self.double_coercion = kwargs["double_coercion"]
            
        self._reconfigure_common_parameters(**kwargs)
        self._reconfigure_endpoint_override(**kwargs)

    def on_config_saved(self, event):
        config = event.data
        self.config = config
        self.set_client(max_token_length=self.max_token_length)

    def response_tokens(self, response: str):
        return response.usage.output_tokens

    def prompt_tokens(self, response: str):
        return response.usage.input_tokens

    async def status(self):
        self.emit_status()

    def prompt_template(self, system_message: str, prompt: str):
        """
        Anthropic handles the prompt template internally, so we just
        give the prompt as is.
        """
        return prompt

    async def generate(self, prompt: str, parameters: dict, kind: str):
        """
        Generates text from the given prompt and parameters using LiteLLM.
        """

        if not self.anthropic_api_key and not self.endpoint_override_base_url_configured:
            raise Exception("No anthropic API key set")
        
        prompt, coercion_prompt = self.split_prompt_for_coercion(prompt)
        
        system_message = self.get_system_message(kind)
        
        messages = [
            {"role": "user", "content": prompt.strip()}
        ]
        
        if coercion_prompt:
            messages.append({"role": "assistant", "content": coercion_prompt.strip()})

        self.log.debug(
            "generate",
            prompt=prompt[:128] + " ...",
            parameters=parameters,
            system_message=system_message,
        )

        try:
            # Prepare LiteLLM parameters
            litellm_params = {
                "model": f"anthropic/{self.model_name}",
                "messages": messages,
                "system": system_message,
                "stream": True,
                **parameters,
            }

            # Set API key and base URL if needed
            if self.api_key:
                litellm_params["api_key"] = self.api_key
            if self.base_url:
                litellm_params["api_base"] = self.base_url

            stream = await acompletion(**litellm_params)
            
            response = ""
            
            # Iterate over streamed chunks
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and getattr(delta, "content", None):
                    content_piece = delta.content
                    response += content_piece
                    # Incrementally track token usage
                    self.update_request_tokens(self.count_tokens(content_piece))
            
            # Extract token usage if available
            if hasattr(stream, 'usage') and stream.usage:
                self._returned_prompt_tokens = getattr(stream.usage, 'prompt_tokens', None)
                self._returned_response_tokens = getattr(stream.usage, 'completion_tokens', None)

            log.debug("generated response", response=response)

            return response
        except AuthenticationError as e:
            self.log.error("generate error - authentication", e=e)
            emit("status", message="Anthropic API: Authentication Failed", status="error")
            return ""
        except RateLimitError as e:
            self.log.error("generate error - rate limit", e=e)
            emit("status", message="Anthropic API: Rate Limit Exceeded", status="error")
            return ""
        except BadRequestError as e:
            self.log.error("generate error - bad request", e=e)
            emit("status", message="Anthropic API: Bad Request", status="error")
            return ""
        except ServiceUnavailableError as e:
            self.log.error("generate error - service unavailable", e=e)
            emit("status", message="Anthropic API: Service Unavailable", status="error")
            return ""
        except Timeout as e:
            self.log.error("generate error - timeout", e=e)
            emit("status", message="Anthropic API: Request Timeout", status="error")
            return ""
        except Exception as e:
            self.log.error("generate error", e=e)
            emit("status", message="Error during generation (check logs)", status="error")
            return ""
