# koboldcpp_provider.py
from typing import List, Dict, Any, Optional

import litellm
from .base_provider import BaseProvider, ProviderSetting
import json, time, requests, httpx, itertools
from typing import Iterator, AsyncIterator
from litellm.llms.custom_llm import CustomLLM
from litellm.types.utils import ModelInfoBase,ModelResponse, GenericStreamingChunk

_KOBOLD_PARAMS = {
    "rep_pen", "rep_pen_range", "typical_p", "tfs_z", "top_a", "top_k",
    "mirostat", "mirostat_tau", "mirostat_eta", "min_p", "xtc_threshold",
    "xtc_probability", "dynatemp_range", "dynatemp_exponent",
    "banned_tokens", "sampler_priority", "sampler_order", "sampler_seed",
    "presence_penalty", "frequency_penalty", "logit_bias",
    "use_default_badwordsids",
}

_identifier_ = "koboldcpp"


class KoboldCppProvider(BaseProvider):
    """KoboldCpp LiteLLM Provider"""
    
    @classmethod
    def get_provider_name(cls) -> str:
        return "KoboldCpp"
    
    @classmethod
    def get_provider_identifier(cls) -> str:
        return _identifier_
    
    @classmethod
    def get_settings_schema(cls) -> List[ProviderSetting]:
        return [
            ProviderSetting(
                key="api_base",
                label="API Base URL",
                type="text",
                required=True,
                default="http://localhost:5001",
                description="KoboldCpp API base URL"
            ),
            ProviderSetting(
                key="api_key",
                label="API Key",
                type="password",
                required=False,
                default="dummy",
                description="KoboldCpp doesn't require an API key, but LiteLLM needs one",
                hidden=True 
            )

        ]
    
    def get_available_models(self, settings: Dict[str, Any] = None) -> List[str]:
        """Get the currently loaded model from KoboldCpp"""
        if not settings or not settings.get("api_base"):
            return ["unknown"]
        
        try:
            import requests
            api_base = settings["api_base"].rstrip("/")
            r = requests.get(f"{api_base}/api/v1/model", timeout=5)
            name = r.json().get("result", "unknown")
            return [name]
        except Exception:
            return ["unknown"]
    
    def get_model_parameters(self, model_name: str) -> List[str]:
        """Get supported parameters for KoboldCpp models"""
        kobold_params = list(_KOBOLD_PARAMS)
        standard_params = ["temperature", "max_tokens", "top_p"]
        all_params = set(kobold_params + standard_params)
        return sorted(list(all_params))
    
    def _build_litellm_params(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """Build parameters for KoboldCpp litellm call"""
        api_base = self.config.settings.get("api_base", "http://localhost:5001")
        full_model_name = f"{_identifier_}/{model_name}"
        supported_params = self.get_model_parameters(model_name)
        params = {
            "model": full_model_name,
            "api_base": api_base,
            "custom_llm_provider": _identifier_,
        }
        for key, value in kwargs.items():
            if key in supported_params or key in ["messages", "stream"]:
                params[key] = value
        params["api_key"] = self.config.settings.get("api_key", "dummy")
        return params


class KoboldCppLiteLLM(CustomLLM):
    def __init__(self):
        super().__init__()

    def _build_payload(self, messages, max_tokens, opts):
        prompt = "".join(m["content"] for m in messages if m["role"] != "system")
        p = {"prompt": prompt, "max_length": max_tokens or 256}
        for k, v in opts.items():
            if k in _KOBOLD_PARAMS or k in ("temperature", "top_p"):
                p[k] = v
        return p

    @staticmethod
    def _mk_usage(prompt_tokens: int, completion_tokens: int):
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    def completion(self, *, model, messages, max_tokens=None, optional_params=None, **kwargs):
        optional_params = optional_params or {}
        # Get api_base from kwargs - LiteLLM passes it dynamically
        api_base = kwargs.get("api_base")
        if not api_base:
            raise Exception("KoboldCpp completion requires api_base to be set in kwargs")
        api_base = api_base.rstrip("/")
        
        payload = self._build_payload(messages, max_tokens, optional_params)
        r = requests.post(f"{api_base}/api/v1/generate", json=payload,
                          timeout=optional_params.get("timeout", 60))
        d = r.json()
        txt = d["results"][0]["text"]
        return ModelResponse(
            id=f"kcpp-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=model,
            choices=[{"index": 0, "finish_reason": "stop",
                      "message": {"role": "assistant", "content": txt}}],
            usage=self._mk_usage(d.get("prompt_tokens", 0),
                                 d.get("tokens_generated", len(txt.split())))
        )

    def streaming(self, *, model, messages, max_tokens=None, optional_params=None, **kwargs) -> Iterator[GenericStreamingChunk]:
        optional_params = optional_params or {}
        # Get api_base from kwargs - LiteLLM passes it dynamically
        api_base = kwargs.get("api_base")
        if not api_base:
            raise Exception("KoboldCpp streaming requires api_base to be set in kwargs")
        api_base = api_base.rstrip("/")
        
        payload = self._build_payload(messages, max_tokens, optional_params)
        s = requests.post(
            f"{api_base}/api/extra/generate/stream",
            json=payload,
            stream=True,
            timeout=optional_params.get("timeout", None),
        )  # SSE endpoint
        buf, idx = "", 0
        for line in s.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            tok = json.loads(line[5:].strip())  # {"token": "x", ...}
            if tok.get("token") is None:
                continue
            buf += tok["token"]
            yield {           # GenericStreamingChunk spec :contentReference[oaicite:1]{index=1}
                "index": idx,
                "text": tok["token"],
                "finish_reason": None,
                "is_finished": False,
                "tool_use": None,
                "usage": {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1},
            }
            idx += 1
        yield {
            "index": idx,
            "text": "",
            "finish_reason": "stop",
            "is_finished": True,
            "tool_use": None,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    async def acompletion(self, *, model, messages, max_tokens=None, optional_params=None, **kwargs):
        optional_params = optional_params or {}
        # Get api_base from kwargs - LiteLLM passes it dynamically
        api_base = kwargs.get("api_base")
        if not api_base:
            raise Exception("KoboldCpp acompletion requires api_base to be set in kwargs")
        api_base = api_base.rstrip("/")
        
        payload = self._build_payload(messages, max_tokens, optional_params)
        async with httpx.AsyncClient(timeout=optional_params.get("timeout", 60)) as client:
            r = await client.post(f"{api_base}/api/v1/generate", json=payload)
            d = r.json()
        txt = d["results"][0]["text"]
        return ModelResponse(
            id=f"kcpp-{int(time.time())}",
            object="chat.completion",
            created=int(time.time()),
            model=model,
            choices=[{"index": 0, "finish_reason": "stop",
                      "message": {"role": "assistant", "content": txt}}],
            usage=self._mk_usage(d.get("prompt_tokens", 0),
                                 d.get("tokens_generated", len(txt.split())))
        )

    async def astreaming(self, *, model, messages, max_tokens=None, optional_params=None, **kwargs) -> AsyncIterator[GenericStreamingChunk]:
        optional_params = optional_params or {}
        # Get api_base from kwargs - LiteLLM passes it dynamically
        api_base = kwargs.get("api_base")
        if not api_base:
            raise Exception("KoboldCpp astreaming requires api_base to be set in kwargs")
        api_base = api_base.rstrip("/")
        
        payload = self._build_payload(messages, max_tokens, optional_params)
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{api_base}/api/extra/generate/stream",
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    raise Exception(f"KoboldCpp streaming endpoint not available (status: {resp.status_code})")
                
                idx = 0
                async for raw in resp.aiter_lines():
                    if not raw or not raw.startswith("data:"):
                        continue
                    tok = json.loads(raw[5:].strip())
                    if tok.get("token") is None:
                        continue
                    yield {
                        "index": idx,
                        "text": tok["token"],
                        "finish_reason": None,
                        "is_finished": False,
                        "tool_use": None,
                        "usage": {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1},
                    }
                    idx += 1
                yield {
                    "index": idx,
                    "text": "",
                    "finish_reason": "stop",
                    "is_finished": True,
                    "tool_use": None,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                }

    def list_models(self, api_base: Optional[str] = None) -> list[str]:
        """
        KoboldCpp runs exactly one model at a time; `/api/v1/model`
        returns its short name.
        """
        if not api_base:
            raise Exception("KoboldCpp list_models requires api_base parameter")
        try:
            r = requests.get(f"{api_base.rstrip('/')}/api/v1/model", timeout=5)
            name = r.json().get("result") or r.text.strip()
            return [f"{_identifier_}/{name}"]
        except Exception:
            raise
    
    def get_model_info(self, model: str, api_base: Optional[str] = None) -> ModelInfoBase:
        """
        Populate LiteLLM's `ModelInfoBase` from the three public
        endpoints KoboldCpp exposes.
        """
        if not api_base:
            raise Exception("KoboldCpp get_model_info requires api_base parameter")
        
        api_base = api_base.rstrip("/")
        info = requests.get(f"{api_base}/api/v1/model").json()
        real_name = info.get("result", "unknown")

        ctx = requests.get(f"{api_base}/api/v1/config/max_context_length").json().get("value", None)
        gen = requests.get(f"{api_base}/api/v1/config/max_length").json().get("value", None)

        return ModelInfoBase(
            key=f"{_identifier_}/{real_name}",
            litellm_provider=_identifier_,
            mode="chat",
            input_cost_per_token=0.0,
            output_cost_per_token=0.0,
            max_tokens=gen,
            max_input_tokens=ctx,
            max_output_tokens=gen,
        )














