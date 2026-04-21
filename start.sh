#!/usr/bin/env bash
# Quick starter for Linux/Mac (uv + uvicorn)

set -euo pipefail

echo "============================================"
echo "AI COUNCIL - Linux/Mac Starter"
echo "============================================"
echo ""

if ! command -v uv &> /dev/null; then
    echo "[INFO] Instalacja uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v uv &> /dev/null; then
    echo "[ERROR] uv nie jest dostepny. Zobacz: https://docs.astral.sh/uv/"
    exit 1
fi

uv run python start.py
