import sys
import os
import asyncio
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from llm_providers import get_provider, AVAILABLE_PROVIDERS

async def verify_providers():
    load_dotenv()
    print("Verifying LLM Providers...")
    
    # Check OpenAI
    try:
        provider = get_provider("openai")
        print(f"✅ OpenAI Provider Name: {provider.get_name()}")
        models = await provider.get_available_models()
        print(f"   Supported models fetch: {len(models)} (Expected 0 for base impl)")
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")

    # Check OpenRouter
    try:
        provider = get_provider("openrouter")
        print(f"✅ OpenRouter Default Name: {provider.get_name()}")
        print("   Fetching OpenRouter models...")
        models = await provider.get_available_models()
        if len(models) > 0:
             print(f"✅ OpenRouter Models Fetched: {len(models)}")
             print(f"   Sample: {models[:3]}")
        else:
             print("❌ OpenRouter Models Fetch Failed (Empty List)")
    except Exception as e:
        print(f"❌ OpenRouter Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_providers())
