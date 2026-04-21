@echo off
REM ============================================
REM AI COUNCIL - Quick Diagnostic
REM ============================================

echo.
echo ============================================
echo AI COUNCIL - Diagnostyka
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python nie jest zainstalowany!
    echo     Pobierz: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python zainstalowany
echo.

REM Run check_setup
echo Uruchamiam pelna diagnostyke...
echo.
python check_setup.py

echo.
echo ============================================
echo Nacisnij dowolny klawisz aby zamknac...
pause >nul
