# Private Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `MaciejZet/ai-council` safe as a public repository while synchronizing an explicitly allowlisted private Google Drive library into a private Pinecone namespace that Council can retrieve from without committing source content.

**Architecture:** Google Drive is the private source of truth. A local/admin-only sync command uses read-only Drive credentials, exports or downloads allowlisted files, passes their text through the existing chunking/embedding pipeline, and writes vectors plus provenance into a dedicated Pinecone namespace. Council runtime reads Pinecone only. Git, CI and normal logs contain no private source text.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, `google-api-python-client`, `google-auth`, OpenAI embeddings, Pinecone Python SDK, pytest, uv, Ruff.

## Global Constraints

- Public Git may contain code, schemas, book titles, authors and framework identifiers, but no PDFs/ebooks, book summaries, highlights, annotations, extracted source text, private retrieval chunks, embeddings, Drive exports, or ingestion caches.
- Google Drive access is read-only and limited to an explicit allowlist of folder IDs and file IDs.
- Private Drive credentials and allowlist configuration remain outside Git.
- Private vectors use `PINECONE_PRIVATE_NAMESPACE`; existing public/demo ingestion may continue using its current default namespace behavior.
- Normal logs contain technical IDs, counts, timings and error codes only. Source text is never logged. Private source titles are logged only when `PRIVATE_KNOWLEDGE_DEBUG_TITLES=true`.
- CI runs without Google Drive, Pinecone or production LLM credentials and uses synthetic fixtures only.
- The app starts and deliberates when private knowledge is unavailable.
- A knowledge outage is represented as `unavailable`; the system never implies that private sources were consulted.
- Adding or changing a Drive source requires no Git commit.
- Existing public API behavior remains backward-compatible except for additive optional status fields.

## File map

### Create

- `src/knowledge/private_models.py`
- `src/knowledge/private_config.py`
- `src/knowledge/drive_source.py`
- `src/knowledge/private_sync.py`
- `scripts/sync_private_knowledge.py`
- `scripts/check_private_corpus.py`
- `tests/test_private_config.py`
- `tests/test_drive_source.py`
- `tests/test_private_sync.py`
- `tests/test_private_retrieval.py`
- `tests/test_private_corpus_guard.py`
- `docs/PRIVATE_KNOWLEDGE.md`

### Modify

- `.gitignore`
- `.env.example`
- `pyproject.toml`
- `uv.lock`
- `src/knowledge/ingest.py`
- `src/knowledge/retriever.py`
- `src/council/orchestrator.py`
- `.github/workflows/ci.yml`
- `README.md`

---

### Task 1: Enforce the public/private repository boundary

**Files:**
- Modify: `.gitignore`
- Create: `scripts/check_private_corpus.py`
- Create: `tests/test_private_corpus_guard.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `check_paths(paths: Iterable[str]) -> list[str]`
- CLI: `python scripts/check_private_corpus.py [--tracked-only]`, exit `0` when safe and `1` on violations.

- [ ] **Step 1: Write the failing tests**

```python
from scripts.check_private_corpus import check_paths


def test_guard_rejects_private_working_paths():
    violations = check_paths([
        "private_knowledge/export.txt",
        "drive_exports/book.pdf",
        ".private_knowledge/state.json",
    ])
    assert len(violations) == 3


def test_guard_rejects_ebook_formats_anywhere():
    assert check_paths(["assets/book.epub"])
    assert check_paths(["docs/library.azw3"])


def test_guard_allows_public_docs_and_test_pdf():
    assert check_paths([
        "docs/architecture.md",
        "tests/fixtures/public-domain-sample.pdf",
    ]) == []
```

- [ ] **Step 2: Verify the tests fail**

```bash
uv run pytest tests/test_private_corpus_guard.py -v --no-cov
```

Expected: import failure because `scripts/check_private_corpus.py` does not exist.

- [ ] **Step 3: Implement the guard**

Use this implementation shape:

```python
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path, PurePosixPath
from typing import Iterable

FORBIDDEN_PREFIXES = (
    "books_pdf/",
    "private_knowledge/",
    "knowledge_private/",
    "drive_exports/",
    "ingestion_cache/",
    ".private_knowledge/",
)
FORBIDDEN_EXTENSIONS = {".epub", ".mobi", ".azw", ".azw3"}


def check_paths(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for raw in paths:
        normalized = raw.replace("\\", "/").lstrip("./")
        suffix = PurePosixPath(normalized).suffix.lower()
        if normalized.startswith(FORBIDDEN_PREFIXES) or suffix in FORBIDDEN_EXTENSIONS:
            violations.append(normalized)
    return sorted(set(violations))


def git_paths(args: list[str]) -> list[str]:
    output = subprocess.check_output(["git", *args], text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracked-only", action="store_true")
    parsed = parser.parse_args()
    paths = git_paths(["ls-files"])
    if not parsed.tracked_only:
        paths.extend(git_paths(["diff", "--cached", "--name-only"]))
    violations = check_paths(paths)
    for path in violations:
        print(path)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The script inspects path names only and never opens or prints file content.

- [ ] **Step 4: Strengthen `.gitignore`**

```gitignore
# Private knowledge corpus and local sync state
books_pdf/
private_knowledge/
knowledge_private/
drive_exports/
ingestion_cache/
.private_knowledge/
*.epub
*.mobi
*.azw
*.azw3
```

Do not ignore `*.pdf` globally because public documentation/test PDFs are valid repository assets.

- [ ] **Step 5: Add the guard to CI before pytest**

```yaml
      - name: Public repository corpus guard
        run: uv run python scripts/check_private_corpus.py --tracked-only
```

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest tests/test_private_corpus_guard.py -v --no-cov
uv run python scripts/check_private_corpus.py --tracked-only
git add .gitignore .github/workflows/ci.yml scripts/check_private_corpus.py tests/test_private_corpus_guard.py
git commit -m "security: enforce private knowledge repository boundary"
```

---

### Task 2: Add typed private configuration and metadata

**Files:**
- Create: `src/knowledge/private_models.py`
- Create: `src/knowledge/private_config.py`
- Create: `tests/test_private_config.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `DriveAllowlistEntry`, `DriveAllowlist`, `PrivateSourceMetadata`, `KnowledgeRetrievalResult`, `PrivateKnowledgeConfig.from_env()`.

- [ ] **Step 1: Write failing tests**

```python
from src.knowledge.private_config import PrivateKnowledgeConfig


def test_private_config_is_disabled_without_allowlist(monkeypatch):
    monkeypatch.delenv("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE", raising=False)
    cfg = PrivateKnowledgeConfig.from_env()
    assert cfg.enabled is False


def test_app_config_does_not_require_drive_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("PINECONE_PRIVATE_NAMESPACE", "private-test")
    cfg = PrivateKnowledgeConfig.from_env()
    assert cfg.pinecone_namespace == "private-test"
```

Add a test that writes this synthetic allowlist to `tmp_path` and parses it successfully:

```json
{
  "files": [
    {
      "id": "synthetic-file-id",
      "source_type": "synthesis",
      "domains": ["strategy"],
      "experts": ["strategy"],
      "framework_tags": ["test-framework"]
    }
  ],
  "folders": []
}
```

- [ ] **Step 2: Verify failure**

```bash
uv run pytest tests/test_private_config.py -v --no-cov
```

- [ ] **Step 3: Implement the models**

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

SourceType = Literal[
    "book", "summary", "personal_note", "synthesis", "internal_doc",
    "article", "ogólne", "web", "notion", "file",
]
KnowledgeStatus = Literal["ok", "no_matches", "disabled", "unavailable"]


class DriveAllowlistEntry(BaseModel):
    id: str
    source_type: SourceType = "book"
    domains: list[str] = Field(default_factory=list)
    experts: list[str] = Field(default_factory=list)
    framework_tags: list[str] = Field(default_factory=list)
    recursive: bool = True


class DriveAllowlist(BaseModel):
    files: list[DriveAllowlistEntry] = Field(default_factory=list)
    folders: list[DriveAllowlistEntry] = Field(default_factory=list)


class PrivateSourceMetadata(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    language: str
    domains: list[str] = Field(default_factory=list)
    experts: list[str] = Field(default_factory=list)
    framework_tags: list[str] = Field(default_factory=list)
    drive_file_id: str
    content_hash: str
    modified_time: str | None = None


class KnowledgeRetrievalResult(BaseModel):
    status: KnowledgeStatus
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
```

- [ ] **Step 4: Implement environment configuration**

`PrivateKnowledgeConfig` is a frozen dataclass with fields:

```python
allowlist_file: Path | None
state_file: Path
pinecone_namespace: str
debug_titles: bool
enabled: bool
```

`from_env()` uses these exact defaults:

```text
PRIVATE_KNOWLEDGE_STATE_FILE=.private_knowledge/state.json
PINECONE_PRIVATE_NAMESPACE=private-library
PRIVATE_KNOWLEDGE_DEBUG_TITLES=false
```

It must not validate Google credentials. Add `load_allowlist() -> DriveAllowlist`, which reads JSON only when an allowlist path is configured.

- [ ] **Step 5: Update `.env.example`**

```env
# Private knowledge sync (optional; local/admin use only)
# GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/outside/repo/drive-readonly.json
# PRIVATE_KNOWLEDGE_ALLOWLIST_FILE=/absolute/path/outside/repo/private-knowledge-allowlist.json
# PRIVATE_KNOWLEDGE_STATE_FILE=.private_knowledge/state.json
PINECONE_PRIVATE_NAMESPACE=private-library
PRIVATE_KNOWLEDGE_DEBUG_TITLES=false
```

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest tests/test_private_config.py -v --no-cov
git add .env.example src/knowledge/private_models.py src/knowledge/private_config.py tests/test_private_config.py
git commit -m "feat: add private knowledge configuration models"
```

---

### Task 3: Make ingestion reusable, namespace-aware and failure-safe

**Files:**
- Modify: `src/knowledge/ingest.py`
- Create: `tests/test_private_sync.py`

**Interfaces:**
- Produces:
  - `content_sha256(content: bytes | str) -> str`
  - `stable_doc_id(source_kind: str, source_id: str) -> str`
  - `generate_chunk_id(doc_id: str, content_hash: str, chunk_index: int) -> str`
  - `upsert_text_document(text: str, metadata: PrivateSourceMetadata, *, namespace: str | None = None, batch_size: int = 100) -> dict[str, Any]`

- [ ] **Step 1: Write failing core tests**

Use a fake Pinecone index and monkeypatch `get_embeddings()` to return deterministic vectors. Assert that `upsert_text_document()` passes `namespace="private-test"`, stores the metadata fields below, and does not call delete when an upsert raises.

Required vector metadata:

```python
{
    "text": "synthetic chunk",
    "title": "Synthetic Source",
    "source_type": "book",
    "language": "en",
    "domains": ["strategy"],
    "experts": ["strategy"],
    "framework_tags": ["synthetic-framework"],
    "chunk_index": 0,
    "total_chunks": 1,
    "doc_id": "stable-id",
    "content_hash": "content-hash",
    "embedding_version": "v2",
}
```

- [ ] **Step 2: Verify failure**

```bash
uv run pytest tests/test_private_sync.py -k "ingest or stable or namespace" -v --no-cov
```

- [ ] **Step 3: Add deterministic identity helpers**

```python
def content_sha256(content: bytes | str) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def stable_doc_id(source_kind: str, source_id: str) -> str:
    return hashlib.sha256(f"{source_kind}:{source_id}".encode("utf-8")).hexdigest()[:28]


def generate_chunk_id(doc_id: str, content_hash: str, chunk_index: int) -> str:
    raw = f"{doc_id}:{content_hash}:{chunk_index}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```

- [ ] **Step 4: Add `upsert_text_document()`**

Reuse existing `chunk_text()`, `get_embeddings()` and `get_pinecone_index()`. Build all new vectors and call:

```python
index.upsert(vectors=batch, namespace=namespace)
```

when `namespace` is not `None`. After every batch succeeds, remove stale versions only:

```python
stale_filter = {
    "$and": [
        {"doc_id": {"$eq": metadata.doc_id}},
        {"content_hash": {"$ne": metadata.content_hash}},
    ]
}
index.delete(filter=stale_filter, namespace=namespace)
```

If an upsert raises, propagate the error and do not call delete.

- [ ] **Step 5: Keep `ingest_pdf()` backward-compatible**

`ingest_pdf()` continues to accept the existing arguments. It extracts text, builds metadata, and delegates to `upsert_text_document()`. Do not store `source_path` in new vector metadata.

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest tests/test_private_sync.py -v --no-cov
git add src/knowledge/ingest.py tests/test_private_sync.py
git commit -m "refactor: add namespace-safe knowledge ingestion"
```

---

### Task 4: Add the read-only allowlist Drive adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/knowledge/drive_source.py`
- Create: `tests/test_drive_source.py`

**Interfaces:**
- Produces `DriveSourceRecord` and `DriveSourceClient`.

```python
@dataclass(frozen=True)
class DriveSourceRecord:
    file_id: str
    name: str
    mime_type: str
    modified_time: str | None
    md5_checksum: str | None
    allowlist_entry: DriveAllowlistEntry
```

Required client methods:

```python
class DriveSourceClient:
    def list_allowed(self, allowlist: DriveAllowlist) -> list[DriveSourceRecord]:
        raise NotImplementedError

    def read_bytes(self, record: DriveSourceRecord) -> bytes:
        raise NotImplementedError
```

The `NotImplementedError` bodies above define the interface only; the implementation step below replaces them in the production file.

- [ ] **Step 1: Add dependencies and lock them**

Add:

```toml
"google-api-python-client>=2.0.0",
"google-auth>=2.0.0",
```

Then:

```bash
uv lock
uv sync --extra dev
```

- [ ] **Step 2: Write mocked tests**

No test may call Google. Cover explicit file IDs, children of allowlisted folders, recursive descent limited to those folders, rejection of files outside the allowlist, binary PDF download, Google Docs export as UTF-8 text bytes, and unsupported MIME type handling.

- [ ] **Step 3: Verify failure**

```bash
uv run pytest tests/test_drive_source.py -v --no-cov
```

- [ ] **Step 4: Implement lazy read-only Drive access**

Build the service only inside `DriveSourceClient.__init__()` or a private lazy getter:

```python
import google.auth
from googleapiclient.discovery import build

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"

credentials, _ = google.auth.default(scopes=[DRIVE_READONLY_SCOPE])
service = build("drive", "v3", credentials=credentials, cache_discovery=False)
```

Folder listing uses a parent-bound query:

```python
query = f"'{folder_id}' in parents and trashed = false"
```

Request only:

```text
id,name,mimeType,modifiedTime,md5Checksum,parents
```

Binary files use `files().get_media(fileId=record.file_id)`. Google Docs with MIME type `application/vnd.google-apps.document` use `files().export_media(fileId=record.file_id, mimeType="text/plain")`. Read bytes with `MediaIoBaseDownload` into `io.BytesIO`.

Never issue an account-wide list query without an allowlisted parent.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/test_drive_source.py -v --no-cov
git add pyproject.toml uv.lock src/knowledge/drive_source.py tests/test_drive_source.py
git commit -m "feat: add allowlist-only Google Drive source"
```

---

### Task 5: Implement idempotent Drive-to-Pinecone sync

**Files:**
- Create: `src/knowledge/private_sync.py`
- Modify: `tests/test_private_sync.py`
- Create: `scripts/sync_private_knowledge.py`

**Interfaces:**
- Produces:
  - `PrivateKnowledgeSync.sync(dry_run: bool = False) -> SyncReport`
  - CLI `uv run python scripts/sync_private_knowledge.py [--dry-run]`

- [ ] **Step 1: Add failing behavior tests**

Use synthetic bytes only. Verify:

1. same `remote_version` is skipped;
2. changed source is fetched, SHA-256 hashed and ingested;
3. Google Docs decode UTF-8 directly;
4. PDFs are written only inside `tempfile.TemporaryDirectory()` and passed to existing PDF extraction;
5. failed upsert does not advance state;
6. state contains IDs, versions, hashes, timestamps and chunk counts only;
7. captured logs contain neither the synthetic private sentence nor the synthetic source title while debug titles are off.

- [ ] **Step 2: Implement state loading and atomic saving**

State schema:

```json
{
  "version": 1,
  "documents": {
    "synthetic-drive-file-id": {
      "doc_id": "synthetic-doc-id",
      "remote_version": "2026-08-15T12:00:00Z",
      "content_hash": "sha256-value",
      "last_ingested_at": "2026-08-15T12:05:00Z",
      "chunks": 12
    }
  }
}
```

Save with a sibling temporary file and `Path.replace()` so a failed write does not corrupt the previous state.

- [ ] **Step 3: Implement the sync loop**

For each `DriveSourceRecord`:

```python
remote_version = record.md5_checksum or record.modified_time or "unknown"
previous = state.documents.get(record.file_id)
if previous is not None and previous.remote_version == remote_version:
    report.skipped += 1
    continue
```

For changed/new sources:

```python
payload = drive.read_bytes(record)
content_hash = content_sha256(payload)
doc_id = stable_doc_id("gdrive", record.file_id)
```

For Google Docs:

```python
text = payload.decode("utf-8")
```

For PDF records, write `payload` into a `TemporaryDirectory()` path and call `extract_text_from_pdf()`; never use a repository-relative temp path.

Create `PrivateSourceMetadata` from allowlist metadata, detected language, `doc_id`, `record.name`, `record.file_id`, `content_hash`, and `record.modified_time`. Call:

```python
upsert_text_document(
    text,
    metadata,
    namespace=config.pinecone_namespace,
)
```

Update in-memory state only after that call returns successfully.

- [ ] **Step 4: Implement CLI behavior**

The CLI loads `PrivateKnowledgeConfig`, requires an allowlist path, constructs `DriveSourceClient`, and runs sync. `--dry-run` lists only counts and technical file IDs and does not download, embed, write state or mutate Pinecone.

Printed report fields:

```text
scanned
skipped
updated
failed
failed_doc_ids
```

No source text is printed. Source titles are printed only in debug-title mode.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest tests/test_private_sync.py -v --no-cov
git add src/knowledge/private_sync.py scripts/sync_private_knowledge.py tests/test_private_sync.py
git commit -m "feat: sync private Drive knowledge into Pinecone"
```

---

### Task 6: Add private retrieval filters, provenance and explicit health

**Files:**
- Modify: `src/knowledge/retriever.py`
- Modify: `src/council/orchestrator.py`
- Create: `tests/test_private_retrieval.py`
- Modify: `tests/test_council.py`

**Interfaces:**
- Produces:
  - `query_knowledge_result(query: str, top_k: int = 5, category: str | None = None, source_type: str | None = None, domains: list[str] | None = None, experts: list[str] | None = None, min_score: float = 0.3, hybrid: bool = False, namespace: str | None = None) -> KnowledgeRetrievalResult`
  - backward-compatible `query_knowledge()` returning only `.chunks`.
- `CouncilDeliberation` gains `knowledge_status: str = "disabled"` and `knowledge_error_code: str | None = None`.

- [ ] **Step 1: Write failing retrieval tests**

With fake Pinecone results, call:

```python
result = query_knowledge_result(
    "synthetic pricing question",
    domains=["pricing"],
    experts=["monetization"],
    namespace="private-test",
)
```

Assert the Pinecone call contains `namespace="private-test"` and this filter shape:

```python
{
    "$and": [
        {"domains": {"$in": ["pricing"]}},
        {"experts": {"$in": ["monetization"]}},
    ]
}
```

Also test `source_type="synthesis"`, `unavailable` on missing configuration/query errors, `no_matches` for an empty successful query, `ok` for matches, and legacy `query_knowledge()` list behavior.

- [ ] **Step 2: Build filters without overwriting constraints**

Represent each active constraint as one clause:

```python
clauses: list[dict[str, Any]] = []
if source_type:
    clauses.append({"source_type": {"$eq": source_type}})
if category:
    clauses.append({"category": {"$eq": category}})
if domains:
    clauses.append({"domains": {"$in": domains}})
if experts:
    clauses.append({"experts": {"$in": experts}})
filter_dict = {"$and": clauses} if len(clauses) > 1 else (clauses[0] if clauses else None)
```

Pass `namespace=namespace` to `index.query()` when provided.

- [ ] **Step 3: Preserve provenance for agents**

`format_context_for_agent(chunks, include_provenance=True)` returns compact internal blocks:

```text
[SOURCE]
title: Synthetic Source
source_type: synthesis
doc_id: synthetic-doc-id
chunk: 4
score: 0.82

Synthetic retrieved text used only by the model prompt.
```

Do not include local filesystem paths or credential data.

`format_sources_for_display()` returns title, source type, category/domain, chunk indices and scores. Remove the current default 300-character text excerpts; add `include_excerpt: bool = False` only if compatibility requires the field.

- [ ] **Step 4: Add structured retrieval status**

`query_knowledge_result()` maps outcomes as follows:

```text
valid query + matches -> ok
valid query + zero matches -> no_matches
knowledge intentionally disabled by caller -> disabled
missing embedding/Pinecone config or Pinecone query failure -> unavailable
```

Keep `query_knowledge()` as:

```python
def query_knowledge(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    return query_knowledge_result(*args, **kwargs).chunks
```

If the existing signature must remain explicit for type checking, copy its existing parameters and append the new optional parameters instead of using variadic arguments.

- [ ] **Step 5: Propagate status through Council**

Update `Council._get_context()` to return texts, display sources, status and error code. Do not log private chunks or titles.

For normal deliberation, `unavailable` means agents continue without private context and `CouncilDeliberation.knowledge_status == "unavailable"`.

For `kb_only`, distinguish:

```text
no_matches -> "Nie znaleziono pasujących źródeł w bazie wiedzy."
unavailable -> "Prywatna baza wiedzy jest obecnie niedostępna; źródła nie zostały zweryfikowane."
```

- [ ] **Step 6: Verify and commit**

```bash
uv run pytest tests/test_private_retrieval.py tests/test_council.py -v --no-cov
git add src/knowledge/retriever.py src/council/orchestrator.py tests/test_private_retrieval.py tests/test_council.py
git commit -m "feat: add private expert-aware retrieval status"
```

---

### Task 7: Document, run full verification and prepare for merge

**Files:**
- Create: `docs/PRIVATE_KNOWLEDGE.md`
- Modify: `README.md`
- Modify only defects found by verification.

- [ ] **Step 1: Write operator documentation**

Use a placeholder-only allowlist example:

```json
{
  "folders": [
    {
      "id": "DRIVE_FOLDER_ID",
      "source_type": "book",
      "domains": ["strategy"],
      "experts": ["strategy"],
      "framework_tags": [],
      "recursive": true
    }
  ],
  "files": [
    {
      "id": "DRIVE_DOCUMENT_ID",
      "source_type": "synthesis",
      "domains": ["strategy", "marketing"],
      "experts": ["strategy", "marketing"],
      "framework_tags": [],
      "recursive": false
    }
  ]
}
```

Document that this JSON lives outside the repository. Document:

```bash
uv run python scripts/sync_private_knowledge.py --dry-run
uv run python scripts/sync_private_knowledge.py
```

State explicitly that books, summaries, Drive exports, chunks and private state must not be committed to Git, tests, PR descriptions or public issue attachments.

- [ ] **Step 2: Update README**

Link to `docs/PRIVATE_KNOWLEDGE.md`. Keep generic local PDF import documented only as a runtime capability; do not suggest storing books inside the repository.

- [ ] **Step 3: Run lint and focused tests**

```bash
uv run ruff check src/knowledge scripts tests
uv run pytest \
  tests/test_private_config.py \
  tests/test_drive_source.py \
  tests/test_private_sync.py \
  tests/test_private_retrieval.py \
  tests/test_private_corpus_guard.py \
  tests/test_council.py \
  -v --tb=short --no-cov
```

Expected: exit code `0` for both commands with no external credentials.

- [ ] **Step 4: Run the full regression suite and repository guard**

```bash
uv run pytest tests/ -v --tb=short --no-cov
uv run python tests/quality_gate.py
uv run python scripts/check_private_corpus.py --tracked-only
```

Expected: all commands exit `0`.

- [ ] **Step 5: Verify tracked-file safety**

```bash
git diff main...HEAD -- .env .env.example
git ls-files | grep -E '(^|/)(private_knowledge|knowledge_private|drive_exports|ingestion_cache|books_pdf|\.private_knowledge)/' && exit 1 || true
git ls-files | grep -Ei '\.(epub|mobi|azw|azw3)$' && exit 1 || true
```

Expected: `.env.example` contains placeholders only and both tracked-file searches return no matches.

- [ ] **Step 6: Perform one authorized local smoke sync**

On a machine with private Drive/Pinecone/embedding credentials:

```bash
uv run python scripts/sync_private_knowledge.py --dry-run
uv run python scripts/sync_private_knowledge.py
```

Success means allowlisted sources are processed into `PINECONE_PRIVATE_NAMESPACE`, state remains under `.private_knowledge/`, and `git status --short` contains no private corpus/export/state files.

Do not paste Drive IDs, source text, credentials, state contents or retrieved passages into a public PR.

- [ ] **Step 7: Commit documentation or verification fixes**

```bash
git add docs/PRIVATE_KNOWLEDGE.md README.md
git commit -m "docs: document private Drive knowledge workflow"
```

If verification required code fixes, commit each fix with the affected test before this documentation commit.

---

## Acceptance checklist

- [ ] Fresh clone contains no private corpus, summaries, notes, chunks or embeddings.
- [ ] CI passes without production secrets.
- [ ] Drive traversal cannot escape explicit files/folders in the allowlist.
- [ ] Google Docs exports and PDF temporary files never land in the repo working tree.
- [ ] Private vectors use `PINECONE_PRIVATE_NAMESPACE`.
- [ ] Refresh writes the new vector version before deleting old versions.
- [ ] Sync state contains only IDs, hashes, remote versions, timestamps and counts.
- [ ] Normal logs contain no private text and no source titles by default.
- [ ] Retrieval filters by domain, expert and source type and keeps provenance for the model.
- [ ] Council reports `unavailable` on retrieval outages and never fabricates consulted sources.
- [ ] Updating the Drive library requires no Git commit.

## Deferred to the next implementation slice

- dynamic expert router redesign;
- framework selector;
- blind independent first-round memos;
- Red Team and Evidence Judge redesign;
- Chairman `GO / NO-GO / TEST / DEFER` contract;
- decision memory and expert calibration;
- ChatGPT Skill front door.

These features build on the private retrieval substrate after this plan is implemented and verified.