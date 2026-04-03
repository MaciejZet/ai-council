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

---

## API: narada, sesje, streaming (dla integracji)

### `POST /api/deliberate` — dodatkowe pola JSON

| Pole | Typ | Opis |
|------|-----|------|
| `routing_mode` | `"auto"` \| `"full"` | `auto` = heurystyczny podzbiór agentów (niższy koszt); `full` = zawsze 4 agenci + syntezator |
| `persist_session` | bool | `true` = zapis wyniku narady po stronie serwera (`data/sessions/`) |
| `session_id` | string (opcjonalnie) | Kontynuacja wątku: ten sam ID co w poprzedniej odpowiedzi |

Odpowiedź może zawierać: `session_id` (UUID), `routing_intent` (np. `technical`).

### Sesje (serwer)

- `GET /api/sessions` — lista metadanych sesji
- `GET /api/sessions/{id}` — pełny JSON (w tym `chat_turns`)
- `GET /api/sessions/{id}/export` — eksport (markdown/html/pdf)

### `POST /api/deliberate/stream` — body JSON

Te same pola co wyżej (`routing_mode`, `persist_session`, `session_id`). Zdarzenia SSE m.in.: `routing` (intent, reason), `sources`, `delta`, …

### Debata (`GET /api/debate/stream`)

Zdarzenie `debate_analysis`: `consensus_points`, `disagreement_points`, `disagreement_map` (przed finalną syntezą).

### SEO (`POST /api/seo/generate`)

W odpowiedzi przy sukcesie: `full_page_html` — gotowa strona HTML (ToC + treść + JSON-LD).

### UI (dashboard)

Przy polu zapytania: **Serwer** (persist), **Pełna rada** (routing full). Badge w nagłówku pokazuje wykryty routing po streamie. `session_id` serwera jest trzymany w `localStorage` pod kluczem `ai_council_server_session_id` (Reset „Nowa sesja” czyści).
