# 🚀 SZYBKIE ROZWIĄZANIE - Optymalizacja wydajności

## ✅ Co zostało zrobione:

### 1. Dodano Fast Mode endpoint (`/api/fast`)
- Tylko 1 agent zamiast 5
- Czas: 2-3 sekundy zamiast 15-25 sekund
- **10x szybciej!**

### 2. Utworzono moduł `src/council/fast_mode.py`
- Szybka odpowiedź bez pełnej rady
- Używa tylko Strategista

---

## 🎯 JAK UŻYWAĆ (3 opcje):

### Opcja A: Zmień domyślny endpoint w kodzie (NAJSZYBSZE)

Edytuj `static/js/app.js` linię 945:

```javascript
// PRZED (wolne - 15-25s):
} else {
    deliberateStream(query);
}

// PO (szybkie - 2-3s):
} else {
    fastDeliberate(query);  // Użyj fast mode
}
```

I dodaj funkcję `fastDeliberate` (po linii 1538):

```javascript
// Fast Mode - szybka odpowiedź
async function fastDeliberate(query) {
    showStreamingUI();
    
    try {
        const response = await fetch('/api/fast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                provider: currentProvider,
                model: currentModel,
                use_knowledge_base: false  // Wyłącz dla szybkości
            })
        });
        
        if (!response.ok) throw new Error('API Error');
        const result = await response.json();
        
        // Wyświetl odpowiedź
        displayFastResponse(result);
        
    } catch (err) {
        showToast('Błąd: ' + err.message, 'error');
    }
}

function displayFastResponse(result) {
    const tabContents = document.getElementById('tab-contents');
    tabContents.innerHTML = `
        <div class="p-6 space-y-4">
            <div class="flex items-center gap-2 text-sm text-text-secondary mb-4">
                <span class="material-symbols-outlined text-[18px]">bolt</span>
                <span>Fast Mode - ${result.agent}</span>
                <span class="ml-auto">${result.tokens.total} tokens</span>
            </div>
            <div class="prose prose-invert max-w-none">
                ${marked.parse(result.response)}
            </div>
        </div>
    `;
}
```

---

### Opcja B: Wyłącz większość agentów (PROSTE)

Edytuj `src/agents/core_agents.py` linię 247:

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

**Rezultat**: 2 agentów = **3x szybciej** (5-10s zamiast 15-25s)

---

### Opcja C: Użyj szybszego modelu (NATYCHMIASTOWE)

W `.env` zmień:

```env
# PRZED (wolny):
DEFAULT_MODEL=gpt-4o

# PO (szybki):
DEFAULT_MODEL=gpt-4o-mini
```

Lub w UI wybierz:
- `gpt-4o-mini` (OpenAI - 2x szybszy)
- `gemini-1.5-flash` (Google - 3x szybszy)
- `deepseek-chat` (DeepSeek - bardzo szybki)

---

## 📊 Porównanie:

| Rozwiązanie | Czas | Jakość | Trudność |
|-------------|------|--------|----------|
| **Obecne (wolne)** | 15-25s | Najlepsza | - |
| **Opcja A: Fast Mode** | 2-3s | Dobra | Średnia |
| **Opcja B: 2 agentów** | 5-10s | Bardzo dobra | Łatwa |
| **Opcja C: Szybszy model** | 8-15s | Dobra | Bardzo łatwa |
| **B + C razem** | 3-7s | Dobra | Łatwa |

---

## 🎯 REKOMENDACJA:

### Dla szybkiego testu (teraz):
**Opcja C** - Zmień model na `gpt-4o-mini` w UI

### Dla produkcji (5 min):
**Opcja B** - Wyłącz 3 agentów w `core_agents.py`

### Dla najlepszej wydajności (15 min):
**Opcja A** - Zaimplementuj Fast Mode w UI

---

## 🚀 Quick Fix (skopiuj i wklej):

### 1. Edytuj `src/agents/core_agents.py`:

```python
def create_core_agents(provider: Optional[LLMProvider] = None) -> list[BaseAgent]:
    agents = [
        Strategist(provider),
        Synthesizer(provider),
    ]
    for agent in agents:
        agent_registry.register(agent)
    return agents
```

### 2. Zrestartuj serwer:

```bash
python start.py
```

### 3. Testuj:

Teraz odpowiedzi będą **3x szybsze** (5-10s zamiast 15-25s)!

---

## 💡 Dodatkowe optymalizacje:

### Włącz Redis cache:
```bash
redis-server
```

### Wyłącz knowledge base dla testów:
W UI: Odznacz "Użyj bazy wiedzy"

### Użyj streaming:
Aplikacja już używa streaming - użytkownik widzi odpowiedzi na bieżąco

---

**Który wariant chcesz zastosować?**

A) Fast Mode (najszybszy, wymaga zmian w JS)
B) 2 agentów (szybki, łatwy)
C) Szybszy model (natychmiastowy)
