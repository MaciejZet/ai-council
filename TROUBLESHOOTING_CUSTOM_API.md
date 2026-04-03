# Troubleshooting Custom API Provider

## Problem: Błąd 404

### Możliwe przyczyny:

1. **Niepoprawny Base URL**
   - ❌ `https://api.quatarly.cloud/` (brak `/v1`)
   - ✅ `https://api.quatarly.cloud/v1`
   
   Większość API kompatybilnych z OpenAI wymaga `/v1` na końcu URL.

2. **Niepoprawna nazwa modelu**
   - Sprawdź, czy nazwa modelu jest dokładnie taka, jak w dokumentacji API
   - Przykład: `claude-haiku-4-5-20251001` vs `claude-haiku-4.5-20251001`

3. **Niepoprawny klucz API**
   - Sprawdź, czy klucz jest poprawnie skopiowany
   - Sprawdź, czy klucz ma odpowiednie uprawnienia

## Jak debugować:

### 1. Sprawdź logi backendu
Uruchom aplikację i sprawdź terminal/konsole:
```
CustomAPIProvider - Base URL: https://api.quatarly.cloud/v1
CustomAPIProvider - Model: claude-haiku-4-5-20251001
CustomAPIProvider - API Key: qua-1100ee...
```

### 2. Sprawdź logi frontendu
Otwórz konsolę przeglądarki (F12):
```
Saved custom: ***
Saved custom_base_url: ***
Saved custom_model: ***
Custom provider selected, model: claude-haiku-4-5-20251001
```

### 3. Testuj API ręcznie
Użyj curl, aby przetestować API:
```bash
curl https://api.quatarly.cloud/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer qua-1100eeebe8ff00e4ae0fd5f5262a6f07" \
  -d '{
    "model": "claude-haiku-4-5-20251001",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

## Poprawna konfiguracja dla Quatarly:

1. **API Key**: `qua-1100eeebe8ff00e4ae0fd5f5262a6f07`
2. **Base URL**: `https://api.quatarly.cloud/v1` (dodaj `/v1`)
3. **Model name**: `claude-haiku-4-5-20251001`

## Inne popularne API:

### LM Studio
- Base URL: `http://localhost:1234/v1`
- API Key: `dummy` lub puste
- Model: nazwa modelu załadowanego w LM Studio

### Ollama (OpenAI compatibility)
- Base URL: `http://localhost:11434/v1`
- API Key: `dummy` lub puste
- Model: `llama3.1:8b` (lub inny zainstalowany)

### OpenRouter
- Base URL: `https://openrouter.ai/api/v1`
- API Key: Twój klucz OpenRouter
- Model: `anthropic/claude-3.5-sonnet`

## Sprawdź dokumentację API

Każde API może mieć inne wymagania:
- Sprawdź dokumentację providera
- Sprawdź format URL (czy wymaga `/v1`)
- Sprawdź format nazwy modelu
- Sprawdź format klucza API (Bearer token, API key, etc.)
