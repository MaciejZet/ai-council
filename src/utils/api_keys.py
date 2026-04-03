"""
API Key Management
==================
Manages API keys from localStorage instead of .env files
"""

from typing import Dict, Optional
from fastapi import HTTPException, Header
import json
import base64


class APIKeyManager:
    """Manages API keys from client localStorage"""

    @staticmethod
    def decode_api_keys(encoded_keys: Optional[str]) -> Dict[str, str]:
        """
        Decode API keys from base64-encoded JSON string

        Args:
            encoded_keys: Base64-encoded JSON string with API keys

        Returns:
            Dictionary of provider -> API key
        """
        if not encoded_keys:
            return {}

        try:
            # Decode from base64
            decoded = base64.b64decode(encoded_keys).decode('utf-8')
            keys = json.loads(decoded)
            return keys
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid API keys format: {str(e)}"
            )

    @staticmethod
    def get_api_key(
        provider: str,
        encoded_keys: Optional[str] = None,
        fallback_env: bool = True
    ) -> Optional[str]:
        """
        Get API key for a provider

        Priority:
        1. From encoded_keys (localStorage)
        2. From environment variables (if fallback_env=True)

        Args:
            provider: Provider name (openai, grok, etc.)
            encoded_keys: Base64-encoded API keys from client
            fallback_env: Whether to fallback to environment variables

        Returns:
            API key or None
        """
        import os

        # Try localStorage keys first
        if encoded_keys:
            keys = APIKeyManager.decode_api_keys(encoded_keys)
            if provider in keys and keys[provider]:
                return keys[provider]

        # Fallback to environment variables
        if fallback_env:
            env_key_map = {
                "openai": "OPENAI_API_KEY",
                "grok": "GROK_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "perplexity": "PERPLEXITY_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "custom": "CUSTOM_API_KEY",
            }

            env_var = env_key_map.get(provider)
            if env_var:
                return os.getenv(env_var)

        return None

    @staticmethod
    def get_base_url(
        provider: str,
        encoded_keys: Optional[str] = None,
        fallback_env: bool = True
    ) -> Optional[str]:
        """
        Get base URL for a provider

        Args:
            provider: Provider name
            encoded_keys: Base64-encoded config from client
            fallback_env: Whether to fallback to environment variables

        Returns:
            Base URL or None
        """
        import os

        # Try localStorage config first
        if encoded_keys:
            keys = APIKeyManager.decode_api_keys(encoded_keys)
            base_url_key = f"{provider}_base_url"
            if base_url_key in keys and keys[base_url_key]:
                return keys[base_url_key]

        # Fallback to environment variables
        if fallback_env:
            env_url_map = {
                "openai": "OPENAI_BASE_URL",
                "grok": "GROK_BASE_URL",
                "deepseek": "DEEPSEEK_BASE_URL",
                "perplexity": "PERPLEXITY_BASE_URL",
                "openrouter": "OPENROUTER_BASE_URL",
                "custom": "CUSTOM_BASE_URL",
            }

            env_var = env_url_map.get(provider)
            if env_var:
                return os.getenv(env_var)

        return None

    @staticmethod
    def create_provider_with_keys(
        provider_name: str,
        model: str,
        encoded_keys: Optional[str] = None
    ):
        """
        Create LLM provider instance with API keys from localStorage

        Args:
            provider_name: Provider name
            model: Model name
            encoded_keys: Base64-encoded API keys from client

        Returns:
            LLM provider instance
        """
        from src.llm_providers import (
            OpenAIProvider, GrokProvider, GeminiProvider,
            DeepSeekProvider, PerplexityProvider, OpenRouterProvider
        )
        from src.custom_api_provider import CustomAPIProvider

        # Get API key and base URL
        api_key = APIKeyManager.get_api_key(provider_name, encoded_keys)
        base_url = APIKeyManager.get_base_url(provider_name, encoded_keys)

        # Debug to file
        with open('debug_api_keys.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n=== APIKeyManager.create_provider_with_keys ===\n")
            f.write(f"  provider_name: {provider_name}\n")
            f.write(f"  model: {model}\n")
            f.write(f"  base_url: {base_url}\n")
            f.write(f"  api_key: {'***' if api_key else 'None'}\n")
            f.write(f"  encoded_keys present: {bool(encoded_keys)}\n")
            f.write(f"===============================================\n")

        # For custom provider, get model from localStorage if not provided
        if provider_name == "custom" and encoded_keys:
            keys = APIKeyManager.decode_api_keys(encoded_keys)
            custom_model = keys.get("custom_model")
            if custom_model:
                model = custom_model
                with open('debug_api_keys.txt', 'a', encoding='utf-8') as f:
                    f.write(f"  Using custom model from localStorage: {model}\n")

        # Create provider based on type
        provider_map = {
            "openai": OpenAIProvider,
            "grok": GrokProvider,
            "gemini": GeminiProvider,
            "deepseek": DeepSeekProvider,
            "perplexity": PerplexityProvider,
            "openrouter": OpenRouterProvider,
            "custom": CustomAPIProvider,
        }

        if provider_name not in provider_map:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = provider_map[provider_name]

        # Gemini doesn't use OpenAI-style API
        if provider_name == "gemini":
            return provider_class(model=model, api_key=api_key)
        else:
            return provider_class(
                model=model,
                base_url=base_url,
                api_key=api_key
            )


def get_api_keys_header(x_api_keys: Optional[str] = Header(None)) -> Optional[str]:
    """
    FastAPI dependency to extract API keys from header

    Usage:
        @app.post("/api/endpoint")
        async def endpoint(api_keys: Optional[str] = Depends(get_api_keys_header)):
            provider = create_provider_with_keys("openai", "gpt-4o", api_keys)
    """
    return x_api_keys
