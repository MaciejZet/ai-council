#!/bin/bash
# Run AI Council Web App (FastAPI)

cd "$(dirname "$0")"

# Activate venv if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install uvicorn if needed
pip install uvicorn fastapi python-multipart --quiet

# Run FastAPI
echo "🏛️ Starting AI Council Web App..."
echo "   Open: http://localhost:8501"
echo ""
uvicorn main:app --reload --host 0.0.0.0 --port 8501
