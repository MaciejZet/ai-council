# 🔧 Troubleshooting Guide - AI Council

## Najczęstsze problemy i rozwiązania

### 🔴 Problem: "ModuleNotFoundError: No module named 'X'"

**Przyczyna**: Brakujące pakiety Python

**Rozwiązanie**:
```bash
# Zainstaluj wszystkie zależności
pip install -r requirements.txt

# Lub konkretny pakiet
pip install nazwa-pakietu
```

**Sprawdź**: `python check_setup.py`

---

### 🔴 Problem: "Port 8000 is already in use"

**Przyczyna**: Inny proces używa portu 8000

**Rozwiązanie Windows**:
```bash
# Znajdź proces
netstat -ano | findstr :8000

# Zabij proces (zamień <PID> na numer z poprzedniej komendy)
taskkill /PID <PID> /F
```

**Rozwiązanie Linux/Mac**:
```bash
# Znajdź i zabij proces
lsof -ti:8000 | xargs kill -9
```

**Alternatywa**: Zmień port w `start.py` (linia z `--port`)

---

### 🔴 Problem: "API key is invalid" lub "401 Unauthorized"

**Przyczyna**: Nieprawidłowe lub brakujące API keys

**Rozwiązanie**:
1. Otwórz plik `.env`
2. Zamień `dummy-key` na prawdziwe klucze API
3. Sprawdź czy klucz jest aktywny na stronie providera
4. Zrestartuj aplikację

**Gdzie zdobyć klucze**: Zobacz [QUICK_START.md](QUICK_START.md)

---

### 🔴 Problem: "Redis connection failed"

**Przyczyna**: Redis nie jest uruchomiony (ale to opcjonalne!)

**Rozwiązanie 1** (Uruchom Redis):
```bash
# Windows (wymaga instalacji Redis)
redis-server

# Linux/Mac
redis-server
# lub
brew services start redis  # Mac z Homebrew
```

**Rozwiązanie 2** (Wyłącz Redis):
Aplikacja działa bez Redis (tylko bez cache). Zignoruj ten błąd.

---

### 🔴 Problem: "Pinecone connection failed"

**Przyczyna**: Brak konfiguracji Pinecone (opcjonalne)

**Rozwiązanie**:
Pinecone jest potrzebny tylko dla knowledge base (RAG). Jeśli nie używasz tej funkcji:
- Zignoruj błąd
- Lub dodaj klucze do `.env`:
```env
PINECONE_API_KEY=twoj-klucz
PINECONE_INDEX_NAME=nazwa-indexu
```

---

### 🔴 Problem: "UnicodeEncodeError" w konsoli Windows

**Przyczyna**: Problem z kodowaniem znaków w Windows

**Rozwiązanie**: Używaj `start.py` zamiast `main.py` - ma naprawione kodowanie.

---

### 🔴 Problem: Aplikacja się uruchamia ale nie odpowiada

**Sprawdź**:
1. Czy serwer faktycznie działa:
   ```bash
   curl http://localhost:8000/health
   ```

2. Czy firewall nie blokuje:
   - Windows: Dodaj wyjątek dla Python
   - Linux: Sprawdź `ufw status`

3. Czy używasz właściwego adresu:
   - `http://localhost:8000` ✅
   - `https://localhost:8000` ❌ (bez SSL)

---

### 🔴 Problem: "Rate limit exceeded"

**Przyczyna**: Za dużo requestów w krótkim czasie

**Rozwiązanie**:
- Poczekaj 1 minutę
- Lub wyłącz rate limiting w `main.py` (linia z `rate_limit_middleware`)

**Limity domyślne**:
- 20 requestów/minutę
- 100 requestów/godzinę

---

### 🔴 Problem: Frontend się nie ładuje

**Sprawdź**:
1. Czy plik istnieje:
   ```bash
   ls static/index.html
   ```

2. Czy serwer działa:
   ```bash
   curl http://localhost:8000/health
   ```

3. Czy używasz właściwego URL:
   - `http://localhost:8000` ✅
   - `http://localhost:8000/index.html` ❌

---

### 🔴 Problem: "No such file or directory: '.env'"

**Rozwiązanie**:
```bash
# Skopiuj przykładowy plik
cp .env.example .env

# Lub użyj start.py - automatycznie sprawdzi
python start.py
```

---

### 🔴 Problem: Deliberacja zwraca błąd 500

**Możliwe przyczyny**:
1. **Brak API key** - Sprawdź `.env`
2. **Nieprawidłowy model** - Sprawdź nazwę modelu
3. **Przekroczony limit tokenów** - Skróć prompt
4. **Problem z providerem** - Sprawdź status API providera

**Debug**:
```bash
# Sprawdź logi
tail -f logs/ai_council_main_*.log

# Test health check
curl http://localhost:8000/health

# Test prostego requesta
curl -X POST http://localhost:8000/api/deliberate \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "provider": "openai", "model": "gpt-4o"}'
```

---

### 🔴 Problem: Wolne odpowiedzi

**Optymalizacja**:
1. **Włącz Redis cache**:
   ```bash
   redis-server
   ```

2. **Użyj szybszych modeli**:
   - `gpt-4o-mini` zamiast `gpt-4o`
   - `gemini-1.5-flash` zamiast `gemini-1.5-pro`
   - `deepseek-chat` (bardzo szybki i tani)

3. **Wyłącz niepotrzebnych agentów**:
   - W UI: Agents → Toggle off
   - Lub w kodzie: `agent.enabled = False`

---

### 🔴 Problem: Wysokie koszty API

**Redukcja kosztów**:
1. **Włącz cache** (Redis) - oszczędza 30-40%
2. **Użyj tańszych modeli**:
   - DeepSeek: ~$0.0003/1K tokens
   - Gemini Flash: ~$0.00008/1K tokens
   - GPT-4o-mini: ~$0.00015/1K tokens

3. **Ogranicz liczbę agentów** - mniej agentów = mniej requestów

4. **Sprawdź usage**:
   ```bash
   curl http://localhost:8000/metrics
   ```

---

## 🆘 Dalej nie działa?

### Krok 1: Uruchom diagnostykę
```bash
python check_setup.py
```

### Krok 2: Sprawdź logi
```bash
# Windows
type logs\ai_council_main_*.log

# Linux/Mac
cat logs/ai_council_main_*.log
```

### Krok 3: Test minimalny
```bash
# Test czy Python działa
python --version

# Test czy FastAPI działa
python -c "import fastapi; print('OK')"

# Test czy serwer startuje
python main.py
```

### Krok 4: Zgłoś issue
Jeśli nic nie pomaga, zgłoś issue z:
- Output z `check_setup.py`
- Logi z `logs/`
- Opis problemu
- System operacyjny i wersja Python

---

## 📚 Przydatne komendy

### Sprawdzenie statusu
```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# Lista agentów
curl http://localhost:8000/api/agents
```

### Czyszczenie
```bash
# Wyczyść cache (jeśli Redis)
redis-cli FLUSHALL

# Wyczyść logi
rm logs/*.log

# Reinstaluj pakiety
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Restart
```bash
# Zatrzymaj serwer
Ctrl+C

# Uruchom ponownie
python start.py
```

---

**Nie znalazłeś rozwiązania?** Sprawdź [NAPRAWIONE.md](NAPRAWIONE.md) lub [README.md](README.md)
