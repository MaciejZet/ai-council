import asyncio
import json
import httpx

async def verify_api():
    print("Verifying /api/providers endpoint...")
    try:
        # Assuming server is running on localhost:8501, which it likely is via run.sh
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8501/api/providers")
            if response.status_code == 200:
                data = response.json()
                print("✅ API Response OK")
                
                models = data.get("models", {})
                
                # Check Perplexity
                if "perplexity" in models and len(models["perplexity"]) > 0:
                    print(f"✅ Perplexity Models: {models['perplexity']}")
                else:
                    print("❌ Perplexity Models Missing!")
                
                # Check OpenRouter
                if "openrouter" in models and len(models["openrouter"]) > 0:
                    print(f"✅ OpenRouter Models Count: {len(models['openrouter'])}")
                    print(f"   First 3: {models['openrouter'][:3]}")
                else:
                    print("❌ OpenRouter Models Missing!")
                    
                # Check Grok duplicates in keys (JSON handles unique keys, so just check present)
                if "grok" in models:
                    print(f"✅ Grok Present: {models['grok']}")
                
            else:
                print(f"❌ API Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection Error (Server might be restarting): {e}")

if __name__ == "__main__":
    asyncio.run(verify_api())
