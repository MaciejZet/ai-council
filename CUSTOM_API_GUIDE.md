# Custom API Configuration Guide

## Overview

AI Council now supports custom OpenAI-compatible API endpoints! This allows you to use:
- **LM Studio** - Run models locally
- **Ollama** - Local model serving
- **vLLM** - High-performance inference
- **LocalAI** - Self-hosted AI
- **Any OpenAI-compatible API**

## Quick Setup

### 1. LM Studio

```env
# .env
CUSTOM_BASE_URL=http://localhost:1234/v1
CUSTOM_MODEL=local-model
CUSTOM_API_KEY=dummy
DEFAULT_LLM_PROVIDER=custom
```

### 2. Ollama (with OpenAI compatibility)

```bash
# Start Ollama with OpenAI API compatibility
ollama serve
```

```env
# .env
CUSTOM_BASE_URL=http://localhost:11434/v1
CUSTOM_MODEL=llama2
CUSTOM_API_KEY=dummy
DEFAULT_LLM_PROVIDER=custom
```

### 3. vLLM

```env
# .env
CUSTOM_BASE_URL=http://your-vllm-server:8000/v1
CUSTOM_MODEL=meta-llama/Llama-2-7b-chat-hf
CUSTOM_API_KEY=your_api_key
DEFAULT_LLM_PROVIDER=custom
```

### 4. Custom OpenAI-Compatible API

```env
# .env
CUSTOM_BASE_URL=https://your-api-endpoint.com/v1
CUSTOM_MODEL=your-model-name
CUSTOM_API_KEY=your_api_key
DEFAULT_LLM_PROVIDER=custom
```

## Configuration Options

### Environment Variables

All providers now support custom base URLs and API keys:

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1  # Optional

# Grok
GROK_API_KEY=xai-...
GROK_BASE_URL=https://api.x.ai/v1  # Optional

# DeepSeek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com  # Optional

# Perplexity
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_BASE_URL=https://api.perplexity.ai  # Optional

# OpenRouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1  # Optional

# Custom API
CUSTOM_API_KEY=your_key
CUSTOM_BASE_URL=http://localhost:1234/v1
CUSTOM_MODEL=local-model
```

## Usage Examples

### Using Custom Provider in Code

```python
from src.custom_api_provider import CustomAPIProvider

# Initialize with custom endpoint
provider = CustomAPIProvider(
    model="llama-2-7b",
    base_url="http://localhost:1234/v1",
    api_key="dummy"
)

# Use like any other provider
response = await provider.generate(
    system_prompt="You are a helpful assistant",
    user_prompt="What is AI?",
    temperature=0.7
)

print(response.content)
```

### Using via get_provider()

```python
from src.llm_providers import get_provider

# Will use CUSTOM_BASE_URL and CUSTOM_MODEL from .env
provider = get_provider("custom")

response = await provider.generate(
    system_prompt="You are a helpful assistant",
    user_prompt="Explain quantum computing"
)
```

### Override Base URL Programmatically

```python
from src.llm_providers import OpenAIProvider

# Use OpenAI-compatible endpoint (e.g., Azure OpenAI)
provider = OpenAIProvider(
    model="gpt-4",
    base_url="https://your-azure-endpoint.openai.azure.com/",
    api_key="your-azure-key"
)
```

## Testing Your Setup

### 1. Test Connection

```python
import asyncio
from src.custom_api_provider import CustomAPIProvider

async def test_custom_api():
    provider = CustomAPIProvider(
        base_url="http://localhost:1234/v1",
        model="local-model"
    )
    
    try:
        response = await provider.generate(
            system_prompt="You are a test assistant",
            user_prompt="Say hello!",
            temperature=0.7
        )
        print(f"✅ Success: {response.content}")
        print(f"Tokens: {response.total_tokens}")
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test_custom_api())
```

### 2. Test via API

```bash
# Start the server
python main.py

# Test with custom provider
curl -X POST http://localhost:8000/api/deliberate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "provider": "custom",
    "model": "local-model"
  }'
```

## Common Use Cases

### 1. Privacy-First Setup (All Local)

```env
# Run everything locally - no external API calls
CUSTOM_BASE_URL=http://localhost:1234/v1
CUSTOM_MODEL=mistral-7b
DEFAULT_LLM_PROVIDER=custom

# Disable external providers
OPENAI_API_KEY=
GROK_API_KEY=
```

### 2. Cost Optimization (Mix Local + Cloud)

```env
# Use local models for simple queries
CUSTOM_BASE_URL=http://localhost:1234/v1
CUSTOM_MODEL=llama-2-7b

# Use cloud for complex queries
OPENAI_API_KEY=sk-...
DEFAULT_LLM_PROVIDER=custom  # Start with local
```

### 3. Enterprise Setup (Self-Hosted)

```env
# Internal vLLM cluster
CUSTOM_BASE_URL=https://internal-llm.company.com/v1
CUSTOM_MODEL=company-fine-tuned-model
CUSTOM_API_KEY=internal-token
DEFAULT_LLM_PROVIDER=custom
```

## Troubleshooting

### Connection Refused

```bash
# Check if server is running
curl http://localhost:1234/v1/models

# For LM Studio: Make sure "Start Server" is enabled
# For Ollama: Run `ollama serve`
```

### Model Not Found

```bash
# List available models
curl http://localhost:1234/v1/models

# Update CUSTOM_MODEL to match available model
```

### Authentication Failed

```bash
# For local APIs, use "dummy" or empty string
CUSTOM_API_KEY=dummy

# For remote APIs, check your API key
CUSTOM_API_KEY=your_actual_key
```

### Slow Responses

```bash
# Check if model is loaded
# For LM Studio: Preload model in UI
# For Ollama: Run `ollama pull <model>` first

# Adjust max_tokens for faster responses
# Smaller values = faster generation
```

## Performance Tips

1. **Preload Models**: Load models before first request
2. **Use Smaller Models**: For simple tasks, use 7B models instead of 70B
3. **Adjust Temperature**: Lower temperature (0.3-0.5) for faster, more focused responses
4. **Set max_tokens**: Limit response length for faster generation
5. **Use GPU**: Ensure your local setup uses GPU acceleration

## Security Notes

- Local APIs typically don't need real API keys (use "dummy")
- For remote custom APIs, store keys in `.env` (never commit!)
- Use HTTPS for production custom endpoints
- Implement rate limiting for public-facing custom APIs

## Next Steps

- See `examples/integration_example.py` for more code examples
- Check `IMPROVEMENTS.md` for caching and monitoring features
- Read `QUICKSTART.md` for general setup guide
