# CLAUDE.md — AI Council Codebase Guide

This file provides AI assistants with context about the AI Council codebase: its structure, conventions, workflows, and how to make changes safely.

---

## Project Overview

**AI Council** is a multi-agent deliberation platform where several AI personas independently analyze a query and then collaborate to produce a synthesized recommendation. It exposes a FastAPI REST + WebSocket API, a Vanilla JS SPA frontend, a RAG knowledge base (Pinecone), a plugin ecosystem, and a dedicated SEO article generation module.

**Runtime:** Python 3.12+ / FastAPI (port 8501)
**Frontend:** Vanilla JS + Tailwind CSS SPA (no build step)
**Vector DB:** Pinecone (two indexes: knowledge base + SEO articles)
**LLM Providers:** OpenAI, Grok (xAI), Gemini, DeepSeek, Perplexity, OpenRouter

---

## Repository Layout

```
ai-council/
├── main.py                    # FastAPI app entry point (1 400+ lines)
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── run.sh                     # Bootstrap + launch script (port 8501)
├── run_web.sh                 # Alternative launch script
├── verify_api.py              # Quick HTTP smoke-test for /api/providers
├── verify_llm.py              # LLM provider smoke-test
├── test_openrouter_models.py  # Async test for OpenRouter model list
│
├── src/                       # All application logic
│   ├── llm_providers.py       # Unified LLM provider abstraction (6 providers)
│   ├── agents/                # Agent definitions & registry
│   │   ├── base.py            # BaseAgent ABC, AgentConfig, AgentResponse, AgentRegistry
│   │   ├── core_agents.py     # 5 core agents (Strategist, Analyst, Practitioner, Expert, Synthesizer)
│   │   ├── specialist_agents.py # Specialist agents (Social Media, LinkedIn, SEO, Blog, Branding)
│   │   ├── specialists.py     # Factory helpers for specialists
│   │   ├── custom_agents.py   # CustomAgent + CustomAgentConfig (user-defined)
│   │   ├── agent_storage.py   # JSON persistence for custom agents
│   │   ├── historical_agents.py # Historical persona agents
│   │   └── prompt_templates.py  # System prompt templates for custom agents
│   ├── council/               # Deliberation orchestration
│   │   ├── orchestrator.py    # Council (single-round), CouncilDeliberation result
│   │   ├── debate.py          # DebateOrchestrator (multi-round with reactions & consensus)
│   │   ├── modes.py           # Deliberation modes: Deep Dive, Speed Round, Devil's Advocate, SWOT, Red Team
│   │   └── historical_council.py # Historical-agent council variant
│   ├── knowledge/             # RAG knowledge base
│   │   ├── ingest.py          # PDF → chunk → embed → Pinecone
│   │   ├── retriever.py       # Semantic search with category/score filters
│   │   └── character_knowledge.py # Per-agent knowledge retrieval
│   ├── plugins/               # Plugin ecosystem
│   │   ├── __init__.py        # BasePlugin ABC + PluginManager registry
│   │   ├── web_search.py      # TavilySearchPlugin, DuckDuckGoSearchPlugin
│   │   ├── url_analyzer.py    # URLAnalyzerPlugin (website scraping)
│   │   ├── wikipedia.py       # WikipediaPlugin
│   │   ├── weather.py         # WeatherPlugin
│   │   ├── stocks.py          # StockPricesPlugin
│   │   └── utilities.py       # Calculator, DateTime, Hash/Encode, UnitConverter, Random, TextTools
│   ├── seo/                   # SEO article generation pipeline
│   │   ├── article_generator.py  # Main pipeline: SERP → competitors → outline → draft → brand
│   │   ├── article_storage.py    # Pinecone article persistence
│   │   ├── brand_info.py         # BrandInfoManager
│   │   ├── serp_analyzer.py      # SERP analysis
│   │   ├── competitor_analyzer.py
│   │   ├── schema_generator.py   # JSON-LD schema markup
│   │   └── ahrefs_importer.py    # Ahrefs keyword import
│   └── storage/               # Session persistence
│       ├── session_history.py # JSON file storage in data/sessions/
│       └── export.py          # Export to Markdown / HTML / PDF
│
├── static/                    # Frontend (served directly by FastAPI)
│   ├── index.html             # SPA shell (Tailwind CSS dark theme)
│   ├── js/app.js              # 3 200+ line SPA (vanilla JS, EventSource streaming)
│   └── css/styles.css        # Custom overrides
│
└── data/
    ├── brand_info.json        # Persisted brand info for SEO module
    ├── custom_agents.json     # Persisted custom agent definitions
    └── sessions/              # Session JSON files (auto-created)
```

---

## Quick Start

```bash
# 1. Copy and fill in env file
cp .env.example .env
# Edit .env with your API keys

# 2. Launch (creates venv automatically)
./run.sh
# App available at http://localhost:8501
```

`run.sh` creates `venv/` if absent, installs `requirements.txt`, then starts uvicorn with `--reload`.

---

## Environment Variables

Copy `.env.example` → `.env`. **Never commit `.env`** — it is git-ignored.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | One LLM key required | — | OpenAI (GPT-4o, etc.) |
| `GROK_API_KEY` | Optional | — | xAI Grok |
| `GEMINI_API_KEY` | Optional | — | Google Gemini |
| `DEEPSEEK_API_KEY` | Optional | — | DeepSeek |
| `PERPLEXITY_API_KEY` | Optional | — | Perplexity AI |
| `PINECONE_API_KEY` | Optional | — | Vector DB (RAG + SEO) |
| `PINECONE_INDEX_NAME` | Optional | `ebook-library` | Knowledge base index |
| `PINECONE_SEO_INDEX_NAME` | Optional | `seo-articles` | SEO article index |
| `TAVILY_API_KEY` | Optional | — | Web search plugin |
| `DEFAULT_LLM_PROVIDER` | Optional | `openai` | Default provider |

The application starts without Pinecone or optional keys — those features are simply unavailable.

---

## Core Architecture

### 1. Agent System (`src/agents/`)

Every agent extends `BaseAgent` (ABC in `base.py`):

```python
class BaseAgent(ABC):
    config: AgentConfig          # name, role, emoji, enabled, preferred_provider
    provider: LLMProvider        # injected or resolved from config

    @abstractmethod
    def get_system_prompt(self) -> str: ...  # personality definition

    def build_user_prompt(self, query, context) -> str: ...  # query + RAG context
    async def analyze(self, query, context, ...) -> AgentResponse: ...
    async def analyze_stream(self, ...) -> AsyncGenerator[str, None]: ...
```

**Core agents** (always available, enabled by default):
| Agent | Emoji | Focus |
|---|---|---|
| Strategist | 🎯 | Long-term vision, business goals |
| Analyst | 📊 | Pros/cons, risk, data-driven perspective |
| Practitioner | 🔧 | Feasibility, implementation details |
| Expert | 🎓 | Domain knowledge retrieval |
| Synthesizer | ✨ | Aggregates all views into final recommendation |

**Specialist agents** (disabled by default): Social Media, LinkedIn, SEO, Blog, Branding.

**Custom agents**: User-created via API or UI; stored in `data/custom_agents.json` via `agent_storage`.

`AgentRegistry` (global singleton `agent_registry` in `base.py`) manages all agents:
- `register(agent)` — add agent
- `get_enabled()` — list active agents
- `toggle(name, enabled)` — enable/disable at runtime

### 2. Council Orchestration (`src/council/`)

**`Council`** (`orchestrator.py`) — single deliberation round:
1. Retrieve RAG context (optional)
2. Send query in parallel to all enabled agents
3. Collect `AgentResponse` objects
4. Pass all responses to Synthesizer for final summary
5. Return `CouncilDeliberation` dataclass

**`DebateOrchestrator`** (`debate.py`) — multi-round debate:
1. Initial response from each agent
2. Reaction round (agents see each other's responses)
3. Consensus synthesis

**Council Modes** (`modes.py`): Deep Dive, Speed Round, Devil's Advocate, SWOT Analysis, Red Team — each changes system prompt framing and synthesis instructions.

### 3. LLM Providers (`src/llm_providers.py`)

Unified `LLMProvider` interface for 6 backends:

| Provider class | Backend |
|---|---|
| `OpenAIProvider` | OpenAI API |
| `GrokProvider` | xAI (OpenAI-compatible) |
| `GeminiProvider` | Google Generative AI |
| `DeepSeekProvider` | DeepSeek (OpenAI-compatible) |
| `PerplexityProvider` | Perplexity (OpenAI-compatible) |
| `OpenRouterProvider` | OpenRouter (dynamic model list) |

All providers support:
- `complete(messages, ...)` → `LLMResponse`
- `stream(messages, ...)` → `AsyncGenerator[str, None]`
- Token cost tracking via `TOKEN_COSTS` dict
- `UsageStats` metadata on every response

`get_provider(name)` returns the appropriate provider instance from `AVAILABLE_PROVIDERS`.

### 4. Knowledge Base — RAG (`src/knowledge/`)

- **Ingest** (`ingest.py`): Upload PDF → chunk → embed → upsert to Pinecone index `PINECONE_INDEX_NAME`
- **Retrieve** (`retriever.py`): Semantic search with optional `category`, `source_type`, `min_score` filters
- **Format**: Each chunk stored with metadata: `title`, `category`, `language`, `source_type`, `chunk_index`

### 5. Plugin System (`src/plugins/`)

`BasePlugin` ABC requires:
- `name`, `description`, `api_key_env` properties
- `is_available()` → bool
- `execute(**kwargs)` → `PluginResult`

`PluginManager` (global singleton from `get_plugin_manager()`) registers all plugins and provides `execute(plugin_name, **kwargs)`.

Available plugins: `tavily_search`, `duckduckgo_search`, `url_analyzer`, `wikipedia`, `weather`, `stock_prices`, `calculator`, `datetime`, `hash_encode`, `unit_converter`, `random_generator`, `text_tools`.

### 6. SEO Module (`src/seo/`)

Pipeline: SERP analysis → competitor scraping → structured outline → article draft → brand voice overlay → JSON-LD schema injection.

Article persistence uses a dedicated Pinecone index (`PINECONE_SEO_INDEX_NAME`). Brand info is loaded from / persisted to `data/brand_info.json`.

### 7. Session Storage (`src/storage/`)

Sessions are stored as JSON files in `data/sessions/`:
- Metadata: `session_id`, `timestamp`, `query`, `council_type`, `agents_used`, `total_cost`
- Full deliberation content per session
- Export via `/api/sessions/{session_id}/export?format=markdown|html|pdf`

---

## API Endpoints

All endpoints are defined in `main.py`. The FastAPI app mounts `static/` at `/`.

### Agents
| Method | Path | Description |
|---|---|---|
| GET | `/api/agents` | List all agents with status |
| POST | `/api/agents/{name}/toggle` | Enable/disable an agent |
| GET | `/api/agents/custom` | List custom agents |
| POST | `/api/agents/custom` | Create custom agent |
| GET | `/api/agents/custom/{id}` | Get custom agent |
| PUT | `/api/agents/custom/{id}` | Update custom agent |
| DELETE | `/api/agents/custom/{id}` | Delete custom agent |
| POST | `/api/agents/custom/{id}/toggle` | Toggle custom agent |

### Deliberation
| Method | Path | Description |
|---|---|---|
| POST | `/api/deliberate` | Non-streaming deliberation |
| GET | `/api/deliberate/stream` | SSE streaming deliberation |
| GET | `/api/debate/stream` | SSE multi-round debate |
| GET | `/api/council/modes` | List available council modes |
| GET | `/api/council/mode/stream` | SSE mode-specific deliberation |
| GET | `/api/historical/deliberate/stream` | Historical agents SSE |

### Knowledge Base
| Method | Path | Description |
|---|---|---|
| POST | `/api/ingest` | Upload PDF (multipart/form-data) |
| GET | `/api/stats` | Knowledge base statistics |

### Misc
| Method | Path | Description |
|---|---|---|
| GET | `/api/providers` | Available LLM providers + models |
| GET | `/api/historical/agents` | Historical agent list |
| GET | `/api/sessions/{id}/export` | Export session (`?format=markdown\|html\|pdf`) |

**Streaming endpoints** use Server-Sent Events (SSE). The frontend connects via `EventSource`. Each event is a JSON object; the stream ends with `data: [DONE]`.

---

## Frontend Architecture

Single-page application in `static/js/app.js` (~3 200 lines), zero build tooling.

- **Navigation**: `navigateTo(view)` switches between Dashboard, SEO Generator, Agents, Plugins, Agent Builder, Session History
- **Streaming**: `EventSource` for all deliberation endpoints; tokens appended in real time
- **Theming**: Tailwind CSS dark mode (`dark:` classes)
- **Custom components**: Custom `<select>` dropdowns, file attachment handling
- **No bundler**: Edits to `app.js` or `index.html` are immediately reflected on reload

---

## Development Conventions

### Language
- Code, identifiers, and docstrings are primarily **English**
- Some legacy comments and UI strings are in **Polish** — this is intentional and should not be changed without reason

### Python Style
- **Type hints** on all function signatures (Python 3.10+ union syntax acceptable)
- **Dataclasses** (`@dataclass`) for data structures — prefer over plain dicts
- **Async/await** for all I/O-bound operations; use `AsyncGenerator` for streaming
- **Snake_case** for functions and variables; **CamelCase** for classes; **UPPER_CASE** for constants
- Error handling via `try/except` with `print()` — no structured logging framework
- No test framework (pytest not configured); verification is done via standalone scripts

### Adding a New Agent
1. Create a class extending `BaseAgent` in `src/agents/`
2. Implement `get_system_prompt()` returning the personality string
3. Define an `AgentConfig` with `name`, `role`, `emoji`
4. Register via `agent_registry.register(agent)` — typically in `main.py` lifespan or a factory function
5. Add factory function (e.g. `create_my_agent()`) consistent with `create_core_agents()` pattern

### Adding a New LLM Provider
1. Add a class implementing `LLMProvider` interface in `src/llm_providers.py`
2. Add token costs to `TOKEN_COSTS` dict
3. Register in `AVAILABLE_PROVIDERS` dict
4. Add corresponding env var to `.env.example`

### Adding a New Plugin
1. Create a class extending `BasePlugin` in `src/plugins/`
2. Implement `name`, `description`, `api_key_env`, `is_available()`, `execute()`
3. Register in `PluginManager` inside `get_plugin_manager()` in `src/plugins/__init__.py`
4. Import and register in `main.py` lifespan

### Modifying the Frontend
- Edit `static/js/app.js` directly — no build step
- Add new views by extending the `navigateTo()` switch and adding a corresponding `render*View()` function
- Tailwind classes are loaded via CDN in `index.html` — no compilation needed

---

## Key Design Patterns

| Pattern | Where Used |
|---|---|
| Registry | `AgentRegistry`, `PluginManager` |
| Abstract Base Class | `BaseAgent`, `BasePlugin` |
| Factory | `create_core_agents()`, `create_specialists()`, `create_custom_agent()` |
| Orchestrator | `Council`, `DebateOrchestrator` |
| Provider abstraction | `LLMProvider` + 6 provider classes |
| Async generator streaming | `analyze_stream()`, SSE endpoints in `main.py` |
| Dataclass DTOs | `AgentResponse`, `AgentConfig`, `UsageStats`, `CouncilDeliberation` |
| Singleton | `agent_registry`, `get_plugin_manager()` |

---

## Testing

No pytest/unittest suite exists. Use the verification scripts for smoke-testing:

```bash
# Start server first
./run.sh &

# Test LLM providers endpoint
python verify_api.py

# Test a specific LLM provider
python verify_llm.py

# Test OpenRouter model listing
python test_openrouter_models.py
```

When adding new features, add a corresponding verification script or extend an existing one.

---

## Data Flow: Council Deliberation

```
User query
    │
    ▼
POST /api/deliberate/stream (SSE)
    │
    ▼
Council.deliberate(query, provider, model, ...)
    │
    ├─► knowledge/retriever.py  ──► Pinecone semantic search ──► context chunks
    │
    ├─► [agent1.analyze_stream(), agent2.analyze_stream(), ...]  ──► LLM provider
    │       (parallel, each with own system prompt + RAG context)
    │
    └─► Synthesizer.analyze_stream(all_responses)  ──► final synthesis
    │
    ▼
SSE stream → EventSource (app.js) → rendered Markdown in UI
    │
    ▼
session_history.save_session(deliberation)  →  data/sessions/<id>.json
```

---

## Important Files to Know

| File | Why It Matters |
|---|---|
| `main.py` | All FastAPI routes; app lifespan initializes agents/plugins |
| `src/agents/base.py` | `BaseAgent`, `AgentConfig`, `AgentResponse`, `AgentRegistry` — foundation of the agent system |
| `src/agents/core_agents.py` | The 5 core agent personalities |
| `src/council/orchestrator.py` | Council deliberation logic |
| `src/llm_providers.py` | All LLM provider classes and `get_provider()` |
| `src/plugins/__init__.py` | `BasePlugin`, `PluginManager`, plugin registration |
| `static/js/app.js` | Entire frontend SPA |
| `.env.example` | Canonical list of all environment variables |
| `data/custom_agents.json` | Persisted custom agent definitions (auto-managed) |
| `data/sessions/` | Session history directory (auto-created) |

---

## What Not to Do

- **Do not commit `.env`** — it is in `.gitignore`
- **Do not add a build step** to the frontend without updating `run.sh` and this file
- **Do not delete `data/`** — it contains persisted agent definitions and session history
- **Do not rename `agent_registry`** — it is a global singleton imported across many modules
- **Do not add `streamlit` dependencies** — Streamlit is legacy; the active frontend is FastAPI + vanilla JS
- **Do not use synchronous blocking I/O** inside async endpoint handlers — wrap with `asyncio.run_in_executor` if needed
