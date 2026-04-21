#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup Checker - Sprawdza czy wszystko działa przed uruchomieniem
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def check_python_version():
    """Sprawdź wersję Pythona"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 12):
        print("[X] Python 3.12+ wymagany (zgodnie z pyproject.toml)")
        return False
    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Sprawdź czy wszystkie pakiety są zainstalowane"""
    required = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("openai", "openai"),
        ("google.generativeai", "google.generativeai"),
        ("pydantic", "pydantic"),
        ("python-dotenv", "dotenv"),  # Import name is different!
        ("aiofiles", "aiofiles")
    ]

    missing = []
    for display_name, import_name in required:
        try:
            __import__(import_name.split(".")[0])
            print(f"[OK] {display_name}")
        except ImportError:
            print(f"[X] {display_name} - BRAK")
            missing.append(display_name)

    if missing:
        print(f"\n[X] Brakujace pakiety: {', '.join(missing)}")
        print("Zainstaluj (zalecane): uv sync --extra dev")
        print("Alternatywa: pip install -e .")
        return False

    return True

def check_env_file():
    """Sprawdź plik .env"""
    env_path = Path(".env")
    if not env_path.exists():
        print("[X] Brak pliku .env")
        print("Skopiuj: cp .env.example .env")
        return False

    print("[OK] Plik .env istnieje")

    # Sprawdź czy ma jakieś klucze API
    with open(env_path, encoding='utf-8') as f:
        content = f.read()
        if "dummy-key" in content or "your_" in content:
            print("[!] Plik .env ma przykladowe klucze - dodaj prawdziwe API keys")
            return True  # Nie blokuj startu

    return True

def check_directories():
    """Sprawdź czy istnieją wymagane katalogi"""
    dirs = ["static", "logs", "src"]
    for d in dirs:
        path = Path(d)
        if not path.exists():
            print(f"[X] Brak katalogu: {d}")
            return False
        print(f"[OK] Katalog {d}")
    return True

def check_static_files():
    """Sprawdź czy są pliki statyczne"""
    index = Path("static/index.html")
    if not index.exists():
        print("[X] Brak static/index.html")
        return False
    print("[OK] Frontend (static/index.html)")
    return True

def main():
    print("[CHECK] Sprawdzanie konfiguracji AI Council...\n")

    checks = [
        ("Python", check_python_version),
        ("Zaleznosci", check_dependencies),
        ("Plik .env", check_env_file),
        ("Katalogi", check_directories),
        ("Frontend", check_static_files)
    ]

    results = []
    for name, check_func in checks:
        print(f"\n[{name}]:")
        results.append(check_func())

    print("\n" + "="*50)
    if all(results):
        print("[OK] Wszystko OK! Uruchom: uv run python start.py   lub: python start.py")
        return 0
    else:
        print("[ERROR] Napraw bledy przed uruchomieniem")
        return 1

if __name__ == "__main__":
    sys.exit(main())
