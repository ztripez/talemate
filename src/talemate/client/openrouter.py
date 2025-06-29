import pydantic
import structlog
import httpx
import asyncio
import json
import litellm
from litellm import acompletion
from litellm.utils import supports_reasoning
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    APIError
)

from talemate.client.base import ClientBase, ErrorAction, CommonDefaults
from talemate.client.registry import register
from talemate.config import load_config
from talemate.emit import emit
from talemate.emit.signals import handlers

__all__ = [
    "OpenRouterClient",
]

log = structlog.get_logger("talemate.client.openrouter")

# Available models will be populated when first client with API key is initialized
AVAILABLE_MODELS = []
DEFAULT_MODEL = ""
MODELS_FETCHED = False

async def fetch_available_models(api_key: str = None):
    """Fetch available models from OpenRouter API"""
    global AVAILABLE_MODELS, DEFAULT_MODEL, MODELS_FETCHED
    
    if not api_key:
        return []
    
    if MODELS_FETCHED:
        return AVAILABLE_MODELS
    
    # Only fetch if we haven't already or if explicitly requested
    if AVAILABLE_MODELS and not api_key:
        return AVAILABLE_MODELS
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id")
                    if model_id:
                        models.append(model_id)
                AVAILABLE_MODELS = sorted(models)
                log.debug(f"Fetched {len(AVAILABLE_MODELS)} models from OpenRouter")
            else:
                log.warning(f"Failed to fetch models from OpenRouter: {response.status_code}")
    except Exception as e:
        log.error(f"Error fetching models from OpenRouter: {e}")
    
    MODELS_FETCHED = True
    return AVAILABLE_MODELS



def fetch_models_sync(event):
    api_key = event.data.get("openrouter", {}).get("api_key")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fetch_available_models(api_key))

handlers["config_saved"].connect(fetch_models_sync)
handlers["talemate_started"].connect(fetch_models_sync)

class Defaults(CommonDefaults, pydantic.BaseModel):
    max_token_length: int = 32768
    model: str = DEFAULT_MODEL


@register()
class OpenRouterClient(ClientBase):
    """
    OpenRouter client for generating text using various models.
    """

    client_type = "openrouter"
    conversation_retries = 0
    auto_break_repetition_enabled = False
    # TODO: make this configurable?
    decensor_enabled = False

    class Meta(ClientBase.Meta):
        name_prefix: str = "OpenRouter"
        title: str = "OpenRouter"
        manual_model: bool = True
        manual_model_choices: list[str] = pydantic.Field(default_factory=lambda: AVAILABLE_MODELS)
        requires_prompt_template: bool = False
        defaults: Defaults = Defaults()

    def __init__(self, model=None, **kwargs):
        # Initialize OpenRouter-specific attributes before calling super().__init__
        # because super().__init__ will call set_client() which needs these attributes
        self.api_key_status = None
        self._models_fetched = False
        
        super().__init__(**kwargs)
        
        # Initialize config from load_config
        self.config = load_config()
        handlers["config_saved"].connect(self.on_config_saved)

    @property
    def can_be_coerced(self) -> bool:
        return True

    @property   
    def openrouter_api_key(self):
        # First check if api_key was set during initialization (from model config)
        if hasattr(self, 'api_key') and self.api_key:
            return self.api_key
        # Otherwise fall back to config file if it exists
        if hasattr(self, 'config') and self.config:
            return self.config.get("openrouter", {}).get("api_key")
        return None

    @property
    def supported_parameters(self):
        return [
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "frequency_penalty",
            "presence_penalty",
            "repetition_penalty",
            "max_tokens",
        ]

    def emit_status(self, processing: bool = None):
        error_action = None
        if processing is not None:
            self.processing = processing

        if self.openrouter_api_key:
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
                    "openrouter_api",
                ],
            )

        if not self.model_name:
            status = "error"
            model_name = "No model loaded"

        self.current_status = status

        data = {
            "error_action": error_action.model_dump() if error_action else None,
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
        if not self.openrouter_api_key:
            log.error("No OpenRouter API key set")
            if hasattr(self, 'api_key_status') and self.api_key_status:
                self.api_key_status = False
                emit("request_client_status")
                emit("request_agent_status")
            return

        if not self.model_name:
            self.model_name = DEFAULT_MODEL

        if max_token_length and not isinstance(max_token_length, int):
            max_token_length = int(max_token_length)
        
        # Configure LiteLLM for OpenRouter
        if self.openrouter_api_key:
            litellm.api_key = self.openrouter_api_key
        litellm.api_base = self.openrouter_api_key
        
        # Set max token length (default to 32k if not specified)
        if max_token_length is not None:
            self.max_token_length = max_token_length
        else:
            self.max_token_length = 32768

        if not hasattr(self, 'api_key_status') or not self.api_key_status:
            if hasattr(self, 'api_key_status') and self.api_key_status is False:
                emit("request_client_status")
                emit("request_agent_status")
            self.api_key_status = True

        log.info(
            "openrouter set client",
            max_token_length=self.max_token_length,
            provided_max_token_length=max_token_length,
            model=self.model_name,
        )

    def reconfigure(self, **kwargs):
        if kwargs.get("model"):
            self.model_name = kwargs["model"]
            self.set_client(kwargs.get("max_token_length"))

        if "enabled" in kwargs:
            self.enabled = bool(kwargs["enabled"])

        self._reconfigure_common_parameters(**kwargs)

    def on_config_saved(self, event):
        config = event.data
        self.config = config
        self.set_client(max_token_length=self.max_token_length)

    async def status(self):
        # Fetch models if we have an API key and haven't fetched yet
        if self.openrouter_api_key and not self._models_fetched:
            self._models_fetched = True
            # Update the Meta class with new model choices
            self.Meta.manual_model_choices = AVAILABLE_MODELS
        
        self.emit_status()

    def prompt_template(self, system_message: str, prompt: str):
        """
        Open-router handles the prompt template internally, so we just
        give the prompt as is.
        """
        return prompt

    async def generate(self, prompt: str, parameters: dict, kind: str):
        """
        Generates text from the given prompt and parameters using LiteLLM.
        """

        if not self.openrouter_api_key:
            raise Exception("No OpenRouter API key set")

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
                "model": f"openrouter/{self.model_name}",
                "messages": messages,
                "stream": False,  # Disable streaming for now to fix the issue
                **parameters,
            }
            
            # For reasoning models, request reasoning content
            if supports_reasoning(f"openrouter/{self.model_name}"):
                litellm_params["include_reasoning"] = True
                log.info("OpenRouter detected reasoning model, requesting reasoning content")
            
            # Add system message if provided
            if system_message:
                litellm_params["messages"] = [
                    {"role": "system", "content": system_message}
                ] + messages

            # Set API key and base URL if needed
            if self.openrouter_api_key:
                litellm_params["api_key"] = self.openrouter_api_key
            litellm_params["api_base"] = "https://openrouter.ai/api/v1"

            log.info("OpenRouter making API call", model=litellm_params["model"], messages_count=len(litellm_params["messages"]))
            response = await acompletion(**litellm_params)
            
            log.info("OpenRouter API response received", response_type=type(response).__name__, has_choices=hasattr(response, 'choices'))
            
            # Extract the response text
            if hasattr(response, 'choices') and response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                log.info("OpenRouter choice details", choice_type=type(choice).__name__, has_message=hasattr(choice, 'message'), has_text=hasattr(choice, 'text'))
                
                if hasattr(choice, 'message') and choice.message:
                    content = choice.message.content or ""
                    log.info("OpenRouter extracted from message.content", content_length=len(content), content_preview=content[:100] if content else "EMPTY")
                    
                    # For reasoning models, check if LiteLLM provided reasoning content separately
                    if hasattr(choice, 'message') and hasattr(choice.message, 'reasoning_content') and choice.message.reasoning_content:
                        reasoning_content = choice.message.reasoning_content
                        log.info("OpenRouter reasoning model response with reasoning content",
                                model=self.model_name,
                                has_reasoning=True,
                                content_length=len(content),
                                reasoning_length=len(reasoning_content))
                        
                        # If main content is empty but we have reasoning content, extract final answer from reasoning
                        if not content and reasoning_content:
                            # For DeepSeek R1, the reasoning content contains both thinking and final answer
                            # Try to extract the final answer after the reasoning
                            final_answer = self._extract_final_answer_from_reasoning(reasoning_content)
                            if final_answer:
                                content = final_answer
                                log.info("OpenRouter extracted final answer from reasoning", content_length=len(content))
                            else:
                                # Fallback: use the reasoning content as-is
                                content = reasoning_content
                                log.info("OpenRouter using full reasoning content as fallback", content_length=len(content))
                        elif content and reasoning_content:
                            # Both content and reasoning are present - this is the ideal case
                            # Log that we have both but use the main content as intended
                            log.info("OpenRouter reasoning model returned both content and reasoning",
                                    content_length=len(content),
                                    reasoning_length=len(reasoning_content))
                    
                    # Check for other potential content fields as fallback
                    if not content and hasattr(choice.message, 'text'):
                        alt_content = choice.message.text or ""
                        log.info("OpenRouter message.text found", content_length=len(alt_content), content_preview=alt_content[:100] if alt_content else "EMPTY")
                        if alt_content:
                            content = alt_content
                    
                elif hasattr(choice, 'text'):
                    content = choice.text or ""
                    log.info("OpenRouter extracted from choice.text", content_length=len(content), content_preview=content[:100] if content else "EMPTY")
                else:
                    content = ""
                    log.warning("OpenRouter choice has no message or text attribute", choice_attrs=dir(choice))
                    
                # Extract token usage if available
                if hasattr(response, 'usage') and response.usage:
                    self._returned_prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
                    self._returned_response_tokens = getattr(response.usage, 'completion_tokens', None)
                    log.info("OpenRouter token usage", prompt_tokens=self._returned_prompt_tokens, completion_tokens=self._returned_response_tokens)

                log.info("OpenRouter final content", content_length=len(content), is_empty=not content.strip())
                return content
            else:
                log.warning("OpenRouter response has no choices or empty choices", has_choices=hasattr(response, 'choices'), choices_length=len(response.choices) if hasattr(response, 'choices') and response.choices else 0)
                return ""
        except AuthenticationError as e:
            self.log.error("generate error - authentication", e=e)
            emit("status", message="OpenRouter API: Authentication Failed", status="error")
            return ""
        except RateLimitError as e:
            self.log.error("generate error - rate limit", e=e)
            emit("status", message="OpenRouter API: Rate Limit Exceeded", status="error")
            return ""
        except BadRequestError as e:
            self.log.error("generate error - bad request", e=e)
            emit("status", message="OpenRouter API: Bad Request", status="error")
            return ""
        except ServiceUnavailableError as e:
            self.log.error("generate error - service unavailable", e=e)
            emit("status", message="OpenRouter API: Service Unavailable", status="error")
            return ""
        except Timeout as e:
            self.log.error("generate error - timeout", e=e)
            emit("status", message="OpenRouter API: Request Timeout", status="error")
            return ""
        except Exception as e:
            self.log.error("generate error", e=e)
            emit("status", message="Error during generation (check logs)", status="error")
            return ""

    def _extract_final_answer_from_reasoning(self, reasoning_content: str) -> str:
        """
        Extract the final answer from reasoning content for reasoning models like DeepSeek R1.
        
        DeepSeek R1 and similar reasoning models often structure their reasoning content with
        the thinking process followed by a final answer section.
        """
        if not reasoning_content:
            return ""
        
        # Common patterns for final answer extraction
        final_answer_markers = [
            "Final answer:",
            "Answer:",
            "Conclusion:",
            "Therefore:",
            "In conclusion:",
            "So the answer is:",
            "The answer is:",
            "My final answer is:",
            "\n\n---\n\n",  # Some models use separator lines
            "\n\nFinal response:",
            "\n\nResponse:",
        ]
        
        # Try to find a final answer marker and extract content after it
        for marker in final_answer_markers:
            if marker.lower() in reasoning_content.lower():
                # Find the marker (case insensitive)
                marker_pos = reasoning_content.lower().find(marker.lower())
                if marker_pos != -1:
                    # Extract everything after the marker
                    final_answer = reasoning_content[marker_pos + len(marker):].strip()
                    if final_answer:
                        log.info("OpenRouter extracted final answer using marker", marker=marker, answer_length=len(final_answer))
                        return final_answer
        
        # If no clear marker found, try to extract the last paragraph/section
        # that looks like a final answer (not thinking process)
        lines = reasoning_content.strip().split('\n')
        
        # Look for the last substantial paragraph that doesn't contain thinking indicators
        thinking_indicators = [
            "let me think",
            "i need to",
            "first,",
            "second,",
            "next,",
            "then,",
            "hmm",
            "wait",
            "actually",
            "let's see",
            "i should",
            "maybe",
            "perhaps",
            "it seems",
            "i think",
            "considering",
            "looking at",
        ]
        
        # Start from the end and work backwards to find a good final answer
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if not line:
                continue
                
            # Skip lines that look like thinking process
            is_thinking = any(indicator in line.lower() for indicator in thinking_indicators)
            if is_thinking:
                continue
                
            # If we find a substantial line that doesn't look like thinking, use it and everything after
            if len(line) > 20:  # Substantial content
                final_section = '\n'.join(lines[i:]).strip()
                if final_section:
                    log.info("OpenRouter extracted final answer from last section", answer_length=len(final_section))
                    return final_section
        
        # If all else fails, return the last 30% of the content as it's likely the conclusion
        # Increased from 20% to 30% to avoid cutting off mid-sentence
        content_length = len(reasoning_content)
        if content_length > 100:
            # Try 30% first
            final_portion = reasoning_content[int(content_length * 0.7):].strip()
            if final_portion:
                log.info("OpenRouter extracted final answer from last 30% of content", answer_length=len(final_portion))
                return final_portion
            
            # If that's too small, try 40%
            final_portion = reasoning_content[int(content_length * 0.6):].strip()
            if final_portion:
                log.info("OpenRouter extracted final answer from last 40% of content", answer_length=len(final_portion))
                return final_portion
        
        # No clear final answer found
        log.warning("OpenRouter could not extract clear final answer from reasoning content")
        return ""