@echo off
REM Quick starter for Windows
echo ============================================
echo AI COUNCIL - Windows Starter
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python nie jest zainstalowany!
    echo Pobierz z: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Run the smart starter
python start.py

pause
