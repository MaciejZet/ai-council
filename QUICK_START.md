# 🚀 Quick Start - AI Council

## Szybkie uruchomienie w 3 krokach:

### 1️⃣ Zainstaluj zależności
```bash
pip install -r requirements.txt
```

### 2️⃣ Dodaj API keys
Edytuj plik `.env` i zamień `dummy-key` na prawdziwe klucze:
```env
OPENAI_API_KEY=sk-twoj-prawdziwy-klucz
GEMINI_API_KEY=twoj-prawdziwy-klucz
# ... itd
```

### 3️⃣ Uruchom aplikację
```bash
python start.py
```

Gotowe! Otwórz: **http://localhost:8000**

---

## 🔑 Gdzie zdobyć API keys:

| Provider | Link | Koszt |
|----------|------|-------|
| OpenAI | https://platform.openai.com/api-keys | Płatne |
| Google Gemini | https://aistudio.google.com/apikey | Darmowe (limit) |
| Grok (xAI) | https://console.x.ai/ | Płatne |
| DeepSeek | https://platform.deepseek.com/ | Bardzo tanie |
| OpenRouter | https://openrouter.ai/keys | Pay-as-you-go |

**Minimum**: Potrzebujesz przynajmniej 1 klucz API (np. Gemini - darmowy).

---

## 🧪 Test bez API keys:

Możesz przetestować interfejs bez prawdziwych kluczy:
```bash
python start.py
```

Aplikacja się uruchomi, ale deliberacje nie będą działać bez prawdziwych API keys.

---

## 📖 Więcej informacji:

- **NAPRAWIONE.md** - Co zostało naprawione
- **README.md** - Pełna dokumentacja
- **IMPROVEMENTS.md** - Szczegóły techniczne
