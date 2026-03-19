import pytest
import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_openrouter_models():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_key_here":
        print("Skipping test: OPENROUTER_API_KEY not set.")
        return

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )
    
    try:
        print("Fetching models from OpenRouter...")
        models_page = await client.models.list()
        # models_page is typically a sync or async iterator or list depending on version.
        # AsyncOpenAI return object is usually usually not async iterator for .list()? 
        # Actually in v1+, usage is `await client.models.list()`. The result has .data.
        
        models = models_page.data
        print(f"Successfully fetched {len(models)} models.")
        if len(models) > 0:
            print("First 5 models:")
            for m in models[:5]:
                print(f"- {m.id}")
                
    except Exception as e:
        print(f"Error fetching models: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter_models())
