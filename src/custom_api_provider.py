"""
Custom OpenAI-Compatible Provider
==================================
Universal provider for any OpenAI-compatible API (LM Studio, Ollama, vLLM, etc.)
"""

import os
from typing import Optional, AsyncGenerator
from openai import AsyncOpenAI

from src.llm_providers import LLMProvider, LLMResponse


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

        # Debug to file
        with open('debug_api_keys.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n=== CustomAPIProvider.__init__ ===\n")
            f.write(f"  model: {self.model}\n")
            f.write(f"  base_url: {self.base_url}\n")
            f.write(f"  api_key: {self.api_key[:20]}..." if self.api_key and len(self.api_key) > 20 else f"  api_key: {self.api_key}\n")
            f.write(f"===================================\n")

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
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"CustomAPIProvider - Base URL: {self.base_url}")
        logger.info(f"CustomAPIProvider - Model: {self.model}")
        logger.info(f"CustomAPIProvider - API Key: {self.api_key[:10]}..." if self.api_key else "No API key")

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
            logger.error(f"CustomAPIProvider error: {str(e)}")
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
        # Debug to file
        with open('debug_api_keys.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n=== CustomAPIProvider.generate_stream ===\n")
            f.write(f"  base_url: {self.base_url}\n")
            f.write(f"  model: {self.model}\n")
            f.write(f"  api_key: {self.api_key[:20]}..." if self.api_key and len(self.api_key) > 20 else f"  api_key: {self.api_key}\n")
            f.write(f"=========================================\n")

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
            with open('debug_api_keys.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n!!! ERROR in generate_stream !!!\n")
                f.write(f"  Error: {str(e)}\n")
                f.write(f"  Type: {type(e).__name__}\n")
                f.write(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
            raise

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
