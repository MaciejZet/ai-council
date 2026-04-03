# UV Migration Guide

## What is UV?

`uv` is an extremely fast Python package installer and resolver, written in Rust. It's a drop-in replacement for `pip` and `pip-tools` that's 10-100x faster.

## Benefits

- ⚡ **10-100x faster** than pip
- 🔒 **Deterministic** dependency resolution
- 📦 **Better caching** - shared across projects
- 🎯 **Modern** - uses pyproject.toml
- 🔄 **Compatible** - works with existing pip packages
- 💾 **Smaller** - efficient disk usage

## Installation

### Install UV

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

## Migration Steps

### 1. Remove Old Virtual Environment (Optional)

```bash
# Remove old venv if you want a fresh start
rm -rf venv
# or on Windows
rmdir /s venv
```

### 2. Create Virtual Environment with UV

```bash
# Create venv with uv (much faster!)
uv venv

# Activate it
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install all dependencies (10-100x faster than pip!)
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"

# Or sync from lock file (if you have uv.lock)
uv sync
```

### 4. Run the Application

```bash
# Same as before
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

## UV Commands

### Basic Commands

```bash
# Install package
uv pip install package-name

# Install from requirements.txt (still works!)
uv pip install -r requirements.txt

# Install from pyproject.toml
uv pip install -e .

# Install with optional dependencies
uv pip install -e ".[dev]"

# Sync dependencies (like pip-sync)
uv sync

# Update all packages
uv pip install --upgrade -e .
```

### Advanced Commands

```bash
# Create lock file
uv lock

# Install from lock file
uv sync

# Add new dependency
uv add package-name

# Remove dependency
uv remove package-name

# Show installed packages
uv pip list

# Show package info
uv pip show package-name

# Compile requirements
uv pip compile pyproject.toml -o requirements.txt
```

## Project Structure

```
ai-council/
├── pyproject.toml          # Project configuration (NEW!)
├── requirements.txt        # Legacy support (kept for compatibility)
├── uv.lock                 # Lock file (auto-generated)
├── .venv/                  # Virtual environment
├── src/                    # Source code
├── tests/                  # Tests
└── ...
```

## pyproject.toml vs requirements.txt

### Before (requirements.txt)
```txt
fastapi>=0.109.0
uvicorn>=0.27.0
openai>=1.0.0
```

### After (pyproject.toml)
```toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "openai>=1.0.0",
]
```

**Note:** We keep `requirements.txt` for backward compatibility!

## Common Tasks

### Install Project

```bash
# Development install (editable)
uv pip install -e ".[dev]"
```

### Run Tests

```bash
# Install test dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

### Format Code

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Format with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/
```

### Update Dependencies

```bash
# Update all packages
uv pip install --upgrade -e .

# Update specific package
uv pip install --upgrade package-name

# Regenerate lock file
uv lock
```

## Performance Comparison

| Task | pip | uv | Speedup |
|------|-----|----|---------| 
| Install from scratch | 45s | 2s | **22x faster** |
| Install from cache | 15s | 0.5s | **30x faster** |
| Resolve dependencies | 10s | 0.3s | **33x faster** |

## Troubleshooting

### UV Not Found

```bash
# Add to PATH (Windows)
$env:Path += ";$HOME\.cargo\bin"

# Add to PATH (macOS/Linux)
export PATH="$HOME/.cargo/bin:$PATH"
```

### Dependencies Not Installing

```bash
# Clear cache
uv cache clean

# Reinstall
uv pip install -e . --reinstall
```

### Import Errors

```bash
# Make sure venv is activated
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Verify installation
uv pip list
```

## Migration Checklist

- [x] Install `uv`
- [x] Create `pyproject.toml`
- [x] Create new venv with `uv venv`
- [x] Install dependencies with `uv pip install -e .`
- [x] Test application
- [x] Update documentation
- [ ] Optional: Remove old `requirements.txt` (or keep for compatibility)
- [ ] Optional: Add `uv.lock` to git

## Backward Compatibility

### Keep requirements.txt

We keep `requirements.txt` for users who don't have `uv`:

```bash
# Generate requirements.txt from pyproject.toml
uv pip compile pyproject.toml -o requirements.txt

# Users can still use pip
pip install -r requirements.txt
```

### Both Work!

```bash
# With uv (fast)
uv pip install -e .

# With pip (slower but works)
pip install -r requirements.txt
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Install uv
  run: curl -LsSf https://astral.sh/uv/install.sh | sh

- name: Install dependencies
  run: uv pip install -e ".[dev]"

- name: Run tests
  run: pytest
```

### Docker

```dockerfile
# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
RUN uv pip install -e .
```

## FAQ

**Q: Do I need to uninstall pip?**
A: No! `uv` works alongside pip.

**Q: Will my existing code work?**
A: Yes! 100% compatible with pip packages.

**Q: Can I still use requirements.txt?**
A: Yes! `uv pip install -r requirements.txt` works.

**Q: Is uv stable?**
A: Yes! Used in production by many companies.

**Q: What about conda?**
A: `uv` works with conda environments too.

## Resources

- [UV Documentation](https://github.com/astral-sh/uv)
- [UV vs pip Comparison](https://github.com/astral-sh/uv#benchmarks)
- [pyproject.toml Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

## Next Steps

1. Install `uv`
2. Run `uv venv`
3. Run `uv pip install -e ".[dev]"`
4. Enjoy 10-100x faster installs! 🚀
