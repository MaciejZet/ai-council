"""
LLM Provider Abstraction Layer
===============================
Obsługuje wiele providerów LLM: OpenAI, Grok (xAI), Gemini, DeepSeek, Perplexity, OpenRouter
Z obsługą zwracania usage (tokeny) i retry logic
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, AsyncGenerator, List
from dataclasses import dataclass
from dotenv import load_dotenv

import httpx

# Import retry decorators
from src.utils.error_handler import retry_with_backoff, timeout

load_dotenv()

# Krótka lista gdy katalog OpenRouter jest niedostępny (sieć, timeout).
OPENROUTER_MODELS_FALLBACK: List[str] = [
    "google/gemini-3-pro-preview:free",
    "google/gemini-2.0-flash-exp:free",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-405b-instruct",
    "mistralai/mistral-large-2407",
    "microsoft/wizardlm-2-8x22b",
    "qwen/qwen-2.5-72b-instruct",
]

_openrouter_catalog_cache: Dict[str, tuple[float, List[Dict[str, str]], float]] = {}
_OPENROUTER_CATALOG_TTL_SEC = 300.0
_OPENROUTER_CATALOG_FAILURE_TTL_SEC = 30.0
_OPENROUTER_CATALOG_TIMEOUT_SEC = 8.0


def _parse_openrouter_price(value: Any) -> float:
    """OpenRouter zwraca ceny za token jako string lub liczbę."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    s = str(value).strip()
    if not s or s == "0":
        return 0.0
    try:
        return max(0.0, float(s))
    except ValueError:
        return 0.0


def openrouter_tier_for_row(row: dict) -> str:
    """
    Kategoria UI: free | cheap | standard | premium wg id (:free) i pricing.prompt/completion (USD / token).
    """
    mid = str(row.get("id") or "").strip().lower()
    if ":free" in mid:
        return "free"
    pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
    raw_p = pricing.get("prompt")
    raw_c = pricing.get("completion")
    has_any = raw_p is not None or raw_c is not None
    pin = _parse_openrouter_price(raw_p)
    pout = _parse_openrouter_price(raw_c)
    mx = max(pin, pout)
    if not has_any:
        return "standard"
    if mx <= 0:
        return "free"
    per_1m = mx * 1_000_000
    if per_1m < 0.35:
        return "cheap"
    if per_1m < 4.0:
        return "standard"
    return "premium"


async def fetch_openrouter_catalog_entries(
    base_url: Optional[str] = None, *, use_cache: bool = True
) -> List[Dict[str, str]]:
    """
    Katalog OpenRouter: id + tier (do zakładek w UI).
    GET /v1/models — bez klucza API.
    """
    root = (base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")).rstrip("/")
    models_url = f"{root}/models"
    now = time.monotonic()

    if use_cache and root in _openrouter_catalog_cache:
        ts, cached, ttl = _openrouter_catalog_cache[root]
        if now - ts < ttl:
            return [dict(x) for x in cached]

    try:
        timeout = httpx.Timeout(_OPENROUTER_CATALOG_TIMEOUT_SEC, connect=3.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(models_url)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        if use_cache:
            _openrouter_catalog_cache[root] = (now, [], _OPENROUTER_CATALOG_FAILURE_TTL_SEC)
        return []

    rows = payload.get("data") or []
    by_id: Dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        model_id = str(row["id"]).strip()
        by_id[model_id] = openrouter_tier_for_row(row)
    out: List[Dict[str, str]] = [{"id": i, "tier": by_id[i]} for i in sorted(by_id)]
    if use_cache:
        _openrouter_catalog_cache[root] = (now, out, _OPENROUTER_CATALOG_TTL_SEC)
    return [dict(x) for x in out]


async def fetch_openrouter_model_ids(
    base_url: Optional[str] = None, *, use_cache: bool = True
) -> List[str]:
    """Posortowane id modeli OpenRouter (jak wcześniej)."""
    entries = await fetch_openrouter_catalog_entries(base_url, use_cache=use_cache)
    return [e["id"] for e in entries]


@dataclass
class LLMResponse:
    """Odpowiedź z LLM z danymi o użyciu tokenów"""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    
    @property
    def usage(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
        }


# Koszty per 1K tokenów (input/output averaged)
TOKEN_COSTS = {
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-5-nano": {"input": 0.001, "output": 0.004},
    "gpt-5-mini": {"input": 0.003, "output": 0.012},
    "gpt-5": {"input": 0.01, "output": 0.03},
    "o1-mini": {"input": 0.003, "output": 0.012},
    # Grok
    "grok-2": {"input": 0.002, "output": 0.01},
    "grok-beta": {"input": 0.005, "output": 0.015},
    # Gemini
    "gemini-3-pro-preview": {"input": 0.00, "output": 0.00},      # Preview pricing (usually free or specific tier)
    "gemini-3-flash-preview": {"input": 0.00, "output": 0.00},    # Preview pricing
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},        # Estimated/Previous pro pricing
    "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},    # Estimated/Previous flash pricing
    "gemini-2.0-flash-exp": {"input": 0.00, "output": 0.00},     # Free tier
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    # DeepSeek
    "deepseek-chat": {"input": 0.00027, "output": 0.0011},      # DeepSeek V3
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219}, # DeepSeek R1
    # Perplexity
    "sonar": {"input": 0.001, "output": 0.001},
    "sonar-pro": {"input": 0.003, "output": 0.015},
    "sonar-reasoning": {"input": 0.001, "output": 0.005},
    # OpenRouter (prices vary significantly, these are placeholders/averages)
    "openrouter-default": {"input": 0.001, "output": 0.002},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Oblicza koszt w USD na podstawie modelu i tokenów"""
    costs = TOKEN_COSTS.get(model, {"input": 0.002, "output": 0.008})
    input_cost = (prompt_tokens / 1000) * costs["input"]
    output_cost = (completion_tokens / 1000) * costs["output"]
    return input_cost + output_cost


class LLMProvider(ABC):
    """Abstrakcyjna klasa bazowa dla providerów LLM"""
    
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        """Generuje odpowiedź na podstawie promptów, zwraca LLMResponse z usage"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Zwraca nazwę providera"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi jeden po drugim"""
        pass
    
    async def get_available_models(self) -> List[str]:
        """Zwraca listę dostępnych modeli (jeśli provider to obsługuje)"""
        return []


class OpenAIProvider(LLMProvider):
    """Provider dla OpenAI GPT"""

    def __init__(self, model: str = "gpt-4o", base_url: Optional[str] = None, api_key: Optional[str] = None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY", "dummy"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL")
        )
        self.model = model
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    @timeout(60.0)
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=self.model
        )
    
    def get_name(self) -> str:
        return f"OpenAI ({self.model})"
    
    async def generate_stream(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z OpenAI"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GrokProvider(LLMProvider):
    """Provider dla Grok (xAI)"""

    def __init__(self, model: str = "grok-beta", base_url: Optional[str] = None, api_key: Optional[str] = None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("GROK_API_KEY", "dummy"),
            base_url=base_url or os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")
        )
        self.model = model
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    @timeout(60.0)
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=self.model
        )
    
    def get_name(self) -> str:
        return f"Grok ({self.model})"
    
    async def generate_stream(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z Grok (OpenAI-compatible API)"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True,
            max_tokens=max_tokens
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GeminiProvider(LLMProvider):
    """Provider dla Google Gemini"""

    def __init__(self, model: str = "gemini-1.5-pro", api_key: Optional[str] = None):
        import google.generativeai as genai
        genai.configure(api_key=api_key or os.getenv("GEMINI_API_KEY", "dummy"))
        self.model = genai.GenerativeModel(model)
        self.model_name = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        
        generation_config = {"temperature": temperature}
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens

        response = await self.model.generate_content_async(
            full_prompt,
            generation_config=generation_config
        )
        
        # Gemini usage metadata
        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
            completion_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
        
        return LLMResponse(
            content=response.text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=self.model_name
        )
    
    def get_name(self) -> str:
        return f"Gemini ({self.model_name})"
    
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z Gemini"""
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        generation_config = {"temperature": temperature}
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens

        response = await self.model.generate_content_async(
            full_prompt,
            generation_config=generation_config,
            stream=True
        )
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text


class DeepSeekProvider(LLMProvider):
    """Provider dla DeepSeek (OpenAI-compatible API)"""

    def __init__(self, model: str = "deepseek-chat", base_url: Optional[str] = None, api_key: Optional[str] = None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", "dummy"),
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        self.model = model
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    @timeout(60.0)
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=self.model
        )
    
    def get_name(self) -> str:
        return f"DeepSeek ({self.model})"
    
    async def generate_stream(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z DeepSeek"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True,
            max_tokens=max_tokens
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class PerplexityProvider(LLMProvider):
    """
    Provider dla Perplexity AI (OpenAI-compatible API)

    Models:
    - sonar: Fast, cost-effective search (128K context)
    - sonar-pro: Advanced search with deeper analysis
    """

    def __init__(self, model: str = "sonar-pro", base_url: Optional[str] = None, api_key: Optional[str] = None):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("PERPLEXITY_API_KEY", "dummy"),
            base_url=base_url or os.getenv("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")
        )
        self.model = model
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    @timeout(60.0)
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=self.model
        )
    
    def get_name(self) -> str:
        return f"Perplexity ({self.model})"
    
    async def generate_stream(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z Perplexity"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True,
            max_tokens=max_tokens
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OpenRouterProvider(LLMProvider):
    """
    Provider dla OpenRouter (Unified Interface for LLMs)
    """

    def __init__(self, model: str = "google/gemini-2.0-flash-exp:free", base_url: Optional[str] = None, api_key: Optional[str] = None):
        from openai import AsyncOpenAI
        resolved_base = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENROUTER_API_KEY", "dummy"),
            base_url=resolved_base,
        )
        self.model = model
        self._openrouter_base_url = resolved_base
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> LLMResponse:
        # OpenRouter often requires 'referer' and 'title' headers, 
        # but the OpenAI client doesn't make it easy to add custom headers globally without hacks.
        # However, it usually works without them for basic access or if configured in the dashboard.
        # Alternatively, we can pass `extra_headers` to the client constructor if using a newer openai lib,
        # or `extra_headers` in the request logic if supported.
        # For now, we'll try standard OpenAI compatible request.
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            # extra_headers={
            #     "HTTP-Referer": "http://localhost:8000", 
            #     "X-Title": "Local App"
            # }
        )
        
        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=self.model
        )
    
    def get_name(self) -> str:
        return f"OpenRouter ({self.model})"
    
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z OpenRouter"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            stream=True,
            max_tokens=max_tokens,
            # extra_headers={
            #     "HTTP-Referer": "http://localhost:8000", 
            #     "X-Title": "Local App"
            # }
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def get_available_models(self) -> List[str]:
        """Zwraca listę modeli dostępnych w OpenRouter (pełny katalog z API)."""
        models = await fetch_openrouter_model_ids(self._openrouter_base_url)
        return models if models else list(OPENROUTER_MODELS_FALLBACK)


def get_provider(provider_name: Optional[str] = None, model: Optional[str] = None) -> LLMProvider:
    """
    Fabryka providerów LLM
    
    Args:
        provider_name: "openai", "grok", "gemini" lub None (użyje domyślnego)
        model: opcjonalny model do użycia
    
    Returns:
        Instancja LLMProvider
    """
    if provider_name is None:
        provider_name = os.getenv("DEFAULT_LLM_PROVIDER", "openai")

    default_models = {
        "openai": "gpt-4o",
        "grok": "grok-beta",
        "gemini": "gemini-3-pro-preview",
        "deepseek": "deepseek-chat",
        "perplexity": "sonar-pro",
        "openrouter": "google/gemini-3-pro-preview:free",
        "custom": os.getenv("CUSTOM_MODEL", "local-model")
    }

    providers = {
        "openai": OpenAIProvider,
        "grok": GrokProvider,
        "gemini": GeminiProvider,
        "deepseek": DeepSeekProvider,
        "perplexity": PerplexityProvider,
        "openrouter": OpenRouterProvider,
        "custom": lambda model: __import_custom_provider(model)
    }

    if provider_name not in providers:
        raise ValueError(f"Nieznany provider: {provider_name}. Dostępne: {list(providers.keys())}")

    model_to_use = model or default_models.get(provider_name)

    # Special handling for custom provider
    if provider_name == "custom":
        from src.custom_api_provider import CustomAPIProvider
        return CustomAPIProvider(model=model_to_use)

    return providers[provider_name](model=model_to_use)


def __import_custom_provider(model: str):
    """Helper to import custom provider"""
    from src.custom_api_provider import CustomAPIProvider
    return CustomAPIProvider(model=model)


# Lista dostępnych providerów
AVAILABLE_PROVIDERS = ["openai", "grok", "gemini", "deepseek", "perplexity", "openrouter", "custom"]
