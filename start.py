#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Starter - Sprawdza setup i uruchamia aplikację
"""

import sys
import subprocess
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_checks():
    """Uruchom check_setup.py"""
    print("[CHECK] Sprawdzanie konfiguracji...\n")
    result = subprocess.run([sys.executable, "check_setup.py"], capture_output=False)
    return result.returncode == 0

def start_server():
    """Uruchom serwer FastAPI"""
    print("\n[START] Uruchamianie AI Council...\n")
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\n[STOP] Zamykanie serwera...")

def main():
    print("=" * 60)
    print("AI COUNCIL - Smart Starter")
    print("=" * 60)

    # Sprawdź czy jesteśmy w odpowiednim katalogu
    if not Path("main.py").exists():
        print("[X] Uruchom z glownego katalogu projektu (gdzie jest main.py)")
        return 1

    # Sprawdź setup
    if not run_checks():
        print("\n[X] Napraw bledy przed uruchomieniem")
        return 1

    # Uruchom serwer
    start_server()
    return 0

if __name__ == "__main__":
    sys.exit(main())
