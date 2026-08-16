# Live Evidence Layer v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded current-web evidence to Council OS after rebuttals and before Red Team/Evidence Judge, with Tavily-backed retrieval, strict privacy and prompt-injection boundaries, Evidence-Judge gating, and sanitized Decision Memory diagnostics.

**Architecture:** A focused `src/council/live_evidence.py` module owns query sanitization, deterministic query planning, Tavily adaptation, URL/source normalization, deduplication, and fixed failure semantics. `CouncilOS` invokes the provider only after rebuttals, passes sanitized source cards to Red Team and Evidence Judge, and passes only Evidence-Judge-accepted cards to Chairman. `DecisionMemoryStore` persists only `LiveEvidenceSummary`, never search queries, titles, URLs, snippets, Tavily answers, or raw provider errors.

**Tech Stack:** Python 3.11+, Pydantic, asyncio, existing `TavilySearchPlugin`, SQLite, pytest.

## Global Constraints

- Live Evidence runs after all rebuttals complete and before Red Team.
- Blind memos and rebuttals receive no live-evidence data.
- At most 2 distinct search queries and at most 5 requested Tavily results per query.
- The external search boundary receives only a sanitized current decision question plus deterministic public focus terms; never private RAG, source inventory, attachment text, expert memo/rebuttal prose, or Decision Memory data.
- Tavily `answer` is ignored. `relevance_score` is search relevance, not credibility.
- External snippets are untrusted data; no instructions inside snippets may affect orchestration, schemas, tools, routing, framework selection, or storage.
- Chairman receives only Evidence-Judge-accepted live source cards.
- Decision Memory stores only sanitized live-evidence diagnostics.
- Live evidence is best-effort: disabled/no-match/unavailable states never fail the Council decision path.
- No GitHub Actions workflow changes and no GitHub Actions acceptance gate.

---

### Task 1: Typed live-evidence contracts

**Files:**
- Modify: `src/council/council_os_models.py`
- Create: `tests/test_live_evidence_models.py`

**Interfaces:**
- Produces: `LiveEvidenceStatus`, `LiveEvidenceSource`, `LiveEvidenceContext`, `LiveEvidenceRejection`, `LiveEvidenceAssessment`, `LiveEvidenceSummary`.
- Extends: `EvidenceAssessment.live_evidence`, `CouncilOSResult.live_evidence_summary`.

- [ ] **Step 1: Write failing model tests**

```python
from src.council.council_os_models import (
    LiveEvidenceAssessment,
    LiveEvidenceRejection,
    LiveEvidenceSource,
    LiveEvidenceSummary,
)


def test_live_source_bounds_and_score():
    source = LiveEvidenceSource(
        evidence_id="web_abc123",
        query_index=0,
        title="x" * 300,
        canonical_url="https://example.com/a",
        domain="www.EXAMPLE.com",
        snippet="hello\x00" + "z" * 800,
        relevance_score=9,
        fetched_at="2026-08-16T12:00:00+00:00",
    )
    assert len(source.title) <= 180
    assert len(source.snippet) <= 600
    assert "\x00" not in source.snippet
    assert source.domain == "example.com"
    assert source.relevance_score == 1.0


def test_live_rejection_reason_is_allowlisted():
    rejection = LiveEvidenceRejection(evidence_id="web_a", reason="free text from model")
    assert rejection.reason == "other_evidence_issue"


def test_live_summary_contains_only_diagnostics():
    summary = LiveEvidenceSummary(
        status="ok",
        query_count=1,
        source_count=1,
        source_domains=["Example.COM", "example.com"],
        accepted_evidence_ids=["web_a", "web_a"],
        rejected_evidence_ids=["web_b"],
        error_labels=["partial_search_failure", "private_exception"],
    )
    dumped = summary.model_dump()
    assert summary.source_domains == ["example.com"]
    assert summary.accepted_evidence_ids == ["web_a"]
    assert summary.error_labels == ["partial_search_failure"]
    assert "snippet" not in dumped and "url" not in dumped
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_live_evidence_models.py -q`
Expected: import/contract failures because live-evidence models do not exist.

- [ ] **Step 3: Add minimal Pydantic contracts**

Implement fixed statuses `ok | no_matches | disabled | unavailable`; source bounds; `http/https` URL validation; domain normalization; fixed rejection labels; fixed source-conflict labels; summary deduplication; fixed error labels `partial_search_failure`, `live_query_redacted`, `live_evidence_unavailable`.

- [ ] **Step 4: Run model tests GREEN**

Run: `python -m pytest tests/test_live_evidence_models.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/council/council_os_models.py tests/test_live_evidence_models.py
git commit -m "feat: add live evidence contracts"
```

### Task 2: Query sanitization and Tavily provider

**Files:**
- Create: `src/council/live_evidence.py`
- Create: `tests/test_live_evidence_provider.py`
- Reuse: `src/plugins/web_search.py`

**Interfaces:**
- Produces: `sanitize_live_query(question: str) -> str`, `plan_live_queries(question: str, profile: ProblemProfile, framework_ids: list[str]) -> list[str]`, `TavilyLiveEvidenceProvider.collect(...) -> LiveEvidenceContext`.

- [ ] **Step 1: Write failing sanitizer/planner/provider tests**

```python
async def test_provider_caps_calls_and_ignores_tavily_answer():
    fake = FakeSearchPlugin([...])
    provider = TavilyLiveEvidenceProvider(search_plugin=fake, enabled=True)
    result = await provider.collect("Should we enter Germany?", profile, ["strategic_choice"])
    assert len(fake.calls) <= 2
    assert all(call["max_results"] == 5 for call in fake.calls)
    assert all("answer" not in source.model_dump() for source in result.sources)


def test_query_redacts_secrets_and_email():
    raw = "Launch? bearer sk-secret-abcdefghijklmnopqrstuvwxyz user@example.com https://x.test/a?token=123"
    clean = sanitize_live_query(raw)
    assert "sk-secret" not in clean
    assert "user@example.com" not in clean
    assert "token=123" not in clean
```

Add cases for opaque tokens, deterministic max-2 query planning, empty-after-redaction -> disabled, all calls fail -> unavailable, partial failure -> `ok + partial_search_failure`, no usable result -> no_matches, canonical URL stripping query/fragment, deterministic SHA-256 `evidence_id`, dedupe/order, invalid scheme rejection, control-character stripping.

- [ ] **Step 2: Run provider tests RED**

Run: `python -m pytest tests/test_live_evidence_provider.py -q`
Expected: missing module/functions.

- [ ] **Step 3: Implement provider**

Use `TavilySearchPlugin.execute(query=..., max_results=5, search_depth="basic")`. Treat a result as usable only when it has a valid http/https URL and at least one non-empty bounded field among title/snippet. Never copy plugin error text. Never consume `data["answer"]`.

- [ ] **Step 4: Run provider tests GREEN**

Run: `python -m pytest tests/test_live_evidence_provider.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/council/live_evidence.py tests/test_live_evidence_provider.py
git commit -m "feat: add bounded Tavily live evidence provider"
```

### Task 3: Council OS stage integration and Evidence-Judge gate

**Files:**
- Modify: `src/council/council_os.py`
- Create: `tests/test_council_os_live_evidence.py`
- Regression: `tests/test_council_os_frameworks.py`, `tests/test_council_os_learning.py`, `tests/test_council_os_v1_compat.py`

**Interfaces:**
- Constructor: optional `live_evidence_provider`.
- New helpers: `_collect_live_evidence`, `_live_evidence_payload`, `_sanitize_live_evidence_assessment`, `_approved_live_evidence_payload`, `_live_evidence_summary`.
- Stage methods keep old call compatibility through optional/default live-evidence arguments.

- [ ] **Step 1: Write failing integration tests**

Create deterministic fake LLM/provider tests that record stage order and prompts. Assert:

```python
assert order.index("rebuttal_done") < order.index("live_collect") < order.index("red_team")
assert "MALICIOUS_LIVE_SENTINEL" not in blind_prompt
assert "MALICIOUS_LIVE_SENTINEL" not in rebuttal_prompt
assert "MALICIOUS_LIVE_SENTINEL" in red_team_prompt
assert "MALICIOUS_LIVE_SENTINEL" in evidence_judge_prompt
assert "REJECTED_LIVE_SENTINEL" not in chairman_prompt
assert "ACCEPTED_LIVE_SENTINEL" in chairman_prompt
```

Also assert unknown evidence ids are removed, accepted ids win over duplicate rejection, free-text rejection/source-conflict labels collapse to fixed labels, provider exception becomes unavailable and deliberation continues, disabled/no_matches are non-fatal, and live-evidence prompts carry an explicit untrusted-external-data instruction.

- [ ] **Step 2: Run integration tests RED**

Run: `python -m pytest tests/test_council_os_live_evidence.py -q`
Expected: missing constructor/helper/stage behavior.

- [ ] **Step 3: Implement pipeline integration**

After `_run_rebuttals`, call the provider with only `query`, `profile`, and selected framework ids. Append `live_evidence_unavailable` to orchestration errors only for unexpected/provider-unavailable failures; disabled/no_matches remain non-errors. Pass bounded source cards to Red Team and Evidence Judge. Extend Evidence Judge JSON contract with `live_evidence`. Build Chairman payload exclusively from accepted ids. Never pass rejected source text/URL/title to Chairman.

- [ ] **Step 4: Preserve old helper signatures**

All modified internal stage helpers accept `live_evidence: LiveEvidenceContext | None = None` so v1/v2 callers remain valid.

- [ ] **Step 5: Run focused and regression tests GREEN**

Run:
`python -m pytest tests/test_council_os_live_evidence.py tests/test_council_os_frameworks.py tests/test_council_os_learning.py tests/test_council_os_v1_compat.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/council/council_os.py tests/test_council_os_live_evidence.py
git commit -m "feat: gate live evidence through council review stages"
```

### Task 4: Decision Memory persistence

**Files:**
- Modify: `src/storage/decision_memory.py`
- Create: `tests/test_decision_memory_live_evidence.py`
- Regression: `tests/test_decision_memory_frameworks.py`, `tests/test_decision_memory_v2_capture.py`, `tests/test_decision_memory_storage.py`

**Interfaces:**
- Additive nullable SQLite column: `live_evidence_json`.
- `capture_decision` serializes `result.live_evidence_summary.model_dump(mode="json")` only.
- Decision detail returns `live_evidence_summary` or `None`.

- [ ] **Step 1: Write failing migration/privacy tests**

Create a v2/framework-era SQLite schema without `live_evidence_json`, initialize `DecisionMemoryStore`, verify migration, capture a result with a live summary, and assert readback. Add sentinel assertions that stored JSON cannot contain `https://`, snippets, titles, raw search queries, Tavily answer, or raw exception strings.

- [ ] **Step 2: Run storage tests RED**

Run: `python -m pytest tests/test_decision_memory_live_evidence.py -q`
Expected: missing column/serialization.

- [ ] **Step 3: Implement additive migration and summary capture**

Follow the existing `learning_context_json` and `framework_selection_json` migration/capture pattern. Do not persist `LiveEvidenceContext`.

- [ ] **Step 4: Run storage regressions GREEN**

Run:
`python -m pytest tests/test_decision_memory_live_evidence.py tests/test_decision_memory_frameworks.py tests/test_decision_memory_v2_capture.py tests/test_decision_memory_storage.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/storage/decision_memory.py tests/test_decision_memory_live_evidence.py
git commit -m "feat: persist sanitized live evidence diagnostics"
```

### Task 5: Documentation, privacy regressions, and final local gate

**Files:**
- Create: `docs/LIVE_EVIDENCE_V1.md`
- Modify: `README.md`
- Test: all new Live Evidence tests plus existing Council OS, Framework Selector, Decision Memory, private retrieval/privacy tests present in the local working copy.

**Interfaces:**
- Documentation must state stage order, 2x5 limits, Tavily-answer exclusion, prompt-injection boundary, disabled/unavailable semantics, Evidence Judge gate, and Decision Memory privacy boundary.

- [ ] **Step 1: Add explicit privacy regression**

Use synthetic sentinels for private RAG, memo, rebuttal, Decision Memory and attachment data. Assert none reaches the fake search plugin query/call arguments.

- [ ] **Step 2: Run all Live Evidence tests**

Run: `python -m pytest tests/test_live_evidence_models.py tests/test_live_evidence_provider.py tests/test_council_os_live_evidence.py tests/test_decision_memory_live_evidence.py -q`
Expected: PASS.

- [ ] **Step 3: Write docs and README update**

Document the exact flow:

```text
blind -> Decision Memory learning -> rebuttals -> Live Evidence -> Red Team -> Evidence Judge -> Chairman
```

State clearly that live snippets are transient untrusted evidence, rejected source text never reaches Chairman, and Decision Memory stores diagnostics only.

- [ ] **Step 4: Run branch-equivalent regression gate**

Run the broadest locally materialized test set covering Council OS, Framework Selector, Decision Memory, private retrieval/privacy plus:

```bash
python -m compileall -q src tests
PYTHONPATH=. python tests/quality_gate.py
```

Run Ruff only if locally installed; otherwise record that no fresh Ruff result is claimed.

- [ ] **Step 5: Verify no workflow changes**

Diff branch against `main`; assert no `.github/workflows/*` path changed.

- [ ] **Step 6: Commit docs**

```bash
git add README.md docs/LIVE_EVIDENCE_V1.md tests
git commit -m "docs: document Live Evidence v1"
```

- [ ] **Step 7: Review, publish, PR, merge**

Request code review, fix any blocker with RED->GREEN tests, rerun the fresh local gate on the exact branch-equivalent blobs, create a draft PR, inspect the complete diff and review threads, mark ready, and squash-merge only when the PR head SHA still matches the verified tree. Do not use GitHub Actions as an acceptance gate.