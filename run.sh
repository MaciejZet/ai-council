#!/bin/bash

# AI Council - Skrypt uruchomieniowy
# ===================================

# Kolory
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🏛️ AI Council - Uruchamianie...${NC}"

# Sprawdź czy venv istnieje
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️ Tworzenie środowiska wirtualnego...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Sprawdź .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️ Brak pliku .env - skopiuj z .env.example i uzupełnij klucze API${NC}"
    cp .env.example .env
    echo "Otwórz .env i dodaj swoje klucze API"
    exit 1
fi

# Install FastAPI deps if needed
pip install fastapi uvicorn python-multipart --quiet

# Uruchom FastAPI (nowy frontend)
echo -e "${GREEN}🚀 Uruchamianie aplikacji na http://localhost:8501${NC}"
uvicorn main:app --reload --host 0.0.0.0 --port 8501
