#!/usr/bin/env bash
# AI Council - Quick Start with uv (lockfile + dev extras)
set -euo pipefail

echo ""
echo "AI Council - Quick Start with uv"
echo "===================================="
echo ""

if ! command -v uv &> /dev/null; then
    echo "UV not found. Installing..."
    if [[ "$OSTYPE" == msys* ]] || [[ "$OSTYPE" == win32 ]]; then
        powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    echo ""
fi

echo "Syncing dependencies: uv sync --extra dev"
uv sync --extra dev
echo ""
echo "Dependencies synced."
echo ""

if [ ! -f ".env" ]; then
    echo "No .env file. Copying from .env.example..."
    cp .env.example .env
    echo "Edit .env and add your API keys."
    echo ""
fi

echo "Optional: Redis for response cache (REDIS_URL in .env)"
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "Redis: OK"
    else
        echo "Redis: installed but not running"
    fi
else
    echo "Redis: not in PATH (optional)"
fi
echo ""

read -r -p "Run tests? (y/N): " run_tests
if [[ "${run_tests:-}" =~ ^[Yy]$ ]]; then
    uv run pytest tests/ -v
    echo ""
fi

echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop."
echo ""

uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
