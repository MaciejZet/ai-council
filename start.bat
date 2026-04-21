@echo off
REM Quick starter for Windows (uv + uvicorn)
setlocal EnableDelayedExpansion
echo ============================================
echo AI COUNCIL - Windows Starter
echo ============================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Instalacja uv...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
)

where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Nie udalo sie uruchomic uv. Zobacz: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

uv run python start.py
set EXITCODE=%ERRORLEVEL%
pause
exit /b %EXITCODE%
