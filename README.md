# AI Council 🏛️

System multi-agentowy "Rada AI" do analizy zapytań z różnych perspektyw.

## Szybki start

```bash
# 1. Uzupełnij klucze API w .env
cp .env.example .env
nano .env  # Dodaj klucze GROK_API_KEY i GEMINI_API_KEY

# 2. Uruchom aplikację
./run.sh

# lub ręcznie:
source venv/bin/activate
streamlit run app.py
```

Aplikacja otworzy się na: **http://localhost:8501**

## Funkcje

### 🏛️ Rada AI
- **5 core agents**: Strateg, Analityk, Praktyk, Ekspert, Syntezator
- **Specjaliści**: SEO, LinkedIn, Social Media (można dodawać własnych)
- **Multi-provider**: OpenAI, Grok (xAI), Gemini

### 📚 Baza wiedzy
- Import PDF-ów (książki, streszczenia)
- RAG - agenci korzystają z kontekstu z bazy
- Pinecone jako vector database

## Import PDF-ów

```bash
# Pojedynczy plik
source venv/bin/activate
python -c "from src.knowledge.ingest import ingest_pdf; ingest_pdf('books_pdf/nazwa.pdf')"

# Cały katalog
python -c "from src.knowledge.ingest import ingest_directory; ingest_directory('books_pdf/')"
```

## Struktura projektu

```
├── app.py                    # Streamlit frontend
├── run.sh                    # Skrypt uruchomieniowy
├── requirements.txt          # Zależności
├── .env                      # Klucze API
│
├── src/
│   ├── llm_providers.py      # OpenAI, Grok, Gemini
│   ├── knowledge/
│   │   ├── ingest.py         # PDF → Pinecone
│   │   └── retriever.py      # RAG queries
│   │
│   ├── agents/
│   │   ├── base.py           # BaseAgent class
│   │   ├── core_agents.py    # 5 core agents
│   │   └── specialists.py    # SEO, LinkedIn, etc.
│   │
│   └── council/
│       └── orchestrator.py   # Council logic
│
└── books_pdf/                # Twoje PDF-y
```

## Dodawanie własnego specjalisty

```python
from src.agents.specialists import create_custom_specialist

email_expert = create_custom_specialist(
    name="Email Marketing Expert",
    specialty="Email Marketing",
    emoji="📧",
    expertise_areas=["Kampanie email", "Automatyzacja", "Segmentacja"],
    focus_points=["Open rate", "CTR", "Deliverability"]
)
```

## Wymagane klucze API

| Provider | Wymagany | Link |
|----------|----------|------|
| OpenAI | ✅ Tak | https://platform.openai.com/api-keys |
| Grok | ❌ Opcjonalny | https://console.x.ai/ |
| Gemini | ❌ Opcjonalny | https://aistudio.google.com/apikey |
| Pinecone | ✅ Tak (dla bazy wiedzy) | https://app.pinecone.io/ |
