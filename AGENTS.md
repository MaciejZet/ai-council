## Learned User Preferences

- When the user asks for broad analysis, improvements, or fixes across the stack, prefer shipping concrete changes and verification over long rounds of clarifying questions.
- The user often writes requirements and feedback in Polish; respond in the same language they use for that thread.

## Learned Workspace Facts

- Python dependencies in this repo are managed with uv: `pyproject.toml` is the source of truth; use `uv sync --extra dev` (or `start-uv.bat` / `start-uv.sh`). The default app entry is `uv run uvicorn main:app` on port 8000; `start.py` / `start.bat` / `start.sh` prefer `uv run` when `uv` is on PATH. `requirements.txt` is a legacy pip mirror, not the primary install path. Use Python 3.12+ locally (`check_setup.py` matches `pyproject.toml`).
- OpenRouter model lists for the UI/API are populated from OpenRouter's public models catalog (`GET` on the configured base URL's `/models` path) with a short server-side TTL cache; an API key is not required to fetch the catalog, but is still required for actual chat/completions calls. `GET /api/providers` may include `openrouter_catalog` entries with `id` and `tier` (free/cheap/standard/premium) for tabbed filtering in the model dropdown; when the user selects OpenRouter, the default model prefers a free-tier entry when one exists in the catalog.
- Non-chat `/api/deliberate` responses can be served from Redis-backed caching when Redis is available and connected; cache keys are designed to include a strong fingerprint of attachment payloads, not just the query text.
- Keep Cursor IDE state out of Git: do not commit `.cursor/` or machine-specific absolute paths; local hooks and paths should remain ignored and off the remote history.
