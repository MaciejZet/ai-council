#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Quatarly API with streaming
"""
import asyncio
import sys
from openai import AsyncOpenAI

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

async def test_quatarly_stream():
    # Konfiguracja
    api_key = "qua-1100eeebe8ff00e4ae0fd5f5262a6f07"
    base_url = "https://api.quatarly.cloud/v1"
    model = "claude-haiku-4-5-20251001"

    print(f"Testing Quatarly API (STREAMING):")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {api_key[:20]}...")
    print()

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )

    try:
        print("Sending streaming request...")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Say hello in 3 words"}
            ],
            stream=True
        )

        print("[STREAMING]")
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end='', flush=True)

        print("\n[SUCCESS]")

    except Exception as e:
        print(f"[ERROR] {e}")
        print(f"Error type: {type(e).__name__}")

        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_quatarly_stream())
