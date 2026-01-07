# AI Council

**Advanced multi-agent AI council system with knowledge base, streaming, and plugins**

AI Council is an intelligent consulting system that uses a team of specialized AI agents to analyze problems from different perspectives. The system combines knowledge from your business library with modern AI models (GPT-5, Grok, Gemini).

## Quick Start

```bash
# 1. Clone and navigate to directory
cd ai-council

# 2. Run installation script
./run.sh
```

Application will be available at: **http://localhost:8501**

### Prerequisites
- Python 3.12+
- API keys for selected providers

## Key Features

### AI Council of Experts
- **5 core agents**:
  - **Strategist** - long-term vision, business goals
  - **Analyst** - pros/cons analysis, risk assessment
  - **Practitioner** - feasibility, implementation planning
  - **Expert** - deep domain knowledge from your database
  - **Synthesizer** - final recommendation combining all perspectives

- **Industry specialists**: SEO, LinkedIn, Social Media, Branding, Blog Content
- **Dynamic agent enable/disable** in real-time

### Intelligent Knowledge Base
- **RAG (Retrieval-Augmented Generation)** - agents draw context from your documents
- **Automatic book categorization** (marketing, strategy, business, productivity)
- **PDF import** - your entire business library (48 Laws of Power, Atomic Habits, etc.)
- **Pinecone vector database** - semantic search

### Advanced Features
- **Multi-provider AI**: OpenAI (GPT-4o/5), Grok (xAI), Gemini (Google)
- **Real-time streaming** - responses generated live token by token
- **Debate mode** - multi-round discussions between agents
- **Chat mode** - conversation context maintained between queries
- **Attachments** - analysis of PDF/txt/docx/md files
- **Cost tracking** - full token and cost calculation

### Plugin System
- **Web search** (Tavily, DuckDuckGo)
- **URL analyzer** - website analysis and summarization
- **Wikipedia** - article search and summarization
- **Weather** - weather forecasts
- **Stocks** - stock market data
- **Calculator** - mathematical calculator
- **Utilities** - converters, hash, random, text tools

### Custom Agents
- **Custom AI agents** - create specialists with your own prompts
- **Template system** - ready-made templates for different roles
- **Tool integration** - integration with plugins
- **Test mode** - test agents before saving

## Use Cases

**For entrepreneurs:**
- Business development strategy analysis
- New investment risk assessment
- Business process optimization
- Content marketing and social media strategy

**For specialists:**
- Technical solution analysis
- Market research and competition
- Marketing strategies
- SEO and content optimization

## Architecture

### Backend (FastAPI)
```
├── main.py                 # REST API + WebSocket streaming
├── src/
│   ├── agents/            # Agent system
│   │   ├── base.py        # Agent base class
│   │   ├── core_agents.py # 5 core agents
│   │   ├── specialists.py # Industry specialists
│   │   ├── custom_agents.py # Custom agents
│   │   └── agent_storage.py # Custom agent management
│   │
│   ├── council/           # Council logic
│   │   ├── orchestrator.py # Deliberation coordination
│   │   └── debate.py      # Debate system
│   │
│   ├── knowledge/         # Knowledge base
│   │   ├── ingest.py      # PDF → vectors
│   │   └── retriever.py   # RAG retrieval
│   │
│   ├── llm_providers.py   # AI integration
│   ├── plugins/           # Plugin system
│   └── prompt_templates.py # Prompt templates
```

### Frontend
```
├── static/
│   ├── index.html         # Main UI
│   ├── js/app.js          # JavaScript application
│   └── css/styles.css     # Styling
└── app.py                 # Legacy Streamlit UI
```

## API Configuration

Create a `.env` file in the root directory:

```env
# Required for knowledge base
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=your_index_name

# Choose at least one AI provider
OPENAI_API_KEY=your_openai_key
GROK_API_KEY=your_grok_key
GEMINI_API_KEY=your_gemini_key

# Optional - for plugins
TAVILY_API_KEY=your_tavily_key
WEATHER_API_KEY=your_weather_key
```

## Knowledge Base Management

### Import single PDF
```bash
python -c "from src.knowledge.ingest import ingest_pdf; ingest_pdf('books_pdf/atomic_habits.pdf')"
```

### Import entire directory
```bash
python -c "from src.knowledge.ingest import ingest_directory; ingest_directory('books_pdf/')"
```

### Check statistics
```bash
python -c "from src.knowledge.ingest import get_ingestion_stats; print(get_ingestion_stats())"
```

## Creating Custom Agents

```python
from src.agents.specialists import create_custom_specialist

# Example: Email Marketing Specialist
email_expert = create_custom_specialist(
    name="Email Marketing Expert",
    specialty="Email Marketing",
    emoji="📧",
    expertise_areas=["Email campaigns", "Automation", "Segmentation"],
    focus_points=["Open rate", "CTR", "Deliverability"]
)
```

### Advanced custom agents
```python
from src.agents.custom_agents import create_custom_agent, CustomAgentConfig

config = CustomAgentConfig(
    name="Data Analyst",
    emoji="📊",
    role="Data Science Expert",
    persona="I specialize in data analysis and machine learning",
    system_prompt="You are a data science expert...",
    tools=["calculator", "web_search", "knowledge_base"],
    context_limit=10000
)

agent_id = create_custom_agent(config)
```

## API Endpoints

### AI Council
- `POST /api/deliberate` - Analysis by council of agents
- `GET /api/deliberate/stream` - Streaming deliberation
- `GET /api/debate/stream` - Multi-round agent debate

### Agent Management
- `GET /api/agents` - List all agents
- `POST /api/agents/{name}/toggle` - Enable/disable agent
- `GET/POST/PUT/DELETE /api/agents/custom` - Custom agent management

### Knowledge Base
- `POST /api/ingest` - Import PDF to knowledge base
- `GET /api/stats` - Knowledge base statistics

### Plugins
- `GET /api/plugins` - List available plugins
- `POST /api/plugins/web-search` - Web search
- `POST /api/plugins/analyze-url` - URL analysis
- `POST /api/plugins/weather` - Weather
- `POST /api/plugins/stocks` - Stock data

## UI Features

- **Dark theme** - modern, minimalist design
- **Real-time updates** - responses appear live
- **Responsive layout** - works on desktop and mobile
- **Agent management** - enable/disable agents in sidebar
- **Cost tracking** - monitor API costs in real-time
- **Export options** - download results as Markdown

## System Requirements

- **Python**: 3.12+
- **RAM**: 8GB+ (for large knowledge bases)
- **Disk**: 10GB+ (for vector database)

### Dependencies
```
fastapi>=0.109.0         # REST API
uvicorn>=0.27.0          # ASGI server
streamlit>=1.30.0        # Legacy UI
openai>=1.0.0           # OpenAI integration
pinecone>=8.0.0         # Vector database
pypdf>=3.0.0            # PDF processing
google-generativeai>=0.3.0  # Gemini
```

## Security

- All API keys stored locally in `.env`
- No external connections without your consent
- PDF data processed locally
- Offline capability (without plugins)

## Contributing

The project is open - you can:
- Add new specialists
- Create custom plugins
- Improve UI/UX
- Extend AI capabilities

## License

MIT License - use commercially and privately.

---

**AI Council** - Your personal team of AI consultants, available 24/7.
