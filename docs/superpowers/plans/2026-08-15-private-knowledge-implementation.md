# Private Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `MaciejZet/ai-council` safe as a public repository while synchronizing an explicitly allowlisted private Google Drive library into a private Pinecone namespace that Council can retrieve from without committing source content.

**Architecture:** Google Drive is the private source of truth. A local/admin-only sync command uses read-only Drive credentials, exports/downloads allowlisted files, normalizes and chunks them through the existing knowledge pipeline, and writes vectors plus provenance metadata into a dedicated Pinecone namespace. Council runtime only queries Pinecone. Git, CI and normal logs never contain private source text.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, `google-api-python-client`, `google-auth`, OpenAI embeddings, Pinecone Python SDK, pytest, uv, Ruff.

## Global Constraints

- Public Git may contain code, schemas, book titles, authors and framework identifiers, but no PDFs/ebooks, book summaries, highlights, annotations, extracted source text, private retrieval chunks, embeddings, Drive exports, or ingestion caches.
- Google Drive access is read-only and limited to an explicit allowlist of folder IDs and file IDs.
- Private Drive credentials and allowlist configuration remain outside Git.
- Use a dedicated Pinecone namespace configured by `PINECONE_PRIVATE_NAMESPACE`; do not mix the private corpus into the default namespace.
- Normal application logs contain technical IDs, counts, timings and errors only; no retrieved source text and no private source titles by default.
- CI must run with no Google Drive, Pinecone or production LLM credentials and use synthetic fixtures only.
- The app must still start and deliberate when private knowledge is unavailable.
- A knowledge outage must be represented as an explicit degraded status; the system must not imply that private sources were consulted.
- Adding or changing a book in Drive must require no Git commit.
- Existing public API behavior should remain backward-compatible unless a new optional field is added.

---

## File map

### Create

- `src/knowledge/private_models.py` — typed models for allowlist entries, private source metadata, sync state and retrieval status.
- `src/knowledge/private_config.py` — environment-backed private knowledge configuration with no secret values committed.
- `src/knowledge/drive_source.py` — read-only Google Drive client, allowlist traversal, binary download and Google Docs export.
- `src/knowledge/private_sync.py` — idempotent Drive-to-Pinecone synchronization service.
- `scripts/sync_private_knowledge.py` — explicit admin CLI entrypoint.
- `scripts/check_private_corpus.py` — repository safety guard for tracked/staged private-corpus paths and ebook formats.
- `tests/test_private_config.py` — configuration and no-credentials behavior.
- `tests/test_drive_source.py` — mocked Drive traversal/download/export tests.
- `tests/test_private_sync.py` — idempotency, hashing, failure safety and no-text logging tests.
- `tests/test_private_retrieval.py` — namespace, domain/expert filters, provenance and degraded status tests.
- `tests/test_private_corpus_guard.py` — repository safety guard tests.
- `docs/PRIVATE_KNOWLEDGE.md` — operator documentation for Drive credentials, allowlist and sync.

### Modify

- `.gitignore` — ignore every local private-knowledge working path and ebook format.
- `.env.example` — document placeholder-only private knowledge configuration.
- `pyproject.toml` — add Google Drive client/auth dependencies.
- `uv.lock` — lock the new dependencies.
- `src/knowledge/ingest.py` — extract a reusable text-document upsert path, namespace support, stable IDs and content hashes.
- `src/knowledge/retriever.py` — namespace-aware retrieval, expert/domain filters, structured status and provenance-preserving context.
- `src/council/orchestrator.py` — propagate knowledge status and avoid claiming private retrieval on outages.
- `.github/workflows/ci.yml` — run the corpus guard with no production secrets.
- `README.md` — point operators to the private knowledge setup without suggesting that books belong in the repository.

---

### Task 1: Enforce the public/private repository boundary

**Files:**
- Modify: `.gitignore`
- Create: `scripts/check_private_corpus.py`
- Create: `tests/test_private_corpus_guard.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: repository file paths from `git ls-files` and staged paths from `git diff --cached --name-only`.
- Produces: `check_paths(paths: Iterable[str]) -> list[str]` and CLI exit code `0` for safe, `1` for violations.

- [ ] **Step 1: Write failing guard tests**

Create `tests/test_private_corpus_guard.py`:

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

- [ ] **Step 2: Run the tests and verify failure**

Run:

```bash
uv run pytest tests/test_private_corpus_guard.py -v --no-cov
```

Expected: import failure because `scripts/check_private_corpus.py` does not exist.

- [ ] **Step 3: Implement the minimal guard**

Create `scripts/check_private_corpus.py` with these public constants and function:

```python
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
    ...
```

Normalize separators to `/`, reject every path under a forbidden prefix, and reject the ebook extensions case-insensitively. The CLI must combine tracked paths and staged paths, print only violating paths, and never open or print file contents.

- [ ] **Step 4: Strengthen `.gitignore`**

Add:

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

Do not add `*.pdf`; public documentation/test PDFs remain valid repository assets.

- [ ] **Step 5: Add the guard to CI**

Add before pytest in `.github/workflows/ci.yml`:

```yaml
      - name: Public repository corpus guard
        run: uv run python scripts/check_private_corpus.py --tracked-only
```

- [ ] **Step 6: Run focused verification**

```bash
uv run pytest tests/test_private_corpus_guard.py -v --no-cov
uv run python scripts/check_private_corpus.py --tracked-only
```

Expected: tests pass and current repository returns exit code `0`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore .github/workflows/ci.yml scripts/check_private_corpus.py tests/test_private_corpus_guard.py
git commit -m "security: enforce private knowledge repository boundary"
```

---

### Task 2: Add explicit private knowledge configuration and typed metadata

**Files:**
- Create: `src/knowledge/private_models.py`
- Create: `src/knowledge/private_config.py`
- Create: `tests/test_private_config.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `PrivateKnowledgeConfig.from_env()`, `DriveAllowlist`, `DriveAllowlistEntry`, `PrivateSourceMetadata`, `KnowledgeRetrievalResult`.
- Later tasks consume these exact names.

- [ ] **Step 1: Write failing configuration tests**

Create `tests/test_private_config.py` covering:

```python
def test_private_config_is_disabled_without_allowlist(monkeypatch):
    monkeypatch.delenv("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE", raising=False)
    cfg = PrivateKnowledgeConfig.from_env()
    assert cfg.enabled is False


def test_private_config_never_requires_drive_credentials_for_app_start(monkeypatch):
    monkeypatch.setenv("PINECONE_PRIVATE_NAMESPACE", "maciej-private")
    cfg = PrivateKnowledgeConfig.from_env()
    assert cfg.pinecone_namespace == "maciej-private"
```

Also test parsing a synthetic allowlist file into `DriveAllowlist`.

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run pytest tests/test_private_config.py -v --no-cov
```

Expected: imports fail because the modules do not exist.

- [ ] **Step 3: Add the models**

`src/knowledge/private_models.py` should define Pydantic models equivalent to:

```python
class DriveAllowlistEntry(BaseModel):
    id: str
    source_type: Literal["book", "summary", "personal_note", "synthesis", "internal_doc"] = "book"
    domains: list[str] = []
    experts: list[str] = []
    framework_tags: list[str] = []
    recursive: bool = True


class DriveAllowlist(BaseModel):
    files: list[DriveAllowlistEntry] = []
    folders: list[DriveAllowlistEntry] = []


class PrivateSourceMetadata(BaseModel):
    doc_id: str
    title: str
    source_type: str
    language: str
    domains: list[str]
    experts: list[str]
    framework_tags: list[str]
    drive_file_id: str
    content_hash: str
    modified_time: str | None = None
```

Use `Field(default_factory=list)` instead of mutable list defaults in the implementation.

Define retrieval status as:

```python
KnowledgeStatus = Literal["ok", "no_matches", "disabled", "unavailable"]

class KnowledgeRetrievalResult(BaseModel):
    status: KnowledgeStatus
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
```

- [ ] **Step 4: Add environment-backed configuration**

`PrivateKnowledgeConfig.from_env()` must read only variable names, never log values:

```text
PRIVATE_KNOWLEDGE_ALLOWLIST_FILE
PRIVATE_KNOWLEDGE_STATE_FILE
PINECONE_PRIVATE_NAMESPACE
PRIVATE_KNOWLEDGE_DEBUG_TITLES
```

Defaults:

```text
PRIVATE_KNOWLEDGE_STATE_FILE=.private_knowledge/state.json
PINECONE_PRIVATE_NAMESPACE=private-library
PRIVATE_KNOWLEDGE_DEBUG_TITLES=false
```

`enabled` means an allowlist path has been configured. It must not mean Drive credentials are valid; credential validation belongs to the sync CLI.

- [ ] **Step 5: Update `.env.example` with placeholders only**

Add:

```env
# Private knowledge sync (optional; local/admin use only)
# GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/outside/repo/drive-readonly.json
# PRIVATE_KNOWLEDGE_ALLOWLIST_FILE=/absolute/path/outside/repo/private-knowledge-allowlist.json
# PRIVATE_KNOWLEDGE_STATE_FILE=.private_knowledge/state.json
PINECONE_PRIVATE_NAMESPACE=private-library
PRIVATE_KNOWLEDGE_DEBUG_TITLES=false
```

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/test_private_config.py -v --no-cov
git add .env.example src/knowledge/private_models.py src/knowledge/private_config.py tests/test_private_config.py
git commit -m "feat: add private knowledge configuration models"
```

---

### Task 3: Make the existing ingestion pipeline namespace-aware and idempotent

**Files:**
- Modify: `src/knowledge/ingest.py`
- Create: `tests/test_private_sync.py` (first ingestion-core tests)

**Interfaces:**
- Produces:
  - `content_sha256(content: bytes | str) -> str`
  - `stable_doc_id(source_kind: str, source_id: str) -> str`
  - `upsert_text_document(text: str, metadata: PrivateSourceMetadata, *, namespace: str, batch_size: int = 100) -> dict[str, Any]`
- Existing `ingest_pdf()` remains callable and becomes a wrapper around the generic path.

- [ ] **Step 1: Write failing ingestion-core tests**

Use fake embeddings and a fake Pinecone index. Verify:

```python
def test_stable_doc_id_is_path_independent():
    assert stable_doc_id("gdrive", "abc123") == stable_doc_id("gdrive", "abc123")


def test_upsert_uses_private_namespace(fake_index, monkeypatch):
    result = upsert_text_document(
        "synthetic knowledge only",
        synthetic_metadata,
        namespace="private-test",
    )
    assert fake_index.upsert_calls[0]["namespace"] == "private-test"
```

Also verify each vector metadata record contains `doc_id`, `content_hash`, `source_type`, `domains`, `experts`, `framework_tags`, `chunk_index` and `text`.

- [ ] **Step 2: Run focused tests and verify failure**

```bash
uv run pytest tests/test_private_sync.py -k "stable_doc_id or upsert_uses_private_namespace" -v --no-cov
```

- [ ] **Step 3: Extract the generic text ingestion path**

Keep existing `chunk_text()` and embedding generation. Replace filename/path-derived vector identity with stable source identity:

```python
def stable_doc_id(source_kind: str, source_id: str) -> str:
    return hashlib.sha256(f"{source_kind}:{source_id}".encode()).hexdigest()[:28]


def generate_chunk_id(doc_id: str, content_hash: str, chunk_index: int) -> str:
    raw = f"{doc_id}:{content_hash}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

`upsert_text_document()` must upsert all new vectors first. Only after successful upserts may it remove older versions with the same `doc_id` and a different `content_hash`.

Use a Pinecone delete filter equivalent to:

```python
{
    "$and": [
        {"doc_id": {"$eq": metadata.doc_id}},
        {"content_hash": {"$ne": metadata.content_hash}},
    ]
}
```

and pass the same `namespace` to `upsert` and `delete`.

- [ ] **Step 4: Preserve local PDF compatibility**

Refactor `ingest_pdf()` to extract text, build `PrivateSourceMetadata`, then call `upsert_text_document()`. Existing callers without `namespace` continue to use the default namespace behavior so current public/demo ingestion does not silently move.

- [ ] **Step 5: Verify failure safety**

Add a fake index that raises during upsert and assert `delete()` was never called. This implements the design rule that a failed refresh cannot destroy the last valid vectors.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/test_private_sync.py -v --no-cov
git add src/knowledge/ingest.py tests/test_private_sync.py
git commit -m "refactor: add namespace-safe idempotent knowledge ingestion"
```

---

### Task 4: Add a read-only, allowlist-only Google Drive source adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/knowledge/drive_source.py`
- Create: `tests/test_drive_source.py`

**Interfaces:**
- Consumes: `DriveAllowlist`, `DriveAllowlistEntry`.
- Produces:
  - `DriveSourceRecord`
  - `DriveSourceClient.list_allowed(allowlist: DriveAllowlist) -> list[DriveSourceRecord]`
  - `DriveSourceClient.read_bytes(record: DriveSourceRecord) -> bytes`

- [ ] **Step 1: Add dependencies**

Add to `pyproject.toml`:

```toml
"google-api-python-client>=2.0.0",
"google-auth>=2.0.0",
```

Then run:

```bash
uv lock
uv sync --extra dev
```

- [ ] **Step 2: Write mocked Drive tests**

The tests must not call Google. Cover:

1. a file ID explicitly present in the allowlist;
2. a folder ID whose children are listed;
3. a file outside the allowlist is never returned;
4. `application/pdf` uses Drive media download;
5. `application/vnd.google-apps.document` uses export to `text/plain` bytes;
6. unsupported MIME types are skipped with a metadata-only warning.

- [ ] **Step 3: Run tests and verify failure**

```bash
uv run pytest tests/test_drive_source.py -v --no-cov
```

- [ ] **Step 4: Implement `DriveSourceClient`**

Build the Drive v3 service lazily with `google.auth.default()` using the read-only Drive scope. Do not initialize the client at module import time.

The record should contain only metadata needed for sync:

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

Folder traversal must query children by parent ID. If `recursive=True`, recurse only through descendant folders of that allowlisted folder. Never issue an unbounded account-wide file listing.

- [ ] **Step 5: Keep credentials outside the repository**

Credential errors should be raised as a dedicated `PrivateKnowledgeConfigError`/`DriveSourceError` containing no credential path contents and no source text.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/test_drive_source.py -v --no-cov
git add pyproject.toml uv.lock src/knowledge/drive_source.py tests/test_drive_source.py
git commit -m "feat: add allowlist-only Google Drive knowledge source"
```

---

### Task 5: Implement idempotent Drive-to-Pinecone synchronization

**Files:**
- Create: `src/knowledge/private_sync.py`
- Modify: `tests/test_private_sync.py`
- Create: `scripts/sync_private_knowledge.py`

**Interfaces:**
- Consumes: `PrivateKnowledgeConfig`, `DriveSourceClient`, `upsert_text_document()`.
- Produces:
  - `PrivateKnowledgeSync.sync(*, dry_run: bool = False) -> SyncReport`
  - CLI: `uv run python scripts/sync_private_knowledge.py [--dry-run]`

- [ ] **Step 1: Add failing sync behavior tests**

Use only synthetic source text. Verify:

- unchanged remote version is skipped;
- changed remote version is fetched, hashed and re-ingested;
- a Google Doc and a PDF both produce text without persisting an export in the repo;
- the state file stores IDs/hashes/counts but no source text;
- a failed embedding/upsert does not advance state;
- sync report contains counts and `doc_id`, never source text;
- log capture does not contain the synthetic private sentence or source title when debug titles are off.

- [ ] **Step 2: Implement private sync state**

Store state at `PRIVATE_KNOWLEDGE_STATE_FILE`, default `.private_knowledge/state.json`:

```json
{
  "version": 1,
  "documents": {
    "<drive-file-id>": {
      "doc_id": "...",
      "remote_version": "...",
      "content_hash": "...",
      "last_ingested_at": "...",
      "chunks": 12
    }
  }
}
```

No title, summary, extracted text or chunk text goes into state.

- [ ] **Step 3: Implement the sync algorithm**

For each allowlisted record:

1. derive `remote_version = md5_checksum or modified_time or "unknown"`;
2. skip immediately when state has the same remote version;
3. read bytes only for changed/new records;
4. compute SHA-256;
5. decode Google Docs `text/plain` as UTF-8; for PDFs use the existing PDF extractor via a secure temporary file outside the repository working tree;
6. create `PrivateSourceMetadata` using the allowlist entry plus title/language detection;
7. call `upsert_text_document(..., namespace=config.pinecone_namespace)`;
8. update state only after success;
9. write state atomically using a temporary sibling file plus `Path.replace()`.

Temporary files must use `tempfile.TemporaryDirectory()` and must not be placed under the repository.

- [ ] **Step 4: Implement the admin CLI**

The CLI must:

```text
1. load PrivateKnowledgeConfig;
2. require PRIVATE_KNOWLEDGE_ALLOWLIST_FILE;
3. validate Drive credentials only now, not at app import/start;
4. run sync;
5. print a metadata-only report: scanned/skipped/updated/failed counts and doc IDs;
6. return non-zero only for configuration errors or failed source updates.
```

`--dry-run` may list planned file IDs/counts but must not download source content, embed or mutate Pinecone/state.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_private_sync.py -v --no-cov
git add src/knowledge/private_sync.py scripts/sync_private_knowledge.py tests/test_private_sync.py
git commit -m "feat: sync private Drive knowledge into Pinecone"
```

---

### Task 6: Add private namespace retrieval, expert/domain filters and provenance

**Files:**
- Modify: `src/knowledge/retriever.py`
- Create: `tests/test_private_retrieval.py`

**Interfaces:**
- Produces:
  - `query_knowledge_result(...) -> KnowledgeRetrievalResult`
  - backward-compatible `query_knowledge(...) -> list[dict[str, Any]]`
  - `format_context_for_agent(chunks, *, include_provenance: bool = True) -> str`

- [ ] **Step 1: Write failing retrieval tests**

With a fake Pinecone index verify:

```python
result = query_knowledge_result(
    "synthetic pricing question",
    domains=["pricing"],
    experts=["monetization"],
    namespace="private-test",
)
```

Expected query call includes:

```python
namespace="private-test"
```

and a metadata filter containing both domain and expert constraints joined by `$and`.

Also test:

- `source_type="synthesis"` is accepted;
- missing Pinecone/OpenAI configuration yields `status="unavailable"`, not a fabricated source;
- configured query with zero matches yields `status="no_matches"`;
- success yields `status="ok"`;
- legacy `query_knowledge()` still returns only `.chunks`.

- [ ] **Step 2: Extend filter validation**

Allowed source types become:

```python
{
    "book", "summary", "personal_note", "synthesis", "internal_doc",
    "article", "ogólne", "web", "notion", "file"
}
```

Add optional `domains: list[str] | None` and `experts: list[str] | None`. Construct an `$and` list rather than overwriting filters.

- [ ] **Step 3: Pass the namespace to Pinecone**

Use explicit `namespace=` whenever one is provided. Council private retrieval will pass `PINECONE_PRIVATE_NAMESPACE`; existing public/demo callers can continue without a namespace argument.

- [ ] **Step 4: Preserve provenance inside agent context**

Change `format_context_for_agent()` so the default private path uses compact provenance headers:

```text
[SOURCE]
title: <title>
source_type: <source_type>
doc_id: <doc_id>
chunk: <chunk_index>
score: <score>

<retrieved text>
```

Do not add local file paths or Drive credential information. This provenance is prompt-internal and allows future Evidence Judge logic to distinguish source types.

- [ ] **Step 5: Remove source excerpts from display metadata by default**

`format_sources_for_display()` should return source title, type, category/domain, chunk indices and score, not a 300-character excerpt. If a UI path genuinely needs excerpts later, make it an explicit opt-in parameter defaulting to `False`.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/test_private_retrieval.py -v --no-cov
git add src/knowledge/retriever.py tests/test_private_retrieval.py
git commit -m "feat: add private namespace and expert-aware retrieval"
```

---

### Task 7: Propagate explicit knowledge health through Council deliberation

**Files:**
- Modify: `src/council/orchestrator.py`
- Modify: `tests/test_council.py`
- Modify or create: `tests/test_private_retrieval.py`

**Interfaces:**
- `CouncilDeliberation` gains backward-compatible fields:
  - `knowledge_status: str = "disabled"`
  - `knowledge_error_code: str | None = None`
- `Council._get_context()` consumes `query_knowledge_result()`.

- [ ] **Step 1: Write failing degraded-mode tests**

Mock retrieval to return `KnowledgeRetrievalResult(status="unavailable", error_code="pinecone_unavailable")` and assert:

```python
result.knowledge_status == "unavailable"
result.sources == []
```

Also verify normal agent deliberation can continue when the mode is not `kb_only`.

For `kb_only`, verify the synthesis message states that the knowledge source is unavailable, not that no relevant facts exist.

- [ ] **Step 2: Update `_get_context()`**

Return a structured tuple containing texts, display sources, status and error code. Do not log chunk text, prompt context or private titles. Log only status/error code and counts.

- [ ] **Step 3: Update `CouncilDeliberation`**

Populate the new status fields in every return path. Keep existing fields and defaults to avoid breaking API consumers.

- [ ] **Step 4: Run Council tests and commit**

```bash
uv run pytest tests/test_council.py tests/test_private_retrieval.py -v --no-cov
git add src/council/orchestrator.py tests/test_council.py tests/test_private_retrieval.py
git commit -m "feat: expose explicit knowledge retrieval status"
```

---

### Task 8: Document the private operator workflow

**Files:**
- Create: `docs/PRIVATE_KNOWLEDGE.md`
- Modify: `README.md`

**Interfaces:**
- Operator-facing commands and config contract only; no private IDs, titles, notes or source text.

- [ ] **Step 1: Write `docs/PRIVATE_KNOWLEDGE.md`**

Document this exact workflow with placeholder IDs only:

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
      "framework_tags": []
    }
  ]
}
```

Document that the file lives outside the repository and is referenced via `PRIVATE_KNOWLEDGE_ALLOWLIST_FILE`.

Document admin commands:

```bash
uv run python scripts/sync_private_knowledge.py --dry-run
uv run python scripts/sync_private_knowledge.py
```

State explicitly that books, summaries and exports must never be added to Git, tests or issue attachments for this public repository.

- [ ] **Step 2: Update README**

Replace any wording suggesting that the repository itself is the book library with a short section linking to `docs/PRIVATE_KNOWLEDGE.md`. Preserve local PDF import as a generic feature only if it remains technically supported, and mark private-library storage as local/private rather than repository content.

- [ ] **Step 3: Run docs-related safety check and commit**

```bash
uv run python scripts/check_private_corpus.py --tracked-only
git add docs/PRIVATE_KNOWLEDGE.md README.md
git commit -m "docs: document private Drive knowledge workflow"
```

---

### Task 9: Full verification and regression gate

**Files:**
- Modify only if verification exposes a defect.

**Interfaces:**
- Produces a green repository state with no production secrets or private source data.

- [ ] **Step 1: Run formatting/lint checks on changed Python files**

```bash
uv run ruff check src/knowledge scripts tests
```

Expected: exit code `0`.

- [ ] **Step 2: Run the private-knowledge test slice**

```bash
uv run pytest \
  tests/test_private_config.py \
  tests/test_drive_source.py \
  tests/test_private_sync.py \
  tests/test_private_retrieval.py \
  tests/test_private_corpus_guard.py \
  tests/test_council.py \
  -v --tb=short --no-cov
```

Expected: all pass with no real Drive/Pinecone/OpenAI credentials.

- [ ] **Step 3: Run the full repository suite**

```bash
uv run pytest tests/ -v --tb=short --no-cov
uv run python tests/quality_gate.py
```

Expected: all existing tests pass and quality gate exits successfully.

- [ ] **Step 4: Run the repository corpus guard**

```bash
uv run python scripts/check_private_corpus.py --tracked-only
```

Expected: exit code `0` and no violating paths.

- [ ] **Step 5: Verify no secret/private configuration was committed**

Run:

```bash
git diff main...HEAD -- .env .env.example
git ls-files | grep -E '(^|/)(private_knowledge|knowledge_private|drive_exports|ingestion_cache|books_pdf|\.private_knowledge)/' && exit 1 || true
git ls-files | grep -Ei '\.(epub|mobi|azw|azw3)$' && exit 1 || true
```

Expected: only placeholder environment names in `.env.example`; no private corpus paths or ebook formats tracked.

- [ ] **Step 6: Perform one authorized local smoke sync outside CI**

Only on a machine with the user's private credentials and allowlist:

```bash
uv run python scripts/sync_private_knowledge.py --dry-run
uv run python scripts/sync_private_knowledge.py
```

Success criteria: allowlisted sources are counted, vectors are written to `PINECONE_PRIVATE_NAMESPACE`, state is written under `.private_knowledge/`, and no source text appears in Git status or normal logs.

Do not paste the resulting source text, Drive IDs, credentials or private state into the public PR.

- [ ] **Step 7: Commit any verification-only fixes, then stop**

If no fixes were needed, do not create an empty commit.

---

## Acceptance checklist

The implementation is ready to merge only when all statements below are true:

- [ ] `git clone` of the public repository contains no private book corpus, summaries, notes, chunks or embeddings.
- [ ] CI passes without Drive/Pinecone/OpenAI production credentials.
- [ ] The Drive adapter can see only explicit allowlist entries and descendants of explicitly allowlisted folders.
- [ ] Google Docs are exported through Drive and PDFs are downloaded to temporary storage outside the repo.
- [ ] Private vectors use `PINECONE_PRIVATE_NAMESPACE`.
- [ ] Refresh upserts new content before deleting older vector versions.
- [ ] Sync state contains only IDs, hashes, versions, counts and timestamps.
- [ ] Normal logs never include retrieved private text and do not include source titles unless debug-title mode is explicitly enabled.
- [ ] Retrieval can filter by domain, expert and source type while preserving source provenance internally.
- [ ] Council reports `unavailable` when private retrieval is down and does not fabricate a consulted source.
- [ ] Adding/updating a Drive book requires no Git commit.

## Deferred to the next implementation slice

These items remain intentionally out of scope until the private boundary works and passes tests:

- dynamic expert router redesign;
- framework selector;
- blind independent first-round memos;
- Red Team and Evidence Judge redesign;
- Chairman `GO / NO-GO / TEST / DEFER` contract;
- decision memory and expert calibration;
- ChatGPT Skill front door.

Those features can safely build on the private retrieval substrate created by this plan.