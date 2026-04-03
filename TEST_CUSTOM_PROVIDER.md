# Test Custom Provider

## Naprawione problemy:

### Problem 1: URL API nie zapisywał się
**Przyczyna**: `replace('_', '-')` zamieniał tylko pierwsze wystąpienie `_`  
**Rozwiązanie**: Zmieniono na `replace(/_/g, '-')` aby zamienić wszystkie wystąpienia

### Problem 2: Model nie zmieniał się przy wyborze custom
**Przyczyna**: Logika w `updateModels()` nie zawsze aktualizowała `currentModel`  
**Rozwiązanie**: Zmieniono logikę aby zawsze ustawiać pierwszy model z listy

## Jak używać:

1. Kliknij ikonę ustawień (⚙️) w lewym dolnym rogu
2. Przejdź do zakładki "Konfiguracja"
3. Kliknij przycisk "Zarządzaj" przy "🔑 Klucze API"
4. W sekcji "Custom API" wpisz:
   - **API Key**: Twój klucz API (lub "dummy" dla lokalnych API)
   - **Base URL**: np. `http://localhost:1234/v1` (LM Studio) lub `http://localhost:11434/v1` (Ollama)
   - **Model name**: nazwa modelu, np. `llama-3.1-8b`
5. Kliknij "💾 Save Keys"
6. Wybierz provider "🔌 Custom" z dropdown w górnym menu
7. Model zostanie automatycznie załadowany z localStorage

## Debugowanie:

Otwórz konsolę przeglądarki (F12) i sprawdź logi:
- Po zapisaniu kluczy: `Saved custom_base_url: ***`
- Po zmianie providera: `Custom provider selected, model: llama-3.1-8b`
- Po aktualizacji modelu: `Model updated to: llama-3.1-8b`

## Kompatybilne API:
- LM Studio (http://localhost:1234/v1)
- Ollama z OpenAI compatibility (http://localhost:11434/v1)
- vLLM
- LocalAI
- Każde inne API kompatybilne z OpenAI
