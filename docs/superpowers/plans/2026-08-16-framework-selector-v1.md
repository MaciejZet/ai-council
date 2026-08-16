# Framework Selector / Decision Doctrine v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic framework selection to Council OS so each decision gets a small, auditable set of analytical lenses, framework-aware private retrieval, `[FMW]` discipline, and sanitized Decision Memory diagnostics without weakening blind-round isolation or privacy.

**Architecture:** Add a versioned immutable framework registry plus a pure deterministic selector that runs after problem profiling/routing and before expert retrieval. Extend the existing retriever with optional `framework_tags`; Council OS first tries framework-aware retrieval and falls back once to the existing domain/expert query on `no_matches`. Framework metadata flows through Red Team, Evidence Judge, Chairman, and Decision Memory only as sanitized ids, scores, reason labels, assignments, and retrieval-status labels.

**Tech Stack:** Python 3.12, dataclasses, Pydantic v2, SQLite, asyncio, pytest. No new runtime dependency.

## Global Constraints

- Framework selection is deterministic. No LLM call is allowed inside the selector.
- Select at most 3 frameworks globally and at most 2 frameworks per routed expert.
- A framework must score at least `5` to be eligible.
- Framework-derived material claims remain `[FMW]`; `[F]` requires independent supplied evidence.
- Framework selection uses only the current query, `ProblemProfile`, and routed expert ids. It receives no Decision Memory history, memos, rebuttals, Red Team output, Evidence Judge output, or RAG chunks.
- Framework-aware retrieval retries the existing base expert/domain query exactly once only when the first result is `no_matches`.
- Retrieval status `unavailable` remains `unavailable` and does not trigger a second backend call.
- Public repository code and diagnostics may contain framework ids, short original descriptions, generic questions, public tag names, scores, and reason labels. They must not contain private book text, summaries, Drive ids, raw retrieved chunks, private source paths, or historical postmortem/notes copied into prompts.
- Decision Memory v2 remains after blind memos in the pipeline.
- GitHub Actions are not used as the implementation or acceptance gate for this phase.

---

## File map

### New files

- `src/council/framework_registry.py`: immutable framework definitions and policy version.
- `src/council/framework_selector.py`: pure scoring, tie-breaking, assignment, and empty-selection fallback.
- `tests/test_framework_registry.py`: registry integrity and privacy-safety checks.
- `tests/test_framework_selector.py`: deterministic selection, score thresholds, caps, and tie-breaking.
- `tests/test_framework_retrieval.py`: framework tag filters and fallback semantics.
- `tests/test_council_os_frameworks.py`: orchestration order, blind prompt cards, Evidence Judge gating, and selector failure fallback.
- `tests/test_decision_memory_frameworks.py`: SQLite migration/capture and privacy regression.

### Modified files

- `src/council/council_os_models.py`: typed framework contracts, Evidence Judge framework assessment, Council result summary.
- `src/knowledge/retriever.py`: optional `framework_tags` filter in both structured and list wrappers.
- `src/council/council_os.py`: selector dependency, framework-aware retrieval, framework cards, downstream framework context, summary construction.
- `src/storage/decision_memory.py`: additive `framework_selection_json` migration and sanitized capture/readback.
- `README.md`: describe selector position, `[FMW]` doctrine, retrieval fallback, and Decision Memory summary.
- `docs/FRAMEWORK_SELECTOR_V1.md`: operational behavior and privacy boundary.

---

### Task 1: Add typed framework contracts

**Files:**
- Modify: `src/council/council_os_models.py`
- Test: `tests/test_framework_selector.py`

**Interfaces:**
- Produces: `FrameworkMatch`, `FrameworkSelection`, `FrameworkFactMisclassification`, `FrameworkAssessment`, `FrameworkSelectionSummary`.
- Extends: `EvidenceAssessment.framework_assessment` with a backward-compatible default.
- Extends: `CouncilOSResult.framework_selection_summary` with a backward-compatible default.

- [ ] **Step 1: Write failing model tests**

Add tests equivalent to:

```python
from src.council.council_os_models import (
    FrameworkAssessment,
    FrameworkFactMisclassification,
    FrameworkMatch,
    FrameworkSelection,
    FrameworkSelectionSummary,
)


def test_framework_models_are_sanitized_and_serializable():
    selection = FrameworkSelection(
        policy_version="framework-selector-v1",
        matches=[
            FrameworkMatch(
                framework_id="value_equation",
                score=8,
                reason_labels=["primary_domain", "routed_expert"],
                assigned_expert_ids=["offer_pricing"],
            )
        ],
        by_expert={"offer_pricing": ["value_equation"]},
    )
    summary = FrameworkSelectionSummary(
        policy_version=selection.policy_version,
        selected_framework_ids=["value_equation"],
        by_expert=selection.by_expert,
        reason_labels_by_framework={"value_equation": ["primary_domain"]},
        retrieval_status_by_expert={"offer_pricing": "framework_match"},
        rejected_framework_ids=[],
        selector_error_labels=[],
    )
    payload = summary.model_dump(mode="json")
    assert "book_text" not in payload
    assert payload["selected_framework_ids"] == ["value_equation"]


def test_framework_fact_misclassification_uses_stable_claim_ref():
    item = FrameworkFactMisclassification(
        claim_ref="marketing:2",
        framework_id="positioning_category",
        reason="framework_rule_presented_as_fact",
    )
    assessment = FrameworkAssessment(misclassified_fact_claims=[item])
    assert assessment.misclassified_fact_claims[0].claim_ref == "marketing:2"
```

Also extend an existing `CouncilOSResult` construction test to prove the new field defaults to `None` or an empty backward-compatible value.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python -m pytest tests/test_framework_selector.py -q
```

Expected: import failures because the framework models do not exist yet.

- [ ] **Step 3: Implement minimal Pydantic models**

Add:

```python
class FrameworkMatch(BaseModel):
    framework_id: str
    score: int
    reason_labels: list[str] = Field(default_factory=list)
    assigned_expert_ids: list[str] = Field(default_factory=list)


class FrameworkSelection(BaseModel):
    policy_version: str
    matches: list[FrameworkMatch] = Field(default_factory=list)
    by_expert: dict[str, list[str]] = Field(default_factory=dict)


class FrameworkFactMisclassification(BaseModel):
    claim_ref: str
    framework_id: str | None = None
    reason: str


class FrameworkAssessment(BaseModel):
    misclassified_fact_claims: list[FrameworkFactMisclassification] = Field(default_factory=list)
    framework_overreach_labels: list[str] = Field(default_factory=list)
    rejected_framework_ids: list[str] = Field(default_factory=list)


class FrameworkSelectionSummary(BaseModel):
    policy_version: str
    selected_framework_ids: list[str] = Field(default_factory=list)
    by_expert: dict[str, list[str]] = Field(default_factory=dict)
    reason_labels_by_framework: dict[str, list[str]] = Field(default_factory=dict)
    retrieval_status_by_expert: dict[str, str] = Field(default_factory=dict)
    rejected_framework_ids: list[str] = Field(default_factory=list)
    selector_error_labels: list[str] = Field(default_factory=list)
```

Add `framework_assessment: FrameworkAssessment = Field(default_factory=FrameworkAssessment)` to `EvidenceAssessment`, and `framework_selection_summary: FrameworkSelectionSummary | None = None` to `CouncilOSResult`.

- [ ] **Step 4: Run the model tests and verify GREEN**

Run:

```bash
python -m pytest tests/test_framework_selector.py -q
```

Expected: model-only tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/council/council_os_models.py tests/test_framework_selector.py
git commit -m "feat: add framework selection contracts"
```

---

### Task 2: Add immutable framework registry and pure selector

**Files:**
- Create: `src/council/framework_registry.py`
- Create: `src/council/framework_selector.py`
- Create: `tests/test_framework_registry.py`
- Modify: `tests/test_framework_selector.py`

**Interfaces:**
- Produces: `FRAMEWORK_POLICY_VERSION`, `FRAMEWORK_REGISTRY`, `FrameworkDefinition`, `select_frameworks(query, profile, routed_expert_ids) -> FrameworkSelection`.
- Consumes: `ProblemProfile`, `FrameworkMatch`, `FrameworkSelection` from Task 1.

- [ ] **Step 1: Write failing registry tests**

```python
from src.council.framework_registry import FRAMEWORK_POLICY_VERSION, FRAMEWORK_REGISTRY


def test_registry_has_expected_unique_ids():
    assert FRAMEWORK_POLICY_VERSION == "framework-selector-v1"
    assert set(FRAMEWORK_REGISTRY) == {
        "strategic_choice",
        "competitive_advantage",
        "positioning_category",
        "value_equation",
        "customer_job_evidence",
        "growth_loop",
        "operating_constraint",
        "reversibility_experiment",
    }
    assert len(FRAMEWORK_REGISTRY) == len(set(FRAMEWORK_REGISTRY))


def test_registry_contains_only_short_public_framework_copy():
    for framework in FRAMEWORK_REGISTRY.values():
        assert framework.description
        assert len(framework.description) <= 280
        assert 2 <= len(framework.diagnostic_questions) <= 3
        serialized = repr(framework).casefold()
        assert "drive_file_id" not in serialized
        assert "private-library" not in serialized
```

- [ ] **Step 2: Write failing selector behavior tests**

Create representative `ProblemProfile` fixtures and assert:

```python
selection = select_frameworks(
    "Should we raise price and change packaging for our B2B offer?",
    ProblemProfile(
        primary_domain="offer_pricing",
        secondary_domains=["sales"],
        decision_kind="pricing",
        reversibility="reversible",
        risk_level="medium",
    ),
    ["offer_pricing", "sales", "strategy", "marketing"],
)
assert selection.matches[0].framework_id == "value_equation"
assert len(selection.matches) <= 3
assert all(len(items) <= 2 for items in selection.by_expert.values())
```

Add tests for strategy, positioning, customer/JTBD, growth, operations, and reversible-test queries. Add an empty-selection test where all candidates remain below `5`.

Add an exact threshold test by calling the internal pure scorer or a public `score_framework(...)` helper with a fixture that yields `5` and a second fixture that yields `4`.

- [ ] **Step 3: Run registry/selector tests and verify RED**

```bash
python -m pytest tests/test_framework_registry.py tests/test_framework_selector.py -q
```

Expected: modules/functions missing.

- [ ] **Step 4: Implement the registry**

Use:

```python
@dataclass(frozen=True)
class FrameworkDefinition:
    id: str
    name: str
    domains: tuple[str, ...]
    decision_kinds: tuple[str, ...]
    expert_ids: tuple[str, ...]
    trigger_keywords: tuple[str, ...]
    framework_tags: tuple[str, ...]
    diagnostic_questions: tuple[str, ...]
    description: str
```

Define the 8 framework ids exactly as listed in the design spec, with short original descriptions and generic diagnostic questions. Keep registry order stable and make `FRAMEWORK_REGISTRY` insertion order authoritative for tie-breaking.

- [ ] **Step 5: Implement deterministic scoring and assignment**

In `framework_selector.py`, define:

```python
FRAMEWORK_MIN_SCORE = 5
MAX_SELECTED_FRAMEWORKS = 3
MAX_FRAMEWORKS_PER_EXPERT = 2
```

Implement boundary-aware keyword matching equivalent to `business_routing._matches_keyword`.

Scoring rules:

```text
+4 primary-domain match
+2 per matching secondary domain, capped at +4
+3 decision-kind match
+2 per routed expert supported by the framework, capped at +4
+1 per trigger keyword, capped at +3
+1 reversibility_experiment bonus when the profile is reversible and the query contains test/experiment language
+1 strategic_choice bonus when the profile is hard_to_reverse or high risk
```

Return reason labels such as `primary_domain`, `secondary_domain`, `decision_kind`, `routed_expert`, `trigger_keyword`, `reversibility_bonus`, `high_risk_bonus` only when that rule contributes points.

Tie-break by descending score, then registry order, then framework id. Keep only candidates scoring `>= 5`, globally cap at 3, then assign only selected frameworks compatible with each routed expert, cap 2 per expert.

- [ ] **Step 6: Run registry/selector tests and verify GREEN**

```bash
python -m pytest tests/test_framework_registry.py tests/test_framework_selector.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/council/framework_registry.py src/council/framework_selector.py tests/test_framework_registry.py tests/test_framework_selector.py
git commit -m "feat: add deterministic framework selector"
```

---

### Task 3: Extend private retrieval with framework tags and safe fallback semantics

**Files:**
- Modify: `src/knowledge/retriever.py`
- Create: `tests/test_framework_retrieval.py`
- Modify: `tests/test_private_retrieval.py` only if an existing fixture needs the new optional argument.

**Interfaces:**
- Extends: `_build_filter(..., framework_tags: list[str] | None)`.
- Extends: `query_knowledge_result(..., framework_tags: list[str] | None = None)`.
- Extends: `query_knowledge(..., framework_tags: list[str] | None = None)`.
- Backward compatibility: omitted `framework_tags` produces the existing filter shape.

- [ ] **Step 1: Write failing filter tests**

```python
from src.knowledge.retriever import _build_filter


def test_framework_tags_are_added_only_when_supplied():
    with_framework = _build_filter(
        category=None,
        source_type=None,
        domains=["marketing"],
        experts=["marketing"],
        framework_tags=["positioning"],
    )
    assert {"framework_tags": {"$in": ["positioning"]}} in with_framework["$and"]

    without_framework = _build_filter(
        category=None,
        source_type=None,
        domains=["marketing"],
        experts=["marketing"],
        framework_tags=None,
    )
    assert "framework_tags" not in repr(without_framework)
```

Also test that `query_knowledge` forwards the parameter to `query_knowledge_result`.

- [ ] **Step 2: Run test and verify RED**

```bash
python -m pytest tests/test_framework_retrieval.py -q
```

Expected: unexpected keyword argument / signature mismatch.

- [ ] **Step 3: Implement the optional filter**

Add `framework_tags` to `_build_filter`, `query_knowledge_result`, and `query_knowledge`. Append:

```python
if framework_tags:
    clauses.append({"framework_tags": {"$in": framework_tags}})
```

Do not change existing behavior when omitted.

- [ ] **Step 4: Run retrieval tests and verify GREEN**

```bash
python -m pytest tests/test_framework_retrieval.py tests/test_private_retrieval.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/retriever.py tests/test_framework_retrieval.py tests/test_private_retrieval.py
git commit -m "feat: add framework tag retrieval filter"
```

---

### Task 4: Integrate selector and framework-aware retrieval into Council OS

**Files:**
- Modify: `src/council/council_os.py`
- Create: `tests/test_council_os_frameworks.py`
- Modify: `tests/test_council_os.py` only for backward-compatible constructor fixtures if required.

**Interfaces:**
- Consumes: `select_frameworks`, `FRAMEWORK_REGISTRY`, `FrameworkSelection`.
- Extends `CouncilOS.__init__` with an injectable selector callable defaulting to `select_frameworks`.
- Produces per-expert sanitized retrieval labels and `FrameworkSelectionSummary`.

- [ ] **Step 1: Write failing orchestration-order test**

Use fakes recording events:

```python
calls = []

def selector(query, profile, routed_ids):
    calls.append("selector")
    return FrameworkSelection(...)


def retriever(query, **kwargs):
    calls.append(("retrieve", tuple(kwargs.get("framework_tags") or [])))
    return KnowledgeRetrievalResult(status="no_matches")
```

Run a Council OS deliberation and assert selector is called after routing/profile construction but before the first retrieval and before any LLM blind memo call.

- [ ] **Step 2: Write failing retrieval-fallback tests**

For an expert with an assigned framework:

- first retrieval call contains framework tags;
- if first result is `no_matches`, second call omits framework tags;
- exactly two retrieval calls occur;
- diagnostic is `framework_no_match_fallback_ok` when fallback is `ok`;
- if first result is `unavailable`, exactly one retrieval call occurs and diagnostic is `framework_unavailable`.

For an expert with no assigned framework, assert one base retrieval and diagnostic `base_retrieval`.

- [ ] **Step 3: Write failing blind-prompt isolation tests**

Assert the selected expert's blind prompt contains:

```text
Selected framework lenses
[FMW]
```

and contains only framework ids/descriptions/questions assigned to that expert.

Assert it contains none of:

- Decision Memory analog ids;
- peer memo text;
- Red Team output;
- Chairman output.

- [ ] **Step 4: Run focused tests and verify RED**

```bash
python -m pytest tests/test_council_os_frameworks.py -q
```

Expected: constructor/selector/prompt behavior missing.

- [ ] **Step 5: Implement selector dependency and safe failure fallback**

Add a callable type such as:

```python
FrameworkSelector = Callable[[str, ProblemProfile, list[str]], FrameworkSelection]
```

`CouncilOS.__init__` accepts `framework_selector: FrameworkSelector = select_frameworks`.

After routing and before `_run_blind_memos`, call the selector inside `try/except`. On exception use:

```python
FrameworkSelection(
    policy_version=FRAMEWORK_POLICY_VERSION,
    matches=[],
    by_expert={},
)
```

and retain `selector_error_labels=["framework_selector_unavailable"]` for the final summary. Never expose exception text.

- [ ] **Step 6: Implement per-expert framework-aware retrieval**

Build tags from assigned framework definitions. For an assigned expert:

```python
first = self.retriever(..., framework_tags=tags)
if first.status == "ok":
    status = "framework_match"
elif first.status == "no_matches":
    second = self.retriever(..., framework_tags=None)
    result = second
    status = (
        "framework_no_match_fallback_ok"
        if second.status == "ok"
        else "framework_no_match_fallback_no_matches"
    )
else:
    result = first
    status = "framework_unavailable"
```

For no assigned framework use the existing call path and `base_retrieval`.

Do not include framework tag values or raw chunks in the external result summary.

- [ ] **Step 7: Add framework cards to blind prompts**

Render only assigned framework cards with id, short description, and diagnostic questions. Add doctrine text:

```text
Selected frameworks are analysis lenses. They do not establish facts about this case.
Use [FMW] for material claims that come mainly from a framework.
Use [F] only when supplied evidence independently supports the factual claim.
You may reject a framework that does not fit the current case.
```

- [ ] **Step 8: Run focused Council OS framework tests and verify GREEN**

```bash
python -m pytest tests/test_council_os_frameworks.py -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/council/council_os.py tests/test_council_os_frameworks.py tests/test_council_os.py
git commit -m "feat: integrate framework selection into Council OS"
```

---

### Task 5: Gate framework reasoning through Red Team, Evidence Judge, and Chairman

**Files:**
- Modify: `src/council/council_os.py`
- Modify: `tests/test_council_os_frameworks.py`

**Interfaces:**
- Red Team receives sanitized framework ids/assignments only.
- Evidence Judge returns `FrameworkAssessment`.
- Chairman receives selected frameworks minus `rejected_framework_ids` plus the Evidence Judge assessment.

- [ ] **Step 1: Write failing Red Team prompt test**

Assert Red Team receives selected framework ids and assignment metadata, and its system/user instructions require checks for:

- framework applicability;
- correlated reasoning caused by shared lenses;
- framework-as-evidence confusion.

Assert no raw book/RAG sentinel appears in the framework metadata section.

- [ ] **Step 2: Write failing Evidence Judge claim-reference test**

Use a memo with at least two claims and a fake Evidence Judge response:

```json
{
  "framework_assessment": {
    "misclassified_fact_claims": [
      {
        "claim_ref": "marketing:1",
        "framework_id": "positioning_category",
        "reason": "framework_rule_presented_as_fact"
      }
    ],
    "framework_overreach_labels": ["correlated_framework_reasoning"],
    "rejected_framework_ids": ["positioning_category"]
  }
}
```

Assert the claim reference is stable as `<expert_id>:<zero-based claim_index>` and validates without copying claim prose into the assessment field.

- [ ] **Step 3: Write failing Chairman rejection test**

If Evidence Judge rejects `positioning_category`, assert the Chairman framework payload does not include that framework as an active lens. The assessment may list it under rejected ids.

- [ ] **Step 4: Run focused tests and verify RED**

```bash
python -m pytest tests/test_council_os_frameworks.py -q
```

Expected: downstream framework fields/instructions missing.

- [ ] **Step 5: Implement sanitized downstream payloads**

Add helpers that serialize only:

```text
framework_id
assigned expert ids
score
reason labels
```

No description is required after the blind round unless it is short public registry copy; prefer ids and reason labels downstream.

Evidence Judge prompt includes a claim index map shaped like:

```json
{
  "marketing:0": {"label": "FMW"},
  "marketing:1": {"label": "F"}
}
```

Do not duplicate claim text into that map; the normal memo payload already contains it.

- [ ] **Step 6: Validate and sanitize `FrameworkAssessment`**

Reject unknown framework ids from `rejected_framework_ids`. Reject claim refs that do not correspond to an existing memo claim. Keep only known ids/refs and fixed short reason strings returned by the model.

- [ ] **Step 7: Filter Chairman framework context**

Chairman active framework ids are:

```python
selected_ids - set(evidence.framework_assessment.rejected_framework_ids)
```

Prompt doctrine must state that framework agreement is not independent confirmation and a framework cannot independently raise confidence.

- [ ] **Step 8: Build final `FrameworkSelectionSummary`**

Set:

- `policy_version`;
- selected ids;
- expert assignments;
- reason labels;
- retrieval diagnostics;
- Evidence Judge rejected ids;
- selector error labels.

Attach it to `CouncilOSResult`.

- [ ] **Step 9: Run focused tests and verify GREEN**

```bash
python -m pytest tests/test_council_os_frameworks.py -q
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add src/council/council_os.py tests/test_council_os_frameworks.py
git commit -m "feat: gate framework reasoning through review stages"
```

---

### Task 6: Persist sanitized framework diagnostics in Decision Memory

**Files:**
- Modify: `src/storage/decision_memory.py`
- Create: `tests/test_decision_memory_frameworks.py`
- Modify: existing Decision Memory tests only where constructors require additive fields.

**Interfaces:**
- Adds SQLite column: `decisions.framework_selection_json TEXT`.
- Capture source: `CouncilOSResult.framework_selection_summary` only.
- Readback key: `framework_selection_summary`.

- [ ] **Step 1: Write failing migration test**

Create a synthetic v2 database without `framework_selection_json`, initialize `DecisionMemoryStore`, then assert:

```python
columns = {row[1] for row in conn.execute("PRAGMA table_info(decisions)")}
assert "framework_selection_json" in columns
```

Also verify a pre-existing decision row still exists after initialization.

- [ ] **Step 2: Write failing capture/privacy test**

Build a `CouncilOSResult` containing a summary and place sentinels such as `PRIVATE_BOOK_SENTINEL`, `DRIVE_ID_SENTINEL`, and `POSTMORTEM_SENTINEL` in fields that must never be copied into the framework summary. Capture the decision and inspect SQLite text:

```python
assert "value_equation" in db_text
assert "PRIVATE_BOOK_SENTINEL" not in db_text_for_framework_column
assert "DRIVE_ID_SENTINEL" not in db_text_for_framework_column
```

- [ ] **Step 3: Run focused tests and verify RED**

```bash
python -m pytest tests/test_decision_memory_frameworks.py -q
```

Expected: missing column/readback support.

- [ ] **Step 4: Add additive migration and capture/readback**

Extend table creation with `framework_selection_json TEXT`, then after `PRAGMA table_info(decisions)`:

```python
if "framework_selection_json" not in columns:
    conn.execute("ALTER TABLE decisions ADD COLUMN framework_selection_json TEXT")
```

Capture only:

```python
framework_summary = (
    result.framework_selection_summary.model_dump(mode="json")
    if result.framework_selection_summary is not None
    else None
)
```

Store that JSON in the current decision row. Read it back as `framework_selection_summary`.

- [ ] **Step 5: Run Decision Memory framework and v2 regression tests**

```bash
python -m pytest tests/test_decision_memory_frameworks.py tests/test_decision_memory.py tests/test_decision_memory_api.py -q
```

Expected: all present tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/storage/decision_memory.py tests/test_decision_memory_frameworks.py tests/test_decision_memory.py tests/test_decision_memory_api.py
git commit -m "feat: persist framework diagnostics in Decision Memory"
```

---

### Task 7: Documentation, compatibility regression, and local acceptance gate

**Files:**
- Create: `docs/FRAMEWORK_SELECTOR_V1.md`
- Modify: `README.md`
- Test: existing Council OS, private retrieval, Decision Memory, and quality suites.

**Interfaces:**
- Documentation must match actual final pipeline and public/private boundaries.
- No `.github/workflows/*` changes.

- [ ] **Step 1: Write operational documentation**

Document:

```text
profile -> route -> framework selector -> framework-aware RAG -> blind memos
-> Decision Memory learning -> rebuttals -> Red Team -> Evidence Judge -> Chairman
```

Include the exact `5` minimum score, `3` global cap, `2` per-expert cap, fallback semantics, `[FMW]` rule, and statement that private source text is not stored in framework diagnostics.

- [ ] **Step 2: Update README**

Add Framework Selector to the Council OS sequence, explain that frameworks are lenses rather than facts, and link `docs/FRAMEWORK_SELECTOR_V1.md`. Keep Decision Memory v2 wording intact.

- [ ] **Step 3: Run focused framework tests**

```bash
python -m pytest \
  tests/test_framework_registry.py \
  tests/test_framework_selector.py \
  tests/test_framework_retrieval.py \
  tests/test_council_os_frameworks.py \
  tests/test_decision_memory_frameworks.py -q
```

Expected: all pass.

- [ ] **Step 4: Run Council OS and Decision Memory regressions**

Run all locally available relevant tests, including:

```bash
python -m pytest tests/test_council_os.py tests/test_council_os_deliberate.py tests/test_council_os_learning.py -q
python -m pytest tests/test_private_retrieval.py -q
```

Then run the repository-wide test suite when the complete checkout is available:

```bash
python -m pytest tests -q
```

Do not substitute GitHub Actions for a missing local test result.

- [ ] **Step 5: Run static/local quality checks**

```bash
python -m compileall -q src tests
```

If Ruff is installed locally:

```bash
python -m ruff check src tests
```

If it is not installed, report that explicitly and do not claim a Ruff pass.

Run the existing deterministic quality gate using the repository's current script/command and require score at or above its configured failure threshold.

- [ ] **Step 6: Privacy regression scan**

Search changed source/tests/docs for synthetic sentinels and forbidden private identifiers. Verify `framework_selection_json` never receives RAG text, Drive ids, notes, or postmortem content.

- [ ] **Step 7: Review the final diff**

Check:

- no `.github/workflows/*` change;
- no raw private text;
- no selector dependency on Decision Memory;
- no framework selection after blind round;
- no Evidence-Judge-rejected framework reaches Chairman active context;
- no retrieval retry after `unavailable`;
- existing retriever callers work without `framework_tags`.

- [ ] **Step 8: Commit docs/final cleanup**

```bash
git add README.md docs/FRAMEWORK_SELECTOR_V1.md
git commit -m "docs: document Framework Selector v1"
```

- [ ] **Step 9: Open PR and merge only from locally verified head**

Open a PR from `feat/framework-selector-v1` to `main`. Record the exact local verification evidence in the PR description and state that GitHub Actions were not used as an acceptance gate. Review the PR diff, fix blockers with a fresh RED→GREEN cycle, repeat the local gate after the last code change, and merge with `expected_head_sha` so the verified head cannot move underneath the merge.

- [ ] **Step 10: Verify post-merge `main` locally**

Confirm the merged `main` contains the expected production blob SHAs. Re-run the focused framework tests, relevant regressions, quality gate, and `compileall` against code matching the post-merge tree. Treat the phase as complete only after that fresh post-merge verification passes.
