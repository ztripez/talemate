import pydantic
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

from talemate.client.base import ClientBase, ParameterReroute, CommonDefaults
from talemate.client.registry import register


class Defaults(CommonDefaults, pydantic.BaseModel):
    api_url: str = "http://localhost:1234"
    max_token_length: int = 8192


@register()
class LMStudioClient(ClientBase):
    auto_determine_prompt_template: bool = True
    client_type = "lmstudio"

    class Meta(ClientBase.Meta):
        name_prefix: str = "LMStudio"
        title: str = "LMStudio"
        defaults: Defaults = Defaults()

    @property
    def supported_parameters(self):
        return [
            "temperature",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            ParameterReroute(
                talemate_parameter="stopping_strings", client_parameter="stop"
            ),
        ]

    def set_client(self, **kwargs):
        # Configure LiteLLM for LMStudio
        litellm.api_base = self.api_url + "/v1"
        litellm.api_key = "sk-1111"  # LMStudio doesn't require a real API key

    def reconfigure(self, **kwargs):
        super().reconfigure(**kwargs)
        
        # Reconfigure LiteLLM if API URL changed
        if "api_url" in kwargs:
            self.set_client()

    async def get_model_name(self):
        model_name = await super().get_model_name()
        
        # model name comes back as a file path, so we need to extract the model name
        # the path could be windows or linux so it needs to handle both backslash and forward slash

        if model_name:
            model_name = model_name.replace("\\", "/").split("/")[-1]

        return model_name

    async def generate(self, prompt: str, parameters: dict, kind: str):
        """
        Generates text from the given prompt and parameters using LiteLLM.
        """

        self.log.debug(
            "generate",
            prompt=prompt[:128] + " ...",
            parameters=parameters,
        )

        try:
            # Convert to chat format for LiteLLM
            messages = [{"role": "user", "content": prompt}]
            
            # Prepare LiteLLM parameters
            litellm_params = {
                "model": f"lm_studio/{self.model_name}",  # Use LM Studio format
                "messages": messages,
                "stream": True,
                **parameters,
            }

            # Set API base and key
            litellm_params["api_base"] = self.api_url + "/v1"
            litellm_params["api_key"] = "sk-1111"

            stream = await acompletion(**litellm_params)

            response = ""

            # Iterate over streamed chunks and accumulate the response while
            # incrementally updating the token counter
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
            return ""
        except BadRequestError as e:
            self.log.error("generate error - bad request", e=e)
            return ""
        except ServiceUnavailableError as e:
            self.log.error("generate error - service unavailable", e=e)
            return ""
        except Timeout as e:
            self.log.error("generate error - timeout", e=e)
            return ""
        except Exception as e:
            self.log.error("generate error", e=e)
            return ""

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def response_tokens(self, response: str):
        """Count tokens in a model response string."""
        return self.count_tokens(response)

    def prompt_tokens(self, prompt: str):
        """Count tokens in a prompt string."""
        return self.count_tokens(prompt)
