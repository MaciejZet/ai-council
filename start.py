#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Starter - Sprawdza setup i uruchamia aplikację
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_checks() -> bool:
    """Uruchom check_setup.py (przez uv run, gdy dostepne)."""
    print("[CHECK] Sprawdzanie konfiguracji...\n")
    uv_bin = shutil.which("uv")
    cmd: list[str] = [uv_bin, "run", "python", "check_setup.py"] if uv_bin else [sys.executable, "check_setup.py"]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def start_server() -> None:
    """Uruchom serwer FastAPI przez uv (preferowane) lub uvicorn z bieżącego interpretera."""
    print("\n[START] Uruchamianie AI Council...\n")
    uv_bin = shutil.which("uv")
    cmd: list[str]
    if uv_bin:
        cmd = [
            uv_bin,
            "run",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload",
        ]
    else:
        print(
            "[!] Brak polecenia `uv`. Zainstaluj: https://docs.astral.sh/uv/\n"
            "    Nastepnie: uv sync --extra dev\n"
            "    Uzywam: python -m uvicorn (niezalecane w tym repo).\n"
        )
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload",
        ]
    try:
        subprocess.run(cmd, check=False)
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
