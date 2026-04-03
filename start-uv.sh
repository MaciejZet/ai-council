#!/bin/bash
# AI Council - Quick Start Script with UV
# Automatically sets up the environment and runs the application

set -e

echo "🚀 AI Council - Quick Start with UV"
echo "===================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV not found. Installing UV..."
    echo ""

    # Detect OS and install
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows
        powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    else
        # macOS/Linux
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi

    echo ""
    echo "✅ UV installed successfully!"
    echo ""
fi

# Check Python version
echo "🔍 Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "   Python $python_version"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment with UV..."
    uv venv
    echo "✅ Virtual environment created!"
    echo ""
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
echo "✅ Virtual environment activated!"
echo ""

# Install dependencies
echo "📥 Installing dependencies with UV (this is fast!)..."
uv pip install -e ".[dev]"
echo "✅ Dependencies installed!"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ .env file created!"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys!"
    echo ""
fi

# Check Redis (optional)
echo "🔍 Checking Redis (optional for caching)..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis is running!"
    else
        echo "⚠️  Redis installed but not running. Start with: redis-server"
    fi
else
    echo "ℹ️  Redis not installed (optional). Install for caching support."
fi
echo ""

# Run tests (optional)
read -p "🧪 Run tests? (y/N): " run_tests
if [[ $run_tests =~ ^[Yy]$ ]]; then
    echo ""
    echo "🧪 Running tests..."
    pytest tests/ -v
    echo ""
fi

# Start the application
echo "🎉 Setup complete! Starting AI Council..."
echo ""
echo "📍 Application will be available at: http://localhost:8000"
echo "📍 API docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
