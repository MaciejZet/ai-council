# AI Council 🏛️

**Zaawansowany system wieloagentowej rady AI z bazą wiedzy, streamingiem i pluginami**

AI Council to inteligentny system konsultingowy wykorzystujący zespół specjalizowanych agentów AI do analizy problemów z różnych perspektyw. System łączy wiedzę z Twojej biblioteki biznesowej z nowoczesnymi modelami AI (GPT-5, Grok, Gemini).

## 🚀 Szybki start

```bash
# 1. Sklonuj i przejdź do katalogu
cd ai-council

# 2. Uruchom skrypt instalacyjny
./run.sh
```

Aplikacja otworzy się na: **http://localhost:8501**

### Wymagania wstępne
- Python 3.12+
- Klucze API dla wybranych providerów

## ✨ Kluczowe możliwości

### 🏛️ Rada Ekspertów AI
- **5 agentów podstawowych**:
  - 🎯 **Strateg** - wizja długoterminowa, cele biznesowe
  - 📊 **Analityk** - analiza za/przeciw, ocena ryzyka
  - 🔧 **Praktyk** - wykonalność, plan implementacji
  - 🎓 **Ekspert** - głęboka wiedza domenowa z Twojej bazy
  - 🔮 **Syntezator** - ostateczna rekomendacja łącząca wszystkie perspektywy

- **Specjaliści branżowi**: SEO, LinkedIn, Social Media, Branding, Blog Content
- **Dynamiczne włączanie/wyłączanie** agentów w czasie rzeczywistym

### 📚 Inteligentna baza wiedzy
- **RAG (Retrieval-Augmented Generation)** - agenci czerpią kontekst z Twoich dokumentów
- **Automatyczna kategoryzacja** książek (marketing, strategia, biznes, produktywność)
- **Import PDF** - cała Twoja biblioteka biznesowa (48 Praw Władzy, Atomowe nawyki, itp.)
- **Pinecone vector database** - semantyczne wyszukiwanie

### ⚡ Zaawansowane funkcje
- **Multi-provider AI**: OpenAI (GPT-4o/5), Grok (xAI), Gemini (Google)
- **Real-time streaming** - odpowiedzi generowane na żywo token po tokenie
- **Tryb debaty** - wielorundowe dyskusje między agentami
- **Tryb chat** - kontekst rozmowy utrzymywany między zapytaniami
- **Załączniki** - analiza plików PDF/txt/docx/md
- **Śledzenie kosztów** - pełna kalkulacja tokenów i kosztów

### 🛠️ Plugin system
- 🔍 **Web search** (Tavily, DuckDuckGo)
- 📄 **URL analyzer** - analiza i podsumowanie stron internetowych
- 🌐 **Wikipedia** - wyszukiwanie i podsumowanie artykułów
- 🌤️ **Weather** - prognoza pogody
- 📈 **Stocks** - dane giełdowe
- 🧮 **Calculator** - kalkulator matematyczny
- 🛠️ **Utilities** - konwertery, hash, random, narzędzia tekstowe

### 🎨 Custom Agenci
- **Własne agenty AI** - twórz specjalistów z własnych promptów
- **Template system** - gotowe szablony dla różnych ról
- **Tool integration** - integracja z pluginami
- **Test mode** - testuj agentów przed zapisaniem

## 📖 Przykładowe zastosowania

**Dla przedsiębiorców:**
- Analiza strategii rozwoju firmy
- Ocena ryzyka nowych inwestycji
- Optymalizacja procesów biznesowych
- Content marketing i social media strategy

**Dla specjalistów:**
- Analiza technicznych rozwiązań
- Badania rynku i konkurencji
- Strategie marketingowe
- Optymalizacja SEO i content

## 🏗️ Architektura

### Backend (FastAPI)
```
├── main.py                 # REST API + WebSocket streaming
├── src/
│   ├── agents/            # System agentów
│   │   ├── base.py        # Klasa bazowa agentów
│   │   ├── core_agents.py # 5 głównych agentów
│   │   ├── specialists.py # Specjaliści branżowi
│   │   ├── custom_agents.py # Własne agenty
│   │   └── agent_storage.py # Zarządzanie custom agentami
│   │
│   ├── council/           # Logika rady
│   │   ├── orchestrator.py # Koordynacja deliberacji
│   │   └── debate.py      # System debat
│   │
│   ├── knowledge/         # Baza wiedzy
│   │   ├── ingest.py      # PDF → wektory
│   │   └── retriever.py   # RAG retrieval
│   │
│   ├── llm_providers.py   # Integracja z AI
│   ├── plugins/           # Plugin system
│   └── prompt_templates.py # Szablony promptów
```

### Frontend
```
├── static/
│   ├── index.html         # Główny UI
│   ├── js/app.js          # JavaScript aplikacja
│   └── css/styles.css     # Styling
└── app.py                 # Legacy Streamlit UI
```

## 🔧 Konfiguracja API

Utwórz plik `.env` w katalogu głównym:

```env
# Wymagane dla bazy wiedzy
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=your_index_name

# Wybierz przynajmniej jednego providera AI
OPENAI_API_KEY=your_openai_key
GROK_API_KEY=your_grok_key
GEMINI_API_KEY=your_gemini_key

# Opcjonalne - dla pluginów
TAVILY_API_KEY=your_tavily_key
WEATHER_API_KEY=your_weather_key
```

## 📚 Zarządzanie bazą wiedzy

### Import pojedynczego PDF
```bash
python -c "from src.knowledge.ingest import ingest_pdf; ingest_pdf('books_pdf/atomowe_nawyki.pdf')"
```

### Import całego katalogu
```bash
python -c "from src.knowledge.ingest import ingest_directory; ingest_directory('books_pdf/')"
```

### Sprawdź statystyki
```bash
python -c "from src.knowledge.ingest import get_ingestion_stats; print(get_ingestion_stats())"
```

## 🎯 Tworzenie własnych agentów

```python
from src.agents.specialists import create_custom_specialist

# Przykład: Specjalista ds. Email Marketing
email_expert = create_custom_specialist(
    name="Email Marketing Expert",
    specialty="Email Marketing",
    emoji="📧",
    expertise_areas=["Kampanie email", "Automatyzacja", "Segmentacja"],
    focus_points=["Open rate", "CTR", "Deliverability"]
)
```

### Zaawansowane custom agenty
```python
from src.agents.custom_agents import create_custom_agent, CustomAgentConfig

config = CustomAgentConfig(
    name="Data Analyst",
    emoji="📊",
    role="Data Science Expert",
    persona="Specjalizuję się w analizie danych i machine learning",
    system_prompt="Jesteś ekspertem data science...",
    tools=["calculator", "web_search", "knowledge_base"],
    context_limit=10000
)

agent_id = create_custom_agent(config)
```

## 🔌 API Endpoints

### Rada AI
- `POST /api/deliberate` - Analiza przez radę agentów
- `GET /api/deliberate/stream` - Streaming deliberacji
- `GET /api/debate/stream` - Wielorundowa debata agentów

### Zarządzanie agentami
- `GET /api/agents` - Lista wszystkich agentów
- `POST /api/agents/{name}/toggle` - Włącz/wyłącz agenta
- `GET/POST/PUT/DELETE /api/agents/custom` - Zarządzanie custom agentami

### Baza wiedzy
- `POST /api/ingest` - Import PDF do bazy
- `GET /api/stats` - Statystyki bazy wiedzy

### Pluginy
- `GET /api/plugins` - Lista dostępnych pluginów
- `POST /api/plugins/web-search` - Wyszukiwanie internetowe
- `POST /api/plugins/analyze-url` - Analiza URL
- `POST /api/plugins/weather` - Pogoda
- `POST /api/plugins/stocks` - Dane giełdowe

## 🎨 UI Features

- **Dark theme** - nowoczesny, minimalistyczny design
- **Real-time updates** - odpowiedzi pojawiają się na żywo
- **Responsive layout** - działa na desktop i mobile
- **Agent management** - włączaj/wyłączaj agentów w sidebar
- **Cost tracking** - monitoruj koszty API w czasie rzeczywistym
- **Export options** - pobieraj wyniki jako Markdown

## 🚦 Wymagania systemowe

- **Python**: 3.12+
- **RAM**: 8GB+ (dla dużych baz wiedzy)
- **Dysk**: 10GB+ (dla wektorowej bazy danych)

### Zależności
```
fastapi>=0.109.0         # REST API
uvicorn>=0.27.0          # ASGI server
streamlit>=1.30.0        # Legacy UI
openai>=1.0.0           # OpenAI integration
pinecone>=8.0.0         # Vector database
pypdf>=3.0.0            # PDF processing
google-generativeai>=0.3.0  # Gemini
```

## 🔐 Bezpieczeństwo

- Wszystkie klucze API przechowywane lokalnie w `.env`
- Brak zewnętrznych połączeń bez Twojej zgody
- Dane PDF przetwarzane lokalnie
- Możliwość pracy offline (bez pluginów)

## 🤝 Przyczynianie się

Projekt jest otwarty - możesz:
- Dodawać nowe specjalistów
- Tworzyć własne pluginy
- Ulepszać UI/UX
- Rozszerzać możliwości AI

## 📄 Licencja

MIT License - wykorzystaj komercyjnie i prywatnie.

---

**AI Council** - Twój osobisty zespół konsultantów AI, dostępny 24/7. 🚀
