"""
Custom OpenAI-Compatible Provider
==================================
Universal provider for any OpenAI-compatible API (LM Studio, Ollama, vLLM, etc.)
"""

import os
import logging
from typing import Optional, AsyncGenerator
from openai import AsyncOpenAI

from src.llm_providers import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


def _debug_enabled() -> bool:
    return os.getenv("AI_COUNCIL_DEBUG_CUSTOM_PROVIDER", "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_secret(secret: Optional[str]) -> str:
    if not secret:
        return "<missing>"
    if len(secret) <= 6:
        return "***"
    return f"{secret[:3]}***{secret[-2:]}"


class CustomAPIProvider(LLMProvider):
    """
    Universal provider for OpenAI-compatible APIs

    Works with:
    - LM Studio (http://localhost:1234/v1)
    - Ollama with OpenAI compatibility (http://localhost:11434/v1)
    - vLLM (custom endpoint)
    - LocalAI (custom endpoint)
    - Any other OpenAI-compatible API
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize custom API provider

        Args:
            model: Model name (defaults to CUSTOM_MODEL env var)
            base_url: API endpoint (defaults to CUSTOM_BASE_URL env var)
            api_key: API key (defaults to CUSTOM_API_KEY env var, or "dummy" for local APIs)
        """
        self.model = model or os.getenv("CUSTOM_MODEL", "local-model")
        self.base_url = base_url or os.getenv("CUSTOM_BASE_URL", "http://localhost:1234/v1")
        self.api_key = api_key or os.getenv("CUSTOM_API_KEY", "dummy")

        if _debug_enabled():
            logger.debug(
                "CustomAPIProvider init model=%s base_url=%s api_key=%s",
                self.model,
                self.base_url,
                _redact_secret(self.api_key),
            )

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate response from custom API"""
        if _debug_enabled():
            logger.debug("CustomAPIProvider generate base_url=%s model=%s", self.base_url, self.model)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            logger.error("CustomAPIProvider error: %s", str(e))
            raise

        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=self.model
        )

    def get_name(self) -> str:
        """Get provider name"""
        return f"Custom API ({self.model})"

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from custom API"""
        if _debug_enabled():
            logger.debug("CustomAPIProvider stream base_url=%s model=%s", self.base_url, self.model)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
        except Exception as e:
            logger.error("CustomAPIProvider stream error (%s): %s", type(e).__name__, str(e))
            raise

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
