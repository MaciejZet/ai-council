@echo off
REM AI Council - Quick Start Script with UV (Windows)
REM Automatically sets up the environment and runs the application

echo.
echo 🚀 AI Council - Quick Start with UV
echo ====================================
echo.

REM Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ UV not found. Installing UV...
    echo.
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    echo ✅ UV installed successfully!
    echo.
)

REM Check Python version
echo 🔍 Checking Python version...
python --version
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo 📦 Creating virtual environment with UV...
    uv venv
    echo ✅ Virtual environment created!
    echo.
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call .venv\Scripts\activate.bat
echo ✅ Virtual environment activated!
echo.

REM Install dependencies
echo 📥 Installing dependencies with UV (this is fast!)...
uv pip install -e ".[dev]"
echo ✅ Dependencies installed!
echo.

REM Check if .env exists
if not exist ".env" (
    echo ⚠️  No .env file found. Creating from .env.example...
    copy .env.example .env
    echo ✅ .env file created!
    echo.
    echo ⚠️  IMPORTANT: Edit .env and add your API keys!
    echo.
)

REM Check Redis (optional)
echo 🔍 Checking Redis (optional for caching)...
where redis-cli >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    redis-cli ping >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo ✅ Redis is running!
    ) else (
        echo ⚠️  Redis installed but not running. Start with: redis-server
    )
) else (
    echo ℹ️  Redis not installed (optional). Install for caching support.
)
echo.

REM Run tests (optional)
set /p run_tests="🧪 Run tests? (y/N): "
if /i "%run_tests%"=="y" (
    echo.
    echo 🧪 Running tests...
    pytest tests/ -v
    echo.
)

REM Start the application
echo 🎉 Setup complete! Starting AI Council...
echo.
echo 📍 Application will be available at: http://localhost:8000
echo 📍 API docs at: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
