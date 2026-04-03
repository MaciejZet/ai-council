# 🗺️ MAPA PROJEKTU - AI Council

```
┌─────────────────────────────────────────────────────────────┐
│                    🚀 START TUTAJ                           │
│                                                             │
│  1. python start.py                                         │
│  2. Otwórz: http://localhost:8000                          │
│  3. Dodaj API keys do .env                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  📁 STRUKTURA PROJEKTU                      │
└─────────────────────────────────────────────────────────────┘

AI Council/
│
├── 🚀 URUCHOMIENIE
│   ├── start.py              ← Smart starter (UŻYJ TEGO!)
│   ├── start.bat             ← Windows: kliknij dwukrotnie
│   ├── start.sh              ← Linux/Mac: ./start.sh
│   ├── main.py               ← Backend FastAPI
│   └── check_setup.py        ← Diagnostyka
│
├── ⚙️ KONFIGURACJA
│   ├── .env                  ← API KEYS (EDYTUJ!)
│   ├── .env.example          ← Przykład
│   ├── requirements.txt      ← Zależności pip
│   └── pyproject.toml        ← Konfiguracja projektu
│
├── 📚 DOKUMENTACJA
│   ├── QUICK_START.md        ← START (3 kroki)
│   ├── PODSUMOWANIE.md       ← Co zostało zrobione
│   ├── NAPRAWIONE.md         ← Lista napraw
│   ├── TROUBLESHOOTING.md    ← Rozwiązywanie problemów
│   ├── STATUS.md             ← Status projektu
│   └── README.md             ← Pełna dokumentacja
│
├── 🧪 TESTY
│   ├── test_integration.py   ← Testy API
│   └── tests/                ← Unit testy
│
├── 💻 KOD ŹRÓDŁOWY
│   └── src/
│       ├── agents/           ← System agentów
│       ├── council/          ← Orkiestracja
│       ├── knowledge/        ← Knowledge base (RAG)
│       ├── plugins/          ← Wtyczki
│       ├── utils/            ← Narzędzia
│       └── llm_providers.py  ← Providery AI
│
├── 🎨 FRONTEND
│   └── static/
│       ├── index.html        ← Główny UI
│       ├── css/              ← Style
│       └── js/               ← JavaScript
│
└── 📊 DANE
    └── logs/                 ← Logi aplikacji

┌─────────────────────────────────────────────────────────────┐
│                  🔄 WORKFLOW UŻYCIA                         │
└─────────────────────────────────────────────────────────────┘

1. INSTALACJA
   │
   ├─→ pip install -r requirements.txt
   └─→ Edytuj .env (dodaj API keys)

2. SPRAWDZENIE
   │
   └─→ python check_setup.py
       │
       ├─→ [OK] Wszystko działa → Krok 3
       └─→ [ERROR] Problem → TROUBLESHOOTING.md

3. URUCHOMIENIE
   │
   └─→ python start.py
       │
       └─→ Serwer na http://localhost:8000

4. TESTOWANIE
   │
   ├─→ Otwórz przeglądarkę: http://localhost:8000
   ├─→ Sprawdź health: curl http://localhost:8000/health
   └─→ Test integracyjny: python test_integration.py

5. UŻYTKOWANIE
   │
   ├─→ Dashboard: Zadaj pytanie
   ├─→ Agents: Zarządzaj agentami
   ├─→ SEO Generator: Generuj artykuły
   └─→ Plugins: Włącz wtyczki

┌─────────────────────────────────────────────────────────────┐
│                  🎯 GŁÓWNE ENDPOINTY                        │
└─────────────────────────────────────────────────────────────┘

Frontend:
  http://localhost:8000                    ← Główny UI

API - Monitoring:
  GET  /health                             ← Status systemu
  GET  /metrics                            ← Metryki

API - Agenci:
  GET  /api/agents                         ← Lista agentów
  POST /api/agents/{name}/toggle           ← Włącz/wyłącz
  GET  /api/agents/custom                  ← Custom agenci

API - Deliberacja:
  POST /api/deliberate                     ← Narada (JSON)
  GET  /api/deliberate/stream              ← Streaming
  GET  /api/debate/stream                  ← Debata

API - Knowledge Base:
  POST /api/ingest                         ← Import PDF
  GET  /api/stats                          ← Statystyki

┌─────────────────────────────────────────────────────────────┐
│                  🔑 API KEYS (WYMAGANE!)                    │
└─────────────────────────────────────────────────────────────┘

Minimum (wybierz 1):
  ✓ GEMINI_API_KEY          → Darmowy! (aistudio.google.com)
  ✓ OPENAI_API_KEY          → Płatny (platform.openai.com)
  ✓ DEEPSEEK_API_KEY        → Bardzo tani (platform.deepseek.com)

Opcjonalne:
  ○ GROK_API_KEY            → xAI (console.x.ai)
  ○ PERPLEXITY_API_KEY      → Perplexity (perplexity.ai)
  ○ OPENROUTER_API_KEY      → OpenRouter (openrouter.ai)

Dla funkcji dodatkowych:
  ○ PINECONE_API_KEY        → Knowledge base (pinecone.io)
  ○ TAVILY_API_KEY          → Web search (tavily.com)

┌─────────────────────────────────────────────────────────────┐
│                  🛠️ NARZĘDZIA DIAGNOSTYCZNE                 │
└─────────────────────────────────────────────────────────────┘

check_setup.py
  ├─→ Sprawdza Python (3.10+)
  ├─→ Weryfikuje pakiety
  ├─→ Sprawdza .env
  ├─→ Weryfikuje katalogi
  └─→ Testuje frontend

start.py
  ├─→ Uruchamia check_setup.py
  ├─→ Pokazuje błędy
  └─→ Startuje serwer

test_integration.py
  ├─→ Testuje /health
  ├─→ Testuje /api/agents
  ├─→ Testuje frontend
  └─→ Testuje /api/deliberate

┌─────────────────────────────────────────────────────────────┐
│                  ❓ PROBLEMY?                               │
└─────────────────────────────────────────────────────────────┘

Problem                          Rozwiązanie
────────────────────────────────────────────────────────────
Brak modułu X                 → pip install -r requirements.txt
Port 8000 zajęty              → TROUBLESHOOTING.md
API key invalid               → Sprawdź .env
Serwer nie odpowiada          → python start.py
Frontend nie działa           → Sprawdź static/index.html
Wolne odpowiedzi              → Włącz Redis cache
Wysokie koszty                → Użyj DeepSeek/Gemini Flash

Więcej: TROUBLESHOOTING.md

┌─────────────────────────────────────────────────────────────┐
│                  📊 STATUS KOMPONENTÓW                      │
└─────────────────────────────────────────────────────────────┘

✅ Backend FastAPI           → Działa (port 8000)
✅ Frontend HTML/JS          → Działa
✅ 5 Core Agents             → Działa
✅ Specialists               → Działa
✅ Health checks             → Działa
✅ Metrics                   → Działa
✅ Diagnostyka               → Działa
⚠️  API keys                 → DODAJ DO .env
⚠️  Redis cache              → Opcjonalny
⚠️  Pinecone KB              → Opcjonalny

┌─────────────────────────────────────────────────────────────┐
│                  🎓 DOKUMENTACJA - GDZIE SZUKAĆ?            │
└─────────────────────────────────────────────────────────────┘

Pytanie                          Dokument
────────────────────────────────────────────────────────────
Jak zacząć?                   → QUICK_START.md
Co zostało naprawione?        → NAPRAWIONE.md
Mam problem                   → TROUBLESHOOTING.md
Jaki jest status?             → STATUS.md
Co zostało zrobione?          → PODSUMOWANIE.md
Pełna dokumentacja            → README.md
Struktura projektu            → MAPA.md (ten plik)

┌─────────────────────────────────────────────────────────────┐
│                  💡 SZYBKIE KOMENDY                         │
└─────────────────────────────────────────────────────────────┘

# Sprawdź setup
python check_setup.py

# Uruchom aplikację
python start.py

# Test (gdy serwer działa)
python test_integration.py

# Health check
curl http://localhost:8000/health

# Lista agentów
curl http://localhost:8000/api/agents

# Metrics
curl http://localhost:8000/metrics

# Logi
tail -f logs/ai_council_main_*.log

┌─────────────────────────────────────────────────────────────┐
│                  🚀 NASTĘPNE KROKI                          │
└─────────────────────────────────────────────────────────────┘

1. ✅ Zainstaluj zależności
   pip install -r requirements.txt

2. ✅ Dodaj API keys do .env
   Edytuj .env, zamień dummy-key

3. ✅ Uruchom aplikację
   python start.py

4. ✅ Otwórz w przeglądarce
   http://localhost:8000

5. ✅ Zadaj pierwsze pytanie
   Dashboard → Wpisz pytanie → Wyślij

6. ⚠️  Opcjonalnie: Włącz Redis
   redis-server

7. ⚠️  Opcjonalnie: Skonfiguruj Pinecone
   Dodaj klucze do .env

Powodzenia! 🎉
```
