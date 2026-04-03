#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Quatarly API
"""
import asyncio
import sys
from openai import AsyncOpenAI

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

async def test_quatarly():
    # Konfiguracja
    api_key = "qua-1100eeebe8ff00e4ae0fd5f5262a6f07"
    base_url = "https://api.quatarly.cloud/v1"
    model = "claude-haiku-4-5-20251001"

    print(f"Testing Quatarly API:")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {api_key[:20]}...")
    print()

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )

    try:
        print("Sending request...")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Hello, say hi!"}
            ],
            max_tokens=50
        )

        print("[SUCCESS]")
        print(f"Response: {response.choices[0].message.content}")
        print(f"Model used: {response.model}")
        print(f"Tokens: {response.usage.total_tokens if response.usage else 'N/A'}")

    except Exception as e:
        print(f"[ERROR] {e}")
        print(f"Error type: {type(e).__name__}")

        # Try to get more details
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
            print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")

if __name__ == "__main__":
    asyncio.run(test_quatarly())
