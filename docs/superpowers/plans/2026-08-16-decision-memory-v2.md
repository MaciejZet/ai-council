# Decision Memory v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add controlled, user-scoped learning from resolved Decision Memory outcomes to Council OS without contaminating the blind round or weakening privacy boundaries.

**Architecture:** Keep Decision Memory writes in the existing store, add a read-only `DecisionLearningStore`, and build deterministic `LearningContext` objects after blind memos complete. Rebuttals, Red Team and Evidence Judge may inspect sanitized learning context; Chairman receives only Evidence-Judge-approved historical signals. Existing behavior remains valid when learning is disabled, unavailable, or below sample thresholds.

**Tech Stack:** Python 3.12, Pydantic v2, SQLite, asyncio, pytest, Ruff.

## Global Constraints

- Blind experts receive no Decision Memory history, calibration, analogies, postmortems, notes, or prior verdicts.
- Sample strengths are fixed: `0-4 -> none`, `5-14 -> weak`, `15+ -> normal`.
- Analogies are user-scoped, deterministic, sanitized, and capped at 3.
- Historical performance is an attention/calibration signal, never an automatic vote multiplier or verdict rule.
- Cross-user history must never enter builder output, prompts, diagnostics, or capture.
- Learning failure must not fail Council OS.
- Existing v1 SQLite databases must migrate without data loss.
- GitHub Actions are not used as the implementation or verification gate for this phase.

---

### Task 1: Add typed learning contracts

**Files:**
- Modify: `src/council/council_os_models.py`
- Test: `tests/test_decision_learning_models.py`

**Interfaces:**
- Produces: `SampleStrength`, `ExpertCalibrationSignal`, `AnalogDecision`, `HistoricalAnalogyRejection`, `HistoricalContextAssessment`, `LearningContext`, `LearningContextSummary`.
- Extends: `EvidenceAssessment.historical_context` and `CouncilOSResult.learning_context_summary` with backward-compatible defaults.

- [ ] **Step 1: Write failing model tests**

Create tests proving defaults preserve existing `CouncilOSResult` construction, sample-strength values validate, summaries contain no historical free-text fields, and `HistoricalContextAssessment` serializes accepted/rejected analogy ids.

- [ ] **Step 2: Run model tests and verify RED**

Run: `pytest tests/test_decision_learning_models.py -v`
Expected: import/attribute failures because v2 models do not exist.

- [ ] **Step 3: Implement minimal Pydantic contracts**

Use `Literal["none", "weak", "normal"]` for sample strength and `Literal["ok", "insufficient_history", "disabled", "unavailable"]` for learning status. Keep all new `EvidenceAssessment`/`CouncilOSResult` fields optional or defaulted.

- [ ] **Step 4: Run model tests and verify GREEN**

Run: `pytest tests/test_decision_learning_models.py -v`
Expected: PASS.

---

### Task 2: Add DecisionLearningStore and v1-to-v2 migration

**Files:**
- Create: `src/storage/decision_learning.py`
- Modify: `src/storage/decision_memory.py`
- Test: `tests/test_decision_learning_store.py`
- Test: `tests/test_decision_memory_storage.py`

**Interfaces:**
- `DecisionLearningStore(db_path: Path | str | None = None)`
- `resolved_decisions(user_id: str, *, primary_domain: str | None = None) -> list[dict[str, Any]]`
- `expert_predictions(user_id: str, expert_ids: list[str], primary_domain: str) -> list[dict[str, Any]]`
- `chairman_predictions(user_id: str, primary_domain: str) -> list[dict[str, Any]]`
- `DecisionMemoryStore.capture_decision(...)` persists sanitized `LearningContextSummary` only.

- [ ] **Step 1: Write failing storage/migration tests**

Create a v1-shaped SQLite database manually, initialize `DecisionMemoryStore`, assert `learning_context_json` is added without deleting rows, and assert learning reads return only allowed metadata. Seed two users with sentinel notes/postmortems and prove user B material never appears in user A reads.

- [ ] **Step 2: Run storage tests and verify RED**

Run: `pytest tests/test_decision_learning_store.py tests/test_decision_memory_storage.py -v`
Expected: missing module/column/read methods.

- [ ] **Step 3: Implement migration**

During `DecisionMemoryStore._initialize`, inspect `PRAGMA table_info(decisions)` and run exactly one `ALTER TABLE decisions ADD COLUMN learning_context_json TEXT` when absent. Existing rows remain `NULL`.

- [ ] **Step 4: Implement read-only store**

Select only decision ids, timestamps, profile metadata, verdict/confidence, resolved vote/status, and blind expert vote/confidence. Do not select query, recommendation, memo text, postmortem, notes, source inventory, or private-source fields into returned learning objects.

- [ ] **Step 5: Extend capture/read paths**

Serialize only `result.learning_context_summary.model_dump(mode="json")` when present. Add the stored sanitized summary to decision detail output. Do not persist full `LearningContext` or analogy source rows.

- [ ] **Step 6: Run storage tests and verify GREEN**

Run: `pytest tests/test_decision_learning_store.py tests/test_decision_memory_storage.py -v`
Expected: PASS.

---

### Task 3: Build deterministic LearningContextBuilder

**Files:**
- Create: `src/council/learning_context.py`
- Test: `tests/test_learning_context.py`

**Interfaces:**
- Constants: `WEAK_SAMPLE_MIN = 5`, `NORMAL_SAMPLE_MIN = 15`, `MAX_ANALOGIES = 3`.
- `sample_strength(sample_size: int) -> SampleStrength`.
- `LearningContextBuilder(store: DecisionLearningStore)`.
- `build(user_id: str, profile: ProblemProfile, routed_expert_ids: list[str], blind_memos: list[ExpertMemo]) -> LearningContext`.

- [ ] **Step 1: Write failing threshold and ranking tests**

Assert sample sizes 0/4/5/14/15 map exactly to none/none/weak/weak/normal. Seed resolved decisions and assert analogy ranking uses `+4 primary_domain`, `+3 decision_kind`, `+2 reversibility`, `+2 risk_level`, capped secondary-domain matches, deterministic recency/id tie breaks, and max 3 outputs.

- [ ] **Step 2: Write failing calibration/privacy tests**

Assert per-expert domain metrics use blind votes, deterministic ordering uses sample strength then lower Brier-like error then hit rate then expert id, and forbidden sentinel text from queries/postmortems/notes cannot appear in `model_dump_json()`.

- [ ] **Step 3: Write failing minority/bias tests**

Assert protected minority requires normal strength plus stronger calibration than majority experts plus a dissenting blind vote. Assert no protection at none/weak. Add conservative deterministic alerts for overconfidence, underconfidence, go bias, test bias, and consensus failure only when weak-or-better evidence supports them.

- [ ] **Step 4: Implement minimal deterministic builder**

No LLM calls. Catch store exceptions at the boundary and return `LearningContext(status="unavailable", error_labels=["learning_store_unavailable"])`. When no scored history exists, return `insufficient_history`. Low-sample metrics may be diagnostic but have no active influence.

- [ ] **Step 5: Run builder tests and verify GREEN**

Run: `pytest tests/test_learning_context.py -v`
Expected: PASS.

---

### Task 4: Integrate learning after blind round with stage-specific exposure

**Files:**
- Modify: `src/council/council_os.py`
- Test: `tests/test_council_os_learning.py`
- Test: `tests/test_council_os_deliberate.py`

**Interfaces:**
- `CouncilOS(..., learning_context_provider: Callable[..., LearningContext] | None = None)`.
- Internal helper `_build_learning_context(...)` returns disabled/unavailable context safely.
- Rebuttal/Red Team/Evidence Judge prompts receive sanitized context subsets.
- Chairman receives only an approved context derived from `HistoricalContextAssessment`.

- [ ] **Step 1: Write blind-firewall RED test**

Use a recording fake LLM and a provider returning a unique historical sentinel. Run deliberation and assert every `[STAGE:BLIND]` system/user prompt is free of the sentinel and every learning-provider invocation occurs only after blind LLM calls complete.

- [ ] **Step 2: Write stage-exposure RED tests**

Assert rebuttals can receive expert calibration and analog metadata; Red Team receives bias/minority labels; Evidence Judge receives the full sanitized learning context; Chairman receives accepted analogies only and no rejected analogy ids as usable context.

- [ ] **Step 3: Add historical adjudication schema to Evidence Judge prompt**

Require accepted analogy ids, rejected analogy objects with stable reason labels, usable calibration expert ids, too-weak calibration expert ids, and current-evidence conflict labels. On parse failure, return an empty safe assessment.

- [ ] **Step 4: Add minority-protection obligation**

When learning context marks a protected minority, Red Team and Chairman prompts explicitly require discussion of that dissent. The final vote remains unconstrained.

- [ ] **Step 5: Add learning summary construction**

Populate `CouncilOSResult.learning_context_summary` from builder status plus Evidence Judge adjudication. Store counts, active sample strengths, bias labels, protected expert ids, rejected analogy id/reason labels, and `influenced_final_stage` boolean. Include no historical free text.

- [ ] **Step 6: Add failure fallback**

Provider/builder exceptions become fixed `learning_context_unavailable` orchestration labels and do not stop rebuttal, Red Team, Evidence Judge, or Chairman.

- [ ] **Step 7: Run Council learning tests and verify GREEN**

Run: `pytest tests/test_council_os_learning.py tests/test_council_os_deliberate.py -v`
Expected: PASS.

---

### Task 5: Wire authenticated user scope at API boundary

**Files:**
- Modify: `src/api/decision_memory.py`
- Modify: `src/council/modes.py` only if needed to pass a request-scoped user id without storage imports in core reasoning.
- Test: `tests/test_decision_learning_api.py`
- Test: `tests/test_decision_memory_capture_api.py`

**Interfaces:**
- Learning is enabled only for authenticated Council OS requests that resolve a user id.
- Anonymous or invalid-session Council OS remains functional with learning disabled and no persistence.
- No user id is placed in LLM prompts.

- [ ] **Step 1: Write failing API ownership tests**

Create two authenticated users and distinct histories. Run Council OS for user A with a fake learning builder/store and assert only A-scoped records influence the result. Assert anonymous requests return a valid stream with learning disabled.

- [ ] **Step 2: Implement narrow request-scope bridge**

Pass the resolved user id to the Council OS learning provider through request/mode construction or an equivalent narrow callable. Keep `CouncilOS` free from session validation and HTTP imports.

- [ ] **Step 3: Preserve best-effort capture**

Capture the sanitized learning summary when the `council_os_result` SSE event is persisted. Storage or learning errors keep the original stream intact with fixed log messages.

- [ ] **Step 4: Run API tests and verify GREEN**

Run: `pytest tests/test_decision_learning_api.py tests/test_decision_memory_capture_api.py -v`
Expected: PASS.

---

### Task 6: Privacy regression, documentation, and local verification

**Files:**
- Create: `tests/test_decision_learning_privacy.py`
- Modify: `README.md`
- Do not modify: `.github/workflows/ci.yml`

**Interfaces:**
- Public documentation explains controlled adaptation, thresholds, privacy, and that historical learning starts after the blind round.

- [ ] **Step 1: Add privacy sentinel tests**

Insert unique sentinels into another user's query, postmortem, notes, simulated raw memo/source fields, and storage exception text. Assert none appear in blind prompts, later prompts outside explicitly allowed ids/metadata, `LearningContextSummary`, current-decision SQLite capture, or public Decision Memory API diagnostics.

- [ ] **Step 2: Run focused Decision Memory v2 suite**

Run: `pytest tests/test_decision_learning_*.py tests/test_learning_context.py tests/test_council_os_learning.py -v`
Expected: PASS.

- [ ] **Step 3: Run local lint**

Run: `ruff check src/council/council_os_models.py src/council/learning_context.py src/council/council_os.py src/storage/decision_learning.py src/storage/decision_memory.py src/api/decision_memory.py tests/test_decision_learning_*.py tests/test_learning_context.py tests/test_council_os_learning.py`
Expected: PASS.

- [ ] **Step 4: Run affected regression suite**

Run: `pytest tests/test_council_os*.py tests/test_decision_memory_*.py tests/test_business_routing.py -v`
Expected: PASS.

- [ ] **Step 5: Run repository quality gate locally when the complete test assets are available**

Run: `python tests/quality_gate.py`
Expected: PASS and no regression below the project threshold.

- [ ] **Step 6: Update README**

Document the `5/15` thresholds, blind-round firewall, metadata-only analogies, Evidence Judge rejection, minority protection, and the fact that v2 does not change routing or numerically multiply votes.

- [ ] **Step 7: Publish the verified branch and open/update the PR**

Summarize local verification evidence in the PR body. Do not use GitHub Actions results as an acceptance gate.
