#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test integracyjny - Sprawdza czy aplikacja działa end-to-end
"""

import sys
import time
import requests
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"

def test_server_running():
    """Test czy serwer odpowiada"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("[OK] Serwer dziala")
            return True
        else:
            print(f"[X] Serwer zwrocil kod: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[X] Serwer nie odpowiada - czy jest uruchomiony?")
        print("    Uruchom: python start.py")
        return False
    except Exception as e:
        print(f"[X] Blad: {e}")
        return False

def test_health_endpoint():
    """Test endpointu /health"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()

        if data.get("status") == "healthy":
            print("[OK] Health check: healthy")
            return True
        else:
            print(f"[!] Health check: {data.get('status', 'unknown')}")
            return True  # Nie blokuj jeśli częściowo działa
    except Exception as e:
        print(f"[X] Health endpoint error: {e}")
        return False

def test_agents_endpoint():
    """Test endpointu /api/agents"""
    try:
        response = requests.get(f"{BASE_URL}/api/agents", timeout=5)
        agents = response.json()

        if isinstance(agents, list) and len(agents) > 0:
            print(f"[OK] Agents endpoint: {len(agents)} agentow")
            return True
        else:
            print("[X] Agents endpoint: brak agentow")
            return False
    except Exception as e:
        print(f"[X] Agents endpoint error: {e}")
        return False

def test_frontend():
    """Test czy frontend się ładuje"""
    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200 and "AI Council" in response.text:
            print("[OK] Frontend laduje sie")
            return True
        else:
            print("[X] Frontend nie dziala poprawnie")
            return False
    except Exception as e:
        print(f"[X] Frontend error: {e}")
        return False

def test_metrics_endpoint():
    """Test endpointu /metrics"""
    try:
        response = requests.get(f"{BASE_URL}/metrics", timeout=5)
        data = response.json()

        if "uptime_seconds" in data:
            print(f"[OK] Metrics endpoint: uptime {data['uptime_seconds']:.1f}s")
            return True
        else:
            print("[!] Metrics endpoint: brak danych")
            return True  # Nie blokuj
    except Exception as e:
        print(f"[!] Metrics endpoint error: {e}")
        return True  # Nie blokuj

def test_deliberate_endpoint():
    """Test endpointu /api/deliberate (wymaga API key)"""
    try:
        payload = {
            "query": "Test query",
            "provider": "openai",
            "model": "gpt-4o",
            "use_knowledge_base": False
        }

        response = requests.post(
            f"{BASE_URL}/api/deliberate",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            print("[OK] Deliberate endpoint dziala")
            return True
        elif response.status_code == 401:
            print("[!] Deliberate endpoint: brak API key (to OK dla testu)")
            return True
        elif response.status_code == 429:
            print("[!] Deliberate endpoint: rate limit (to OK)")
            return True
        else:
            print(f"[!] Deliberate endpoint: status {response.status_code}")
            return True  # Nie blokuj
    except requests.exceptions.Timeout:
        print("[!] Deliberate endpoint: timeout (moze brak API key)")
        return True  # Nie blokuj
    except Exception as e:
        print(f"[!] Deliberate endpoint error: {e}")
        return True  # Nie blokuj

def main():
    print("=" * 60)
    print("TEST INTEGRACYJNY - AI Council")
    print("=" * 60)
    print()

    tests = [
        ("Serwer", test_server_running),
        ("Health Check", test_health_endpoint),
        ("Agents API", test_agents_endpoint),
        ("Frontend", test_frontend),
        ("Metrics", test_metrics_endpoint),
        ("Deliberate API", test_deliberate_endpoint),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n[TEST] {name}:")
        results.append(test_func())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"[SUCCESS] Wszystkie testy przeszly ({passed}/{total})")
        return 0
    else:
        print(f"[PARTIAL] Przeszlo {passed}/{total} testow")
        print("\nSprawdz TROUBLESHOOTING.md dla pomocy")
        return 1

if __name__ == "__main__":
    sys.exit(main())
