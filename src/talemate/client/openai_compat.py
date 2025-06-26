import random
import urllib

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

from talemate.client.base import ClientBase, ExtraField
from talemate.client.registry import register
from talemate.config import Client as BaseClientConfig
from talemate.emit import emit

log = structlog.get_logger("talemate.client.openai_compat")

EXPERIMENTAL_DESCRIPTION = """Use this client if you want to connect to a service implementing an OpenAI-compatible API. Success is going to depend on the level of compatibility. Use the actual OpenAI client if you want to connect to OpenAI's API."""


class Defaults(pydantic.BaseModel):
    api_url: str = "http://localhost:5000"
    api_key: str = ""
    max_token_length: int = 8192
    model: str = ""
    api_handles_prompt_template: bool = False
    double_coercion: str = None
    rate_limit: int | None = None


class ClientConfig(BaseClientConfig):
    api_handles_prompt_template: bool = False


@register()
class OpenAICompatibleClient(ClientBase):
    client_type = "openai_compat"
    conversation_retries = 0
    config_cls = ClientConfig

    class Meta(ClientBase.Meta):
        title: str = "OpenAI Compatible API"
        name_prefix: str = "OpenAI Compatible API"
        experimental: str = EXPERIMENTAL_DESCRIPTION
        enable_api_auth: bool = True
        manual_model: bool = True
        defaults: Defaults = Defaults()
        extra_fields: dict[str, ExtraField] = {
            "api_handles_prompt_template": ExtraField(
                name="api_handles_prompt_template",
                type="bool",
                label="API handles prompt template (chat/completions)",
                required=False,
                description="The API handles the prompt template, meaning your choice in the UI for the prompt template below will be ignored. This is not recommended and should only be used if the API does not support the `completions` andpoint or you don't know which prompt template to use.",
            )
        }

    def __init__(
        self, model=None, api_key=None, api_handles_prompt_template=False, **kwargs
    ):
        self.model_name = model
        self.api_key = api_key
        self.api_handles_prompt_template = api_handles_prompt_template
        super().__init__(**kwargs)

    @property
    def experimental(self):
        return EXPERIMENTAL_DESCRIPTION

    @property
    def can_be_coerced(self):
        """
        Determines whether or not his client can pass LLM coercion. (e.g., is able
        to predefine partial LLM output in the prompt)
        """
        return not self.api_handles_prompt_template

    @property
    def supported_parameters(self):
        return [
            "temperature",
            "top_p",
            "presence_penalty",
            "max_tokens",
        ]

    def set_client(self, **kwargs):
        self.api_key = kwargs.get("api_key", self.api_key)
        self.api_handles_prompt_template = kwargs.get(
            "api_handles_prompt_template", self.api_handles_prompt_template
        )
        
        # Configure LiteLLM for OpenAI Compatible API
        litellm.api_base = self.api_url
        if self.api_key:
            litellm.api_key = self.api_key
        
        self.model_name = (
            kwargs.get("model") or kwargs.get("model_name") or self.model_name
        )

    def prompt_template(self, system_message: str, prompt: str):

        log.debug(
            "IS API HANDLING PROMPT TEMPLATE",
            api_handles_prompt_template=self.api_handles_prompt_template,
        )

        if not self.api_handles_prompt_template:
            return super().prompt_template(system_message, prompt)

        if "<|BOT|>" in prompt:
            _, right = prompt.split("<|BOT|>", 1)
            if right:
                prompt = prompt.replace("<|BOT|>", "\nStart your response with: ")
            else:
                prompt = prompt.replace("<|BOT|>", "")

        return prompt

    async def get_model_name(self):
        return self.model_name

    async def generate(self, prompt: str, parameters: dict, kind: str):
        """
        Generates text from the given prompt and parameters using LiteLLM.
        """

        try:
            if self.api_handles_prompt_template:
                # OpenAI API handles prompt template
                # Use the chat completions endpoint
                self.log.debug(
                    "generate (chat/completions)",
                    prompt=prompt[:128] + " ...",
                    parameters=parameters,
                )
                
                messages = [{"role": "user", "content": prompt.strip()}]
                
                # Prepare LiteLLM parameters for chat
                litellm_params = {
                    "model": f"openai/{self.model_name}",  # Use OpenAI-compatible format
                    "messages": messages,
                    "stream": True,
                    **parameters,
                }
                
                # Set API base and key
                litellm_params["api_base"] = self.api_url
                if self.api_key:
                    litellm_params["api_key"] = self.api_key

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
                        # Track token usage incrementally
                        self.update_request_tokens(self.count_tokens(content_piece))

                # Extract token usage if available
                if hasattr(stream, 'usage') and stream.usage:
                    self._returned_prompt_tokens = getattr(stream.usage, 'prompt_tokens', None)
                    self._returned_response_tokens = getattr(stream.usage, 'completion_tokens', None)

                return self.process_response_for_indirect_coercion(prompt, response)
            else:
                # Talemate handles prompt template
                # Convert to chat format for LiteLLM compatibility
                self.log.debug(
                    "generate (completions)",
                    prompt=prompt[:128] + " ...",
                    parameters=parameters,
                )
                
                messages = [{"role": "user", "content": prompt.strip()}]
                
                # Prepare LiteLLM parameters
                litellm_params = {
                    "model": f"openai/{self.model_name}",  # Use OpenAI-compatible format
                    "messages": messages,
                    "stream": True,
                    **parameters,
                }
                
                # Set API base and key
                litellm_params["api_base"] = self.api_url
                if self.api_key:
                    litellm_params["api_key"] = self.api_key

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
                        # Track token usage incrementally
                        self.update_request_tokens(self.count_tokens(content_piece))

                # Extract token usage if available
                if hasattr(stream, 'usage') and stream.usage:
                    self._returned_prompt_tokens = getattr(stream.usage, 'prompt_tokens', None)
                    self._returned_response_tokens = getattr(stream.usage, 'completion_tokens', None)

                return response
        except AuthenticationError as e:
            self.log.error("generate error - authentication", e=e)
            emit("status", message="OpenAI Compatible API: Authentication Failed", status="error")
            return ""
        except BadRequestError as e:
            self.log.error("generate error - bad request", e=e)
            emit("status", message="OpenAI Compatible API: Bad Request", status="error")
            return ""
        except ServiceUnavailableError as e:
            self.log.error("generate error - service unavailable", e=e)
            emit("status", message="OpenAI Compatible API: Service Unavailable", status="error")
            return ""
        except Timeout as e:
            self.log.error("generate error - timeout", e=e)
            emit("status", message="OpenAI Compatible API: Request Timeout", status="error")
            return ""
        except Exception as e:
            self.log.error("generate error", e=e)
            emit(
                "status", message="Error during generation (check logs)", status="error"
            )
            return ""

    def reconfigure(self, **kwargs):
        if kwargs.get("model"):
            self.model_name = kwargs["model"]
        if "api_url" in kwargs:
            self.api_url = kwargs["api_url"]
        if "max_token_length" in kwargs:
            self.max_token_length = (
                int(kwargs["max_token_length"]) if kwargs["max_token_length"] else 8192
            )
        if "api_key" in kwargs:
            self.api_key = kwargs["api_key"]
        if "api_handles_prompt_template" in kwargs:
            self.api_handles_prompt_template = kwargs["api_handles_prompt_template"]
        # TODO: why isn't this calling super()?
        if "enabled" in kwargs:
            self.enabled = bool(kwargs["enabled"])

        if "double_coercion" in kwargs:
            self.double_coercion = kwargs["double_coercion"]
            
        if "rate_limit" in kwargs:
            self.rate_limit = kwargs["rate_limit"]

        if "enabled" in kwargs:
            self.enabled = bool(kwargs["enabled"])

        self.set_client(**kwargs)

    def jiggle_randomness(self, prompt_config: dict, offset: float = 0.3) -> dict:
        """
        adjusts temperature and presence penalty
        by random values using the base value as a center
        """

        temp = prompt_config["temperature"]

        min_offset = offset * 0.3

        prompt_config["temperature"] = random.uniform(temp + min_offset, temp + offset)

        try:
            presence_penalty = prompt_config["presence_penalty"]
            prompt_config["presence_penalty"] = round(
                random.uniform(presence_penalty + 0.1, presence_penalty + offset), 1
            )
        except KeyError:
            pass
