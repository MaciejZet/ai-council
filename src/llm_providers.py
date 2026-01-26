"""
LLM Provider Abstraction Layer
===============================
Obsługuje wiele providerów LLM: OpenAI, Grok (xAI), Gemini, DeepSeek, Perplexity, OpenRouter
Z obsługą zwracania usage (tokeny)
"""

import os
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, AsyncGenerator, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


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
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
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
    
    def __init__(self, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
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
    
    def __init__(self, model: str = "grok-beta"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=os.getenv("GROK_API_KEY"),
            base_url="https://api.x.ai/v1"
        )
        self.model = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
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
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z Grok (OpenAI-compatible API)"""
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


class GeminiProvider(LLMProvider):
    """Provider dla Google Gemini"""
    
    def __init__(self, model: str = "gemini-1.5-pro"):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model)
        self.model_name = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        response = await self.model.generate_content_async(
            full_prompt,
            generation_config={"temperature": temperature}
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
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z Gemini"""
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        
        response = await self.model.generate_content_async(
            full_prompt,
            generation_config={"temperature": temperature},
            stream=True
        )
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text


class DeepSeekProvider(LLMProvider):
    """Provider dla DeepSeek (OpenAI-compatible API)"""
    
    def __init__(self, model: str = "deepseek-chat"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        self.model = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
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
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z DeepSeek"""
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


class PerplexityProvider(LLMProvider):
    """
    Provider dla Perplexity AI (OpenAI-compatible API)
    
    Models:
    - sonar: Fast, cost-effective search (128K context)
    - sonar-pro: Advanced search with deeper analysis
    """
    
    def __init__(self, model: str = "sonar-pro"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=os.getenv("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai"
        )
        self.model = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
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
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streamuje tokeny odpowiedzi z Perplexity"""
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


class OpenRouterProvider(LLMProvider):
    """
    Provider dla OpenRouter (Unified Interface for LLMs)
    """
    
    def __init__(self, model: str = "google/gemini-2.0-flash-exp:free"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = model
    
    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> LLMResponse:
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
            extra_headers={
                "HTTP-Referer": "https://github.com/MaciejZet/ai-council", 
                "X-Title": "AI Council"
            }
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
        temperature: float = 0.7
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
            extra_headers={
                "HTTP-Referer": "https://github.com/MaciejZet/ai-council", 
                "X-Title": "AI Council"
            }
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def get_available_models(self) -> List[str]:
        """Zwraca listę modeli dostępnych w OpenRouter"""
        try:
            response = await self.client.models.list()
            return [model.id for model in response.data]
        except Exception:
            return []


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
        "openrouter": "google/gemini-3-pro-preview:free"
    }
    
    providers = {
        "openai": OpenAIProvider,
        "grok": GrokProvider,
        "gemini": GeminiProvider,
        "deepseek": DeepSeekProvider,
        "perplexity": PerplexityProvider,
        "openrouter": OpenRouterProvider
    }
    
    if provider_name not in providers:
        raise ValueError(f"Nieznany provider: {provider_name}. Dostępne: {list(providers.keys())}")
    
    model_to_use = model or default_models.get(provider_name)
    return providers[provider_name](model=model_to_use)


# Lista dostępnych providerów
# Lista dostępnych providerów
AVAILABLE_PROVIDERS = ["openai", "grok", "gemini", "deepseek", "perplexity", "openrouter"]
