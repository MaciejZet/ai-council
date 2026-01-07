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
    ./venv/bin/pip install -r requirements.txt
fi

# Aktywuj venv
source venv/bin/activate

# Sprawdź .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️ Brak pliku .env - skopiuj z .env.example i uzupełnij klucze API${NC}"
    cp .env.example .env
    echo "Otwórz .env i dodaj swoje klucze API"
    exit 1
fi

# Install FastAPI deps if needed (using venv pip)
./venv/bin/pip install fastapi uvicorn python-multipart --quiet 2>/dev/null

# Uruchom FastAPI (nowy frontend)
echo -e "${GREEN}🚀 Uruchamianie aplikacji na http://localhost:8501${NC}"
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8501

