# Decision Memory v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist sanitized Council OS decisions for authenticated users, let users attach outcomes/postmortems, and compute deterministic expert/Chairman calibration without feeding historical decisions back into future prompts.

**Architecture:** Add a focused SQLite repository in `src/storage/decision_memory.py`, keep `CouncilOS` storage-agnostic, and persist only at the Council Mode/API boundary through an optional completion callback. Read/update APIs in `main.py` reuse the existing `X-User-Session` ownership model. Calibration is computed from stored blind votes and Chairman verdicts against user-supplied `resolved_vote` outcomes.

**Tech Stack:** Python 3.12+, SQLite (`sqlite3`), Pydantic 2, FastAPI, existing `CouncilOSResult`, pytest, Ruff, GitHub Actions.

## Global Constraints

- Use a dedicated default database at `data/ai_council_decisions.db`; tests inject a temporary path.
- Every persisted record is scoped by the existing authenticated `user_id` resolved from `X-User-Session`.
- Anonymous or invalid-session Council OS runs remain supported and are not persisted.
- Automatic capture is best-effort and must never fail the Council OS stream.
- `CouncilOS` itself must not import storage code or user/session concepts.
- Persist no raw RAG chunk text, source excerpts, source inventory objects, Drive IDs, file-system paths, credentials, full memo prose, full rebuttal prose, book text, or book summaries.
- Storage must construct SQL values explicitly; do not persist `CouncilOSResult.model_dump()` wholesale.
- Calibration uses blind expert votes, not revised votes, for the headline score.
- Chairman calibration uses the final Chairman verdict.
- `brier_like_error = mean((confidence - correctness) ** 2)` where correctness is 1.0 for a matching vote and 0.0 otherwise.
- Historical decisions are not injected into future prompts in v1.
- New tests use synthetic data only.

---

### Task 1: Decision Memory SQLite repository and sanitized capture

**Files:**
- Create: `src/storage/decision_memory.py`
- Create: `tests/test_decision_memory_storage.py`

**Interfaces:**
- Consumes: `src.council.council_os_models.CouncilOSResult` and `DecisionVote`.
- Produces:
  - `DecisionMemoryStore(db_path: Path | str | None = None)`
  - `capture_decision(user_id: str, query: str, result: CouncilOSResult) -> str`
  - `get_decision(user_id: str, decision_id: str) -> dict[str, Any] | None`
  - `list_decisions(user_id: str, *, limit: int = 50, primary_domain: str | None = None, verdict: str | None = None, outcome_status: str | None = None) -> list[dict[str, Any]]`

- [ ] **Step 1: Write failing schema/capture tests**

Create a synthetic `CouncilOSResult` fixture containing sentinel strings in memo/rebuttal prose and a normal Chairman verdict. Test that `capture_decision()` creates a decision row plus expert vote rows, and that `get_decision()` returns only the approved sanitized fields.

```python
result = synthetic_council_result(private_sentinel="PRIVATE_SYNTHETIC_CHUNK")
decision_id = store.capture_decision("user-a", "Should we test pricing?", result)
record = store.get_decision("user-a", decision_id)

assert record is not None
assert record["query"] == "Should we test pricing?"
assert record["verdict"] == "TEST"
assert {vote["expert_id"] for vote in record["expert_votes"]} == {"strategy", "offer_pricing"}
assert "PRIVATE_SYNTHETIC_CHUNK" not in json.dumps(record)
```

Also open the SQLite file directly and assert the sentinel does not appear in any text column of `decisions`, `decision_expert_votes`, or `decision_outcomes`.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/test_decision_memory_storage.py -v --tb=short --no-cov
```

Expected: import failure because `src.storage.decision_memory` does not exist.

- [ ] **Step 3: Implement `DecisionMemoryStore` and schema**

Use a per-instance lock and connection helper so tests can inject a temporary path without mutating module globals.

Required schema:

```sql
CREATE TABLE IF NOT EXISTS decisions (...);
CREATE TABLE IF NOT EXISTS decision_expert_votes (...);
CREATE TABLE IF NOT EXISTS decision_outcomes (...);
CREATE INDEX IF NOT EXISTS idx_decisions_user_created ON decisions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_user_domain ON decisions(user_id, primary_domain);
CREATE INDEX IF NOT EXISTS idx_decisions_user_verdict ON decisions(user_id, verdict);
```

Use `uuid.uuid4()` for decision ids and timezone-aware UTC ISO timestamps.

- [ ] **Step 4: Implement explicit sanitization/capture**

Map only approved fields from `CouncilOSResult`:

```python
verdict = result.verdict
next_experiment = verdict.next_experiment.model_dump(mode="json") if verdict.next_experiment else None
```

Persist:
- profile fields;
- routed expert ids;
- Chairman verdict fields;
- assumptions/evidence-gap labels/what-would-change fields;
- next experiment;
- knowledge status map;
- orchestration error labels;
- expert `blind_vote`, `blind_confidence`, `knowledge_status`;
- matching rebuttal `revised_vote`, `revised_confidence` if present.

Never persist memo recommendation, claims, risks, `what_changes_my_mind`, rebuttal prose, or any retrieval/source payload.

- [ ] **Step 5: Add ownership/list tests**

Assert:

```python
assert store.get_decision("user-b", decision_id) is None
assert store.list_decisions("user-b") == []
```

Create several synthetic decisions and verify filters for `primary_domain` and `verdict`.

- [ ] **Step 6: Run GREEN and Ruff**

```bash
uv run pytest tests/test_decision_memory_storage.py -v --tb=short --no-cov
uv run ruff check src/storage/decision_memory.py tests/test_decision_memory_storage.py
```

Expected: all pass.

---

### Task 2: Outcome upsert and calibration engine

**Files:**
- Modify: `src/storage/decision_memory.py`
- Create: `tests/test_decision_memory_calibration.py`

**Interfaces:**
- Produces:
  - `upsert_outcome(user_id: str, decision_id: str, *, status: str, resolved_vote: str | None, experiment_result: str | None, postmortem: str | None, notes: str | None) -> dict[str, Any] | None`
  - `calibration_report(user_id: str) -> dict[str, Any]`

- [ ] **Step 1: Write failing outcome ownership/upsert tests**

Test first insert, replacement, and cross-user protection:

```python
outcome = store.upsert_outcome(
    "user-a",
    decision_id,
    status="success",
    resolved_vote="TEST",
    experiment_result="12% conversion",
    postmortem="Synthetic postmortem",
    notes=None,
)
assert outcome["resolved_vote"] == "TEST"

revised = store.upsert_outcome(
    "user-a",
    decision_id,
    status="mixed",
    resolved_vote="GO",
    experiment_result="Follow-up changed the read",
    postmortem="Revised",
    notes="Synthetic",
)
assert revised["status"] == "mixed"
assert store.upsert_outcome("user-b", decision_id, status="success", resolved_vote="GO", experiment_result=None, postmortem=None, notes=None) is None
```

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/test_decision_memory_calibration.py -v --tb=short --no-cov
```

Expected: missing `upsert_outcome` / `calibration_report`.

- [ ] **Step 3: Implement outcome upsert**

Before inserting, verify ownership in `decisions`. Use SQLite `INSERT ... ON CONFLICT(decision_id) DO UPDATE`. Update `decisions.updated_at` in the same transaction.

- [ ] **Step 4: Extend list filtering by outcome status**

Use an `EXISTS`/join filter scoped by `user_id`. A decision without an outcome must not match any explicit `outcome_status`.

- [ ] **Step 5: Write deterministic calibration fixture**

Create two resolved decisions with known values. Example:

```text
Decision 1 resolved_vote=TEST
strategy: TEST @ 0.8  -> correct, error 0.04
pricing: GO @ 0.7     -> wrong, error 0.49
chairman: TEST @ 0.9  -> correct, error 0.01

Decision 2 resolved_vote=GO
strategy: TEST @ 0.6  -> wrong, error 0.36
pricing: GO @ 0.5     -> correct, error 0.25
chairman: GO @ 0.7    -> correct, error 0.09
```

Expected strategy aggregate:

```python
assert strategy["sample_size"] == 2
assert strategy["correct_count"] == 1
assert strategy["hit_rate"] == 0.5
assert strategy["mean_confidence"] == 0.7
assert strategy["brier_like_error"] == 0.2
```

Expected Chairman `brier_like_error == 0.05`.

Add a third decision with outcome status but `resolved_vote=None` and assert it is excluded from scored samples.

- [ ] **Step 6: Implement calibration aggregation**

Return:

```python
{
    "sample_size": total_resolved_decisions,
    "experts": [...],
    "domains": {
        "pricing": [...],
        "strategy": [...],
    },
}
```

Each expert item contains `expert_id`, `sample_size`, `correct_count`, `hit_rate`, `mean_confidence`, `brier_like_error`. Add Chairman as `expert_id="chairman"` from `decisions.verdict` and `verdict_confidence`.

Round exposed floating metrics to 6 decimal places for deterministic API output.

- [ ] **Step 7: Run GREEN and Ruff**

```bash
uv run pytest tests/test_decision_memory_storage.py tests/test_decision_memory_calibration.py -v --tb=short --no-cov
uv run ruff check src/storage/decision_memory.py tests/test_decision_memory_storage.py tests/test_decision_memory_calibration.py
```

Expected: all pass.

---

### Task 3: CouncilOSMode completion hook and best-effort persistence boundary

**Files:**
- Modify: `src/council/modes.py`
- Modify: `tests/test_council_os_mode.py`

**Interfaces:**
- `CouncilOSMode` constructor accepts `on_complete: Callable[[str, CouncilOSResult], str | None] | None = None` in addition to existing `use_knowledge_base` behavior.
- `run_stream()` invokes the callback once after `CouncilOS.deliberate()` returns.
- The callback result is an optional `decision_id` added to the `council_os_result` SSE envelope outside the `CouncilOSResult` model.

- [ ] **Step 1: Write failing callback tests**

Add tests for:

```python
captured = []
mode = CouncilOSMode(on_complete=lambda query, result: captured.append((query, result)) or "decision-123")
events = [event async for event in mode.run_stream("synthetic question", llm=object())]
assert len(captured) == 1
assert '"decision_id": "decision-123"' in "".join(events)
```

Add a callback that raises `RuntimeError("SENSITIVE_PRIVATE_SENTINEL")` and assert the stream still emits `council_os_result` and `complete`, does not emit a `decision_id`, and does not serialize the exception message.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/test_council_os_mode.py -v --tb=short --no-cov
```

Expected: constructor does not accept the hook or result event lacks `decision_id`.

- [ ] **Step 3: Implement narrow callback boundary**

Store the callback on `CouncilOSMode`. In `run_stream()`:

```python
decision_id = None
if self.on_complete is not None:
    try:
        decision_id = self.on_complete(query, result)
    except Exception:
        logger.exception("Council OS decision persistence failed")
```

Do not log query/result/exception text. Prefer a logger call that records the exception class or a fixed message without user content.

Build SSE result payload as:

```python
payload = {"result": result.model_dump(mode="json")}
if decision_id:
    payload["decision_id"] = decision_id
```

- [ ] **Step 4: Re-run existing knowledge toggle tests**

The callback change must preserve `use_knowledge_base=False` behavior exactly.

- [ ] **Step 5: Run GREEN**

```bash
uv run pytest tests/test_council_os_mode.py -v --tb=short --no-cov
```

Expected: all pass.

---

### Task 4: Authenticated automatic capture in the existing mode stream API

**Files:**
- Modify: `main.py`
- Create: `tests/test_decision_memory_capture_api.py`

**Interfaces:**
- Reuses `user_store.validate_session()`.
- Uses a module-level production store, e.g. `decision_memory_store = DecisionMemoryStore()`.
- For mode `council_os`, authenticated requests create a `CouncilOSMode` instance with a completion callback; anonymous/invalid-session requests use normal mode behavior.

- [ ] **Step 1: Write failing authenticated/anonymous API tests**

Monkeypatch `user_store.validate_session`, `decision_memory_store.capture_decision`, `CouncilOS`, and provider creation.

Authenticated case:

```python
response = client.get(
    "/api/council/mode/stream",
    params={"mode": "council_os", "query": "synthetic question"},
    headers={"X-User-Session": "valid"},
)
assert response.status_code == 200
assert capture_calls == [("user-a", "synthetic question")]
assert '"decision_id": "decision-123"' in response.text
```

Anonymous and invalid-session cases must return 200, call capture zero times, and omit `decision_id`.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/test_decision_memory_capture_api.py -v --tb=short --no-cov
```

Expected: mode endpoint does not yet wire persistence.

- [ ] **Step 3: Integrate session resolution**

Change the endpoint signature to accept `request: Request` while preserving existing query/provider/model parameters.

Only special-case `mode == "council_os"` for persistence wiring. Do not change registry behavior for other modes.

Pseudo-contract:

```python
mode_instance = get_mode(mode)
uid = user_store.validate_session(request.headers.get("X-User-Session"))
if mode == "council_os" and uid:
    mode_instance = CouncilOSMode(
        use_knowledge_base=mode_instance.use_knowledge_base,
        on_complete=lambda q, result: decision_memory_store.capture_decision(uid, q, result),
    )
```

If the existing endpoint does not expose a knowledge toggle, preserve the mode instance's current/default `use_knowledge_base` value.

- [ ] **Step 4: Make capture failure best-effort**

The callback exception is swallowed by `CouncilOSMode`; API stays 200. Add an API regression test proving a store exception does not alter the business result stream.

- [ ] **Step 5: Run GREEN plus existing Council mode API tests**

```bash
uv run pytest tests/test_decision_memory_capture_api.py tests/test_council_mode_api.py tests/test_council_os_mode.py -v --tb=short --no-cov
```

Expected: all pass.

---

### Task 5: User-scoped Decision Memory REST API and validation

**Files:**
- Modify: `main.py`
- Create: `tests/test_decision_memory_api.py`

**Interfaces:**
- Add `DecisionOutcomeRequest` Pydantic model.
- Add endpoints:
  - `GET /api/decision-memory`
  - `GET /api/decision-memory/{decision_id}`
  - `PUT /api/decision-memory/{decision_id}/outcome`
  - `GET /api/decision-memory/calibration`

- [ ] **Step 1: Write failing auth/ownership tests**

Every endpoint requires a valid `X-User-Session`. Missing/invalid sessions return 401. Cross-user `GET` and `PUT outcome` return 404.

- [ ] **Step 2: Write request validation tests**

Use:

```python
class DecisionOutcomeRequest(BaseModel):
    status: Literal["success", "failure", "mixed", "inconclusive"]
    resolved_vote: Literal["GO", "NO-GO", "TEST", "DEFER"] | None = None
    experiment_result: str | None = Field(default=None, max_length=4000)
    postmortem: str | None = Field(default=None, max_length=8000)
    notes: str | None = Field(default=None, max_length=4000)
```

Assert invalid status/vote and over-limit text return 422.

- [ ] **Step 3: Run RED**

```bash
uv run pytest tests/test_decision_memory_api.py -v --tb=short --no-cov
```

Expected: endpoints absent.

- [ ] **Step 4: Implement auth helper and endpoints**

Reuse the existing session validation pattern. A small local helper is allowed:

```python
def _require_user(request: Request) -> str:
    uid = user_store.validate_session(request.headers.get("X-User-Session"))
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or missing X-User-Session")
    return uid
```

List endpoint bounds `limit` with FastAPI/Pydantic validation (`ge=1`, `le=200`). Validate optional verdict/outcome filters with `Literal` types when feasible so invalid values fail before storage.

- [ ] **Step 5: Add `/api/decision-memory` to normalized core contract paths**

Extend `CORE_CONTRACT_PATH_PREFIXES` with `"/api/decision-memory"`. Existing middleware/exception handling should then normalize relevant validation/rate-limit/internal errors consistently.

- [ ] **Step 6: Run GREEN**

```bash
uv run pytest tests/test_decision_memory_api.py tests/test_core_api_contracts.py -v --tb=short --no-cov
```

Expected: all pass.

---

### Task 6: Documentation, focused CI gate, final review, and merge

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`
- Test: all Decision Memory tests plus full suite

**Interfaces:** None; this task verifies the delivered feature.

- [ ] **Step 1: Document Decision Memory**

README must state:
- authenticated `council_os` runs can receive a `decision_id`;
- decision records store sanitized vote/verdict metadata, not RAG passages or full expert prose;
- outcomes/postmortems are user-authored and revisable;
- calibration uses `resolved_vote`, blind expert votes, Chairman verdict, hit rate, mean confidence, and `brier_like_error`;
- historical decisions are not yet fed back into Council prompts.

Document the four REST endpoints and `X-User-Session` requirement.

- [ ] **Step 2: Add a focused Decision Memory CI step**

Before the full pytest step, run:

```bash
uv run pytest tests/test_decision_memory_*.py -v --tb=short --no-cov
uv run ruff check src/storage/decision_memory.py tests/test_decision_memory_*.py
```

Do not weaken or remove any existing private-knowledge, Council OS, corpus guard, Ruff, pytest, or quality-gate step.

- [ ] **Step 3: Run focused verification**

```bash
uv run pytest tests/test_decision_memory_*.py tests/test_council_os_mode.py tests/test_council_mode_api.py -v --tb=short --no-cov
uv run ruff check src/storage/decision_memory.py tests/test_decision_memory_*.py
```

Expected: 0 failures, 0 lint errors.

- [ ] **Step 4: Run full repository verification**

```bash
uv run python scripts/check_private_corpus.py --tracked-only
uv run ruff check tests
uv run pytest tests/ -v --tb=short --no-cov
uv run python tests/quality_gate.py
```

Expected: all pass and quality gate remains above the existing threshold.

- [ ] **Step 5: Review PR diff**

Verify explicitly:
- no private source text, Drive id, file path, credentials, source inventory, full memo prose, or full rebuttal prose is persisted or committed;
- `CouncilOS` has no storage dependency;
- anonymous Council OS behavior remains valid;
- every read/update is user-scoped;
- cross-user access returns 404;
- capture failures do not fail streaming;
- calibration uses blind votes and excludes null `resolved_vote` outcomes;
- no history retrieval/prompt injection was accidentally added.

- [ ] **Step 6: Merge only after fresh HEAD verification**

Open a draft PR early during implementation. After review fixes and a fresh successful GitHub Actions run on the final HEAD, mark ready and squash merge into `main`.
