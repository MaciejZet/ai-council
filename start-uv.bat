@echo off
REM AI Council - Quick Start with uv (lockfile + dev extras)
setlocal EnableDelayedExpansion

echo.
echo AI Council - Quick Start with uv
echo ====================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo UV not found. Installing...
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
)

echo Checking Python (uv will use .python-version / project settings^)...
echo.

REM Install project + dev tools from uv.lock (deterministic)
echo Syncing dependencies: uv sync --extra dev
uv sync --extra dev
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: uv sync failed.
    exit /b 1
)
echo.
echo Dependencies synced.
echo.

if not exist ".env" (
    echo No .env file. Copying from .env.example...
    copy .env.example .env
    echo Edit .env and add your API keys.
    echo.
)

echo Optional: Redis for response cache (REDIS_URL in .env^)
where redis-cli >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    redis-cli ping >nul 2>nul
    if !ERRORLEVEL! EQU 0 ( echo Redis: OK ) else ( echo Redis: installed but not running )
) else (
    echo Redis: not in PATH ^(optional^)
)
echo.

set /p run_tests="Run tests? (y/N): "
if /i "!run_tests!"=="y" (
    uv run pytest tests/ -v
    echo.
)

echo Starting server at http://localhost:8000
echo Press Ctrl+C to stop.
echo.

uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
