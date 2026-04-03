# 🐌 PROBLEM WYDAJNOŚCI - AI Council

## 🔴 Główny problem:

**Aplikacja odpowiada bardzo wolno na proste zapytania**

## 🔍 Przyczyny:

### 1. **Za dużo aktywnych agentów** (GŁÓWNA PRZYCZYNA)
- Domyślnie włączonych: **5 core agents + specialists**
- Każdy agent = osobne wywołanie LLM API
- Dla prostego "test" → **6-10 wywołań API!**
- Czas: ~3-5 sekund na agenta = **15-50 sekund total**

### 2. **Brak cache**
- Każde zapytanie idzie do API
- Brak Redis = brak cache
- Te same pytania = te same wolne odpowiedzi

### 3. **Synteza zawsze włączona**
- Po wszystkich agentach → jeszcze jedno wywołanie API
- Dodatkowe 3-5 sekund

### 4. **Knowledge base query**
- Pinecone query przed każdą deliberacją
- Dodatkowe 1-2 sekundy

---

## ✅ ROZWIĄZANIA:

### 🚀 Szybkie rozwiązanie (NATYCHMIASTOWE):

#### Opcja A: Wyłącz większość agentów
Edytuj `src/agents/core_agents.py`:

```python
def create_core_agents(provider: Optional[LLMProvider] = None) -> list[BaseAgent]:
    """Tworzy tylko 2 agentów zamiast 5"""
    agents = [
        Strategist(provider),
        # Analyst(provider),      # WYŁĄCZONY
        # Practitioner(provider),  # WYŁĄCZONY
        # Expert(provider),        # WYŁĄCZONY
        Synthesizer(provider),
    ]
    
    for agent in agents:
        agent_registry.register(agent)
    
    return agents
```

**Rezultat**: 2 agentów zamiast 5 = **3x szybciej** (5-10 sekund zamiast 15-50)

#### Opcja B: Tryb "Quick" - tylko 1 agent
Dodaj endpoint `/api/quick` który używa tylko 1 agenta:

```python
@app.post("/api/quick")
async def quick_response(request: DeliberateRequest):
    """Szybka odpowiedź - tylko 1 agent, bez syntezy"""
    provider = create_llm_provider(request.provider, request.model)
    
    # Tylko Strategist
    strategist = Strategist(provider)
    response = await strategist.analyze(request.query, [])
    
    return {"content": response.content}
```

**Rezultat**: 1 agent = **10x szybciej** (2-3 sekundy)

---

### 🔧 Średnioterminowe rozwiązania:

#### 1. Włącz Redis cache
```bash
# Zainstaluj Redis
# Windows: https://github.com/microsoftarchive/redis/releases
# Linux: sudo apt install redis-server

# Uruchom
redis-server

# Restart aplikacji
python start.py
```

**Rezultat**: Powtórzone zapytania = **instant** (<50ms)

#### 2. Użyj szybszych modeli
W `.env`:
```env
# Zamiast gpt-4o (wolny)
DEFAULT_MODEL=gpt-4o-mini

# Lub DeepSeek (bardzo szybki)
DEFAULT_MODEL=deepseek-chat

# Lub Gemini Flash (najszybszy)
DEFAULT_MODEL=gemini-1.5-flash
```

**Rezultat**: **2-3x szybciej** per agent

#### 3. Wyłącz knowledge base dla prostych zapytań
```python
# W main.py, endpoint /api/deliberate
council = Council(
    use_knowledge_base=False  # Wyłącz dla testów
)
```

**Rezultat**: **-2 sekundy** per request

---

### 🏗️ Długoterminowe rozwiązania:

#### 1. Streaming responses
Użyj `/api/deliberate/stream` zamiast `/api/deliberate`
- Użytkownik widzi odpowiedzi na bieżąco
- Wrażenie szybkości nawet jeśli trwa długo

#### 2. Inteligentny routing
```python
def select_agents(query: str) -> List[BaseAgent]:
    """Wybierz tylko relevantnych agentów"""
    if len(query) < 20:  # Proste pytanie
        return [Strategist()]
    elif "analiza" in query.lower():
        return [Analyst(), Synthesizer()]
    else:
        return get_all_agents()
```

#### 3. Parallel + timeout
```python
# W orchestrator.py
tasks = [agent.analyze(query, context) for agent in agents]
responses = await asyncio.wait_for(
    asyncio.gather(*tasks),
    timeout=10.0  # Max 10 sekund
)
```

---

## 🎯 REKOMENDACJA (zrób teraz):

### Krok 1: Stwórz tryb "Fast"
```python
# Dodaj do main.py

@app.post("/api/fast")
async def fast_deliberate(request: DeliberateRequest):
    """Szybka deliberacja - tylko 1-2 agentów"""
    provider = create_llm_provider(request.provider, request.model)
    
    # Tylko Strategist
    strategist = Strategist(provider)
    response = await strategist.analyze(request.query, [])
    
    return {
        "query": request.query,
        "response": response.content,
        "agent": "Strategist",
        "tokens": response.total_tokens,
        "time": "~2-3s"
    }
```

### Krok 2: Domyślnie wyłącz specialists
```python
# W main.py, lifespan
async def lifespan(app: FastAPI):
    create_core_agents()
    # create_specialists()  # WYŁĄCZ - włączaj ręcznie gdy potrzeba
```

### Krok 3: Użyj szybszego modelu
```env
# W .env
DEFAULT_MODEL=gpt-4o-mini  # Zamiast gpt-4o
```

---

## 📊 Porównanie wydajności:

| Konfiguracja | Agenci | Czas | Koszt |
|--------------|--------|------|-------|
| **Obecna (wolna)** | 5 core + 5 specialists | 30-50s | $0.05 |
| **Zoptymalizowana** | 2 core | 5-10s | $0.01 |
| **Fast mode** | 1 agent | 2-3s | $0.005 |
| **Fast + cache** | 1 agent (cached) | <50ms | $0 |
| **Fast + mini model** | 1 agent (gpt-4o-mini) | 1-2s | $0.001 |

---

## 🚀 Quick Fix (skopiuj i wklej):

Stwórz plik `src/council/fast_mode.py`:

```python
"""Fast Mode - Szybkie odpowiedzi bez pełnej rady"""

from src.agents.core_agents import Strategist
from src.llm_providers import LLMProvider

async def fast_response(query: str, provider: LLMProvider) -> str:
    """Szybka odpowiedź - tylko 1 agent"""
    strategist = Strategist(provider)
    response = await strategist.analyze(query, [])
    return response.content
```

Dodaj do `main.py`:

```python
from src.council.fast_mode import fast_response

@app.post("/api/fast")
async def fast_deliberate(request: DeliberateRequest):
    provider = create_llm_provider(request.provider, request.model)
    content = await fast_response(request.query, provider)
    return {"response": content}
```

---

## 💡 Podsumowanie:

**Problem**: 5-10 agentów × 3-5s = 15-50 sekund  
**Rozwiązanie**: 1-2 agentów × 2s = 2-4 sekundy  
**Poprawa**: **10x szybciej!**

Chcesz żebym zaimplementował tryb "Fast"?
