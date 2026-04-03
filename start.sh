#!/bin/bash
# Quick starter for Linux/Mac

echo "============================================"
echo "AI COUNCIL - Linux/Mac Starter"
echo "============================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 nie jest zainstalowany!"
    exit 1
fi

# Run the smart starter
python3 start.py
