# API Keys Management Guide

## Overview

AI Council now supports storing API keys in **localStorage** instead of `.env` files. This provides:
- ✅ No sensitive data in files
- ✅ Easy key management through UI
- ✅ Per-browser configuration
- ✅ Export/Import functionality
- ✅ Fallback to .env for server-side usage

## How It Works

### 1. Client-Side (Browser)
- API keys stored in `localStorage`
- Encoded as base64 JSON
- Sent with each request in `X-API-Keys` header
- Never exposed in URLs or logs

### 2. Server-Side (Backend)
- Reads keys from `X-API-Keys` header
- Falls back to `.env` if header not present
- Validates and uses keys for API calls

## Usage

### Open API Keys Settings

Click the **Settings** button (⚙️) in the sidebar, then click **"Konfiguruj"** in the API Keys section.

### Configure Keys

1. **OpenAI**
   - API Key: `sk-...`
   - Base URL: (optional) Custom endpoint

2. **Grok (xAI)**
   - API Key: `xai-...`
   - Base URL: (optional)

3. **Google Gemini**
   - API Key: `AIza...`

4. **DeepSeek**
   - API Key: `sk-...`
   - Base URL: (optional)

5. **Perplexity**
   - API Key: `pplx-...`
   - Base URL: (optional)

6. **OpenRouter**
   - API Key: `sk-or-...`
   - Base URL: (optional)

7. **Custom API** (LM Studio, Ollama, etc.)
   - API Key: `dummy` (for local APIs)
   - Base URL: `http://localhost:1234/v1`
   - Model: `llama-2-7b`

### Save Keys

Click **"💾 Save Keys"** to store in localStorage.

### Export/Import

- **Export**: Download keys as JSON file (for backup)
- **Import**: Load keys from JSON file

### Clear Keys

Click **"🗑️ Clear All"** to remove all stored keys.

## Security

### Client-Side Security
- Keys stored in browser's localStorage
- Base64 encoded (not encrypted)
- Only accessible from same origin
- Cleared when browser data is cleared

### Server-Side Security
- Keys transmitted via HTTPS (in production)
- Never logged or stored on server
- Used only for API calls
- Validated before use

### Best Practices

1. **Use HTTPS** in production
2. **Don't share** exported JSON files
3. **Clear keys** on shared computers
4. **Use .env** for server-side deployments
5. **Rotate keys** regularly

## Priority Order

When making API calls, keys are used in this order:

1. **localStorage** (from browser)
2. **.env file** (fallback)
3. **Error** if neither available

## Example: Using Keys in Code

### Frontend (JavaScript)

```javascript
// Keys are automatically added to requests
const response = await fetch('/api/deliberate', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-API-Keys': apiKeyManager.encodeKeys()
    },
    body: JSON.stringify({
        query: "What is AI?",
        provider: "openai",
        model: "gpt-4o"
    })
});
```

### Backend (Python)

```python
from fastapi import Depends
from src.utils.api_keys import APIKeyManager, get_api_keys_header

@app.post("/api/deliberate")
async def deliberate(
    request: dict,
    api_keys: str = Depends(get_api_keys_header)
):
    # Create provider with keys from localStorage or .env
    provider = APIKeyManager.create_provider_with_keys(
        provider_name=request["provider"],
        model=request["model"],
        encoded_keys=api_keys
    )
    
    # Use provider
    response = await provider.generate(...)
    return response
```

## Troubleshooting

### Keys Not Working

1. Check if keys are saved: Open API Keys modal
2. Verify key format: Should start with correct prefix (sk-, xai-, etc.)
3. Check browser console for errors
4. Try clearing and re-entering keys

### Keys Lost After Browser Restart

- localStorage persists across sessions
- If lost, check if browser is in private/incognito mode
- Import from backup JSON if available

### Can't Access Settings

- Click ⚙️ icon in sidebar
- Or navigate to Settings page
- Refresh page if modal doesn't appear

## Migration from .env

### Keep Both (Recommended)

```env
# .env - Server-side fallback
OPENAI_API_KEY=sk-...
GROK_API_KEY=xai-...
```

Browser localStorage takes priority, .env is fallback.

### Move to localStorage Only

1. Open API Keys modal
2. Copy keys from `.env`
3. Paste into modal
4. Save keys
5. Remove from `.env` (optional)

## API Reference

### JavaScript API

```javascript
// Get manager instance
const manager = apiKeyManager;

// Set key
manager.setKey('openai', 'sk-...');

// Get key
const key = manager.getKey('openai');

// Check if key exists
if (manager.hasKey('openai')) {
    // Use OpenAI
}

// Get configured providers
const providers = manager.getConfiguredProviders();
// ['openai', 'grok', 'gemini']

// Encode for API request
const encoded = manager.encodeKeys();

// Export/Import
const json = manager.exportKeys();
manager.importKeys(json);

// Clear all
manager.clearKeys();
```

### Python API

```python
from src.utils.api_keys import APIKeyManager

# Get API key
key = APIKeyManager.get_api_key('openai', encoded_keys)

# Get base URL
url = APIKeyManager.get_base_url('openai', encoded_keys)

# Create provider with keys
provider = APIKeyManager.create_provider_with_keys(
    'openai',
    'gpt-4o',
    encoded_keys
)
```

## FAQ

**Q: Are keys encrypted?**
A: Keys are base64 encoded but not encrypted. Use HTTPS in production.

**Q: Can I use both localStorage and .env?**
A: Yes! localStorage takes priority, .env is fallback.

**Q: What happens if I clear browser data?**
A: Keys are lost. Export backup JSON first.

**Q: Can I share keys between browsers?**
A: Export from one browser, import to another.

**Q: Are keys sent to your servers?**
A: Only in API request headers (HTTPS). Never stored on server.

**Q: Can I use different keys per project?**
A: Yes, each browser/origin has separate localStorage.

## Support

For issues:
1. Check browser console (F12)
2. Verify keys in modal
3. Test with .env fallback
4. Check network tab for API calls
