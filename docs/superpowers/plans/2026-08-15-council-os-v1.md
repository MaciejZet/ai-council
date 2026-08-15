# Council OS v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a decision-oriented Council OS mode that routes 4–5 relevant business experts, runs blind memos, rebuttals, Red Team, Evidence Judge, and a typed Chairman verdict while reusing the existing LLM provider and private RAG infrastructure.

**Architecture:** New focused modules define typed decision contracts, a deterministic business expert registry/router, and a `CouncilOS` orchestrator. The orchestrator calls the existing `LLMProvider.generate` and `query_knowledge_result`; `src/council/modes.py` gets only a thin `council_os` SSE adapter so existing modes and APIs remain backward compatible.

**Tech Stack:** Python 3.12+, Pydantic 2, asyncio, existing `src.llm_providers.LLMProvider`, existing Pinecone retriever, pytest, Ruff, GitHub Actions.

## Global Constraints

- Do not rewrite `Council` or `DebateOrchestrator`.
- Do not remove or change behavior of existing council modes.
- No new external dependency.
- Public Git contains no private source text, Drive IDs, book content, summaries, or retrieved passages.
- New tests use synthetic data only.
- Domain routing returns 4–5 experts; Red Team, Evidence Judge, and Chairman are mandatory review roles outside that cap.
- Round 1 is blind: no domain expert may see peer memo content before all blind memos finish.
- Early consensus is computed only from typed blind `vote` values and triggers only when the leading vote share is strictly greater than 0.80.
- Retrieval `unavailable` stays distinct from `no_matches` throughout the pipeline.
- Evidence Judge may say a claim is supported by supplied evidence; it must not claim universal factual verification.
- Chairman runs last and returns `GO`, `NO-GO`, `TEST`, or `DEFER` through a Pydantic-validated schema.
- Malformed structured model output never uses `eval`; typed fallbacks are explicit.
- External SSE result payloads never include raw retrieved chunk text.

---

### Task 1: Typed Council OS contracts and safe structured parsing

**Files:**
- Create: `src/council/council_os_models.py`
- Test: `tests/test_council_os_models.py`

**Interfaces:**
- Produces: `DecisionVote`, `ClaimLabel`, `ProblemProfile`, `Claim`, `ExpertMemo`, `Rebuttal`, `RedTeamReport`, `EvidenceAssessment`, `NextExperiment`, `CouncilVerdict`, `CouncilOSResult`, `extract_json_object(text: str) -> dict`, and typed fallback helpers used by later tasks.
- Consumes: Pydantic only.

- [ ] **Step 1: Write failing model/parser tests**

```python
import pytest

from src.council.council_os_models import (
    CouncilVerdict,
    DecisionVote,
    extract_json_object,
)


def test_extract_json_object_accepts_fenced_json():
    payload = extract_json_object('```json\n{"verdict":"TEST"}\n```')
    assert payload == {"verdict": "TEST"}


def test_council_verdict_rejects_unknown_vote():
    with pytest.raises(ValueError):
        CouncilVerdict(
            verdict="MAYBE",
            recommendation="x",
            confidence=0.5,
            consensus="",
            key_disagreement="",
            minority_report="",
            assumptions=[],
            evidence_gaps=[],
            what_would_change_decision=[],
            next_experiment=None,
        )


def test_decision_vote_values_are_stable():
    assert set(DecisionVote) == {
        DecisionVote.GO,
        DecisionVote.NO_GO,
        DecisionVote.TEST,
        DecisionVote.DEFER,
    }
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_council_os_models.py -v --tb=short --no-cov
```

Expected: collection/import failure because `council_os_models.py` does not exist.

- [ ] **Step 3: Implement typed models and parser**

Required contract shapes:

```python
class DecisionVote(str, Enum):
    GO = "GO"
    NO_GO = "NO-GO"
    TEST = "TEST"
    DEFER = "DEFER"


class ClaimLabel(str, Enum):
    FACT = "F"
    ASSUMPTION = "A"
    INFERENCE = "I"
    FRAMEWORK = "FMW"
    OPINION = "O"


class Claim(BaseModel):
    label: ClaimLabel
    text: str
    source_ids: list[str] = Field(default_factory=list)


class ExpertMemo(BaseModel):
    expert_id: str
    vote: DecisionVote
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    claims: list[Claim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    what_changes_my_mind: list[str] = Field(default_factory=list)
    knowledge_status: str = "disabled"


class Rebuttal(BaseModel):
    expert_id: str
    strongest_agreement: str
    strongest_disagreement: str
    assumption_to_test: str
    revised_vote: DecisionVote
    revised_confidence: float = Field(ge=0.0, le=1.0)


class RedTeamReport(BaseModel):
    failure_modes: list[str] = Field(default_factory=list)
    challenged_assumptions: list[str] = Field(default_factory=list)
    double_crux_questions: list[str] = Field(default_factory=list)
    premature_consensus: bool = False
    contrarian_case: str = ""
    parse_error: bool = False


class EvidenceAssessment(BaseModel):
    supported_claims: list[str] = Field(default_factory=list)
    weak_or_unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    knowledge_status_by_expert: dict[str, str] = Field(default_factory=dict)
    framework_fact_confusions: list[str] = Field(default_factory=list)
    parse_error: bool = False
```

Also define `ProblemProfile`, `NextExperiment`, `CouncilVerdict`, and `CouncilOSResult`. `CouncilOSResult` must contain structured deliberation outputs but no private context/chunk field.

`extract_json_object` strips an optional markdown fence, locates the first `{` and last `}`, calls `json.loads`, and raises `ValueError` on malformed/non-object JSON.

- [ ] **Step 4: Add fallback tests**

```python
from src.council.council_os_models import defer_verdict


def test_defer_verdict_is_explicit_about_parse_failure():
    verdict = defer_verdict("chairman_parse_error")
    assert verdict.verdict.value == "DEFER"
    assert "chairman_parse_error" in verdict.evidence_gaps
```

- [ ] **Step 5: Run focused tests GREEN and Ruff**

```bash
uv run pytest tests/test_council_os_models.py -v --tb=short --no-cov
uv run ruff check src/council/council_os_models.py tests/test_council_os_models.py
```

Expected: all pass.

---

### Task 2: Business expert registry and deterministic router

**Files:**
- Create: `src/council/expert_registry.py`
- Create: `src/council/business_routing.py`
- Test: `tests/test_business_routing.py`

**Interfaces:**
- Consumes: `ProblemProfile` from Task 1.
- Produces: `ExpertDefinition`, `EXPERT_REGISTRY`, `DOMAIN_EXPERT_IDS`, `profile_problem(query: str) -> ProblemProfile`, `route_experts(profile: ProblemProfile, min_experts: int = 4, max_experts: int = 5) -> list[ExpertDefinition]`, `early_consensus_vote(memos: list[ExpertMemo]) -> tuple[DecisionVote | None, float]`.

- [ ] **Step 1: Write routing tests**

```python
from src.council.business_routing import early_consensus_vote, profile_problem, route_experts
from src.council.council_os_models import DecisionVote, ExpertMemo


def routed_ids(query: str) -> list[str]:
    return [expert.id for expert in route_experts(profile_problem(query))]


def test_pricing_routes_offer_expert_and_stays_bounded():
    ids = routed_ids("Czy podnieść cenę planu B2B i zmienić pakiety?")
    assert "offer_pricing" in ids
    assert 4 <= len(ids) <= 5


def test_growth_routes_growth_expert():
    assert "growth" in routed_ids("Jak zwiększyć acquisition i referral growth?")


def test_operations_routes_operator():
    assert "operator" in routed_ids("Jak wdrożyć ten proces operacyjny i właścicieli KPI?")


def test_irreversible_decision_is_high_risk():
    profile = profile_problem("Czy przejąć spółkę i podpisać wieloletnie zobowiązanie?")
    assert profile.reversibility == "hard_to_reverse"
    assert profile.risk_level == "high"
```

- [ ] **Step 2: Run tests RED**

```bash
uv run pytest tests/test_business_routing.py -v --tb=short --no-cov
```

Expected: import failure.

- [ ] **Step 3: Implement expert registry**

Each domain expert definition must include role-specific `domains`, `retrieval_experts`, keyword tuples, and a prompt. Registry order is deterministic:

```python
DOMAIN_EXPERT_IDS = (
    "strategy",
    "marketing",
    "sales",
    "offer_pricing",
    "product_customer",
    "growth",
    "operator",
)
```

Mandatory role ids are `red_team`, `evidence_judge`, and `chairman`.

Prompts must tell experts to distinguish `[F]`, `[A]`, `[I]`, `[FMW]`, `[O]`, state what would change their mind, and avoid inventing evidence outside supplied context.

- [ ] **Step 4: Implement deterministic profile and scoring router**

Use compiled regex/keyword sets, not an LLM. Route score is based on keyword/domain matches with deterministic fallback order. Ensure `min_experts <= result <= max_experts`; default to five only when enough roles score meaningfully, otherwise fill to four.

Implement hard-to-reverse keywords such as acquisition/M&A, long-term commitment, major rebrand, irreversible migration, legal commitment, and large capital allocation. High-risk classification follows hard-to-reverse decisions; medium is default for business decisions; low is reserved for explicit small reversible tests.

- [ ] **Step 5: Add exact >80% early-consensus test**

```python
def memo(expert_id: str, vote: DecisionVote) -> ExpertMemo:
    return ExpertMemo(
        expert_id=expert_id,
        vote=vote,
        recommendation="synthetic",
        confidence=0.7,
        knowledge_status="ok",
    )


def test_early_consensus_requires_strictly_more_than_eighty_percent():
    four_of_five = [memo(str(i), DecisionVote.GO) for i in range(4)] + [
        memo("x", DecisionVote.TEST)
    ]
    vote, share = early_consensus_vote(four_of_five)
    assert share == 0.8
    assert vote is None

    unanimous = [memo(str(i), DecisionVote.GO) for i in range(5)]
    vote, share = early_consensus_vote(unanimous)
    assert vote == DecisionVote.GO
    assert share == 1.0
```

- [ ] **Step 6: Run tests GREEN and Ruff**

```bash
uv run pytest tests/test_business_routing.py -v --tb=short --no-cov
uv run ruff check src/council/expert_registry.py src/council/business_routing.py tests/test_business_routing.py
```

Expected: all pass.

---

### Task 3: Per-expert retrieval and blind memo round

**Files:**
- Create: `src/council/council_os.py`
- Test: `tests/test_council_os.py`

**Interfaces:**
- Consumes: `LLMProvider`, `query_knowledge_result`, `format_context_for_agent`, Task 1 models, Task 2 registry/router.
- Produces initially: `CouncilOS.__init__(llm, *, retriever=query_knowledge_result, knowledge_namespace=None, knowledge_top_k=5)` and internal async `_run_blind_memos`.

- [ ] **Step 1: Write fake provider/retriever fixtures**

```python
from src.llm_providers import LLMResponse
from src.knowledge.private_models import KnowledgeRetrievalResult


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None):
        self.calls.append((system_prompt, user_prompt))
        expert_id = system_prompt.split("[EXPERT_ID:", 1)[1].split("]", 1)[0]
        return LLMResponse(
            content=(
                '{"expert_id":"%s","vote":"TEST","recommendation":"synthetic",'
                '"confidence":0.7,"claims":[],"assumptions":[],"risks":[],'
                '"what_changes_my_mind":[]}' % expert_id
            ),
            model="fake",
        )


def fake_retriever(query, **kwargs):
    return KnowledgeRetrievalResult(
        status="ok",
        chunks=[{
            "text": "PRIVATE_SYNTHETIC_CHUNK",
            "title": "Synthetic Source",
            "doc_id": "synthetic-doc",
            "source_type": "synthesis",
            "chunk_index": 0,
            "score": 0.9,
        }],
    )
```

- [ ] **Step 2: Write failing per-expert retrieval test**

Assert that each retriever invocation receives the routed expert's domain/expert filters and the configured namespace.

- [ ] **Step 3: Write failing blind isolation test**

Run the blind stage and assert:

```python
blind_prompts = [user for system, user in llm.calls if "[STAGE:BLIND]" in system]
assert len(blind_prompts) >= 4
assert all("PEER_MEMO_SENTINEL" not in prompt for prompt in blind_prompts)
```

Also assert private synthetic context is present internally in the matching expert prompt, proving RAG is actually used.

- [ ] **Step 4: Run tests RED**

```bash
uv run pytest tests/test_council_os.py -v --tb=short --no-cov
```

Expected: `CouncilOS` missing/incomplete.

- [ ] **Step 5: Implement retrieval wrapper and blind memo call**

For each routed expert:

```python
result = self.retriever(
    query,
    top_k=self.knowledge_top_k,
    domains=expert.domains,
    experts=expert.retrieval_experts,
    namespace=self.knowledge_namespace,
)
```

Format internal context with provenance. Build system prompts containing explicit markers:

```text
[STAGE:BLIND]
[EXPERT_ID:strategy]
```

Use `asyncio.gather(..., return_exceptions=True)` so one expert failure becomes a typed omission/evidence gap rather than an immediate abort.

After parsing, overwrite/validate `memo.expert_id` from the routed role rather than trusting a model-supplied different id. Set `memo.knowledge_status` from retrieval status.

- [ ] **Step 6: Add degraded retrieval test**

Return `KnowledgeRetrievalResult(status="unavailable", error_code="pinecone_unavailable")` for one expert and assert the resulting memo retains `knowledge_status == "unavailable"` even if the LLM memo succeeds.

- [ ] **Step 7: Run focused tests GREEN and Ruff**

```bash
uv run pytest tests/test_council_os.py -v --tb=short --no-cov
uv run ruff check src/council/council_os.py tests/test_council_os.py
```

Expected: blind-stage tests pass.

---

### Task 4: Rebuttal, Red Team, and Evidence Judge phases

**Files:**
- Modify: `src/council/council_os.py`
- Test: `tests/test_council_os.py`

**Interfaces:**
- Consumes: successful blind `ExpertMemo` objects and internal provenance summaries.
- Produces: `Rebuttal` list, `RedTeamReport`, `EvidenceAssessment`.

- [ ] **Step 1: Extend FakeLLM with stage-specific structured responses**

Detect `[STAGE:REBUTTAL]`, `[STAGE:RED_TEAM]`, and `[STAGE:EVIDENCE_JUDGE]` markers and return valid synthetic JSON for each model.

- [ ] **Step 2: Write failing phase-order/isolation test**

Track `FakeLLM.stage_calls`. Assert no rebuttal call begins until all blind calls are recorded, and Red Team index is greater than every rebuttal index.

For rebuttal prompts, assert a sentinel from another memo is present, proving peer visibility begins only after the blind phase.

- [ ] **Step 3: Implement `_run_rebuttals`**

Each successful domain expert receives compact peer memo JSON excluding raw retrieval context. Parse to `Rebuttal`; on failure create no rebuttal for that expert and record an orchestration evidence gap.

- [ ] **Step 4: Write and implement strict consensus/contrarian test**

Use five blind memos with the same `vote`. Assert Red Team prompt contains:

```text
PREMATURE_CONSENSUS=true
REQUIRED: construct the strongest credible contrarian case
```

Use four-of-five matching votes and assert the flag is false.

- [ ] **Step 5: Implement `_run_red_team`**

Prompt includes blind memos, rebuttals, `ProblemProfile`, and early-consensus signal. It does not include private raw chunks. Parse into `RedTeamReport`; malformed output produces `RedTeamReport(parse_error=True, ...)` with a failure-mode note.

- [ ] **Step 6: Write Evidence Judge provenance test**

Assert Evidence Judge prompt contains synthetic provenance identifiers/title/status, plus memos and Red Team findings, while the eventual public result model contains no `PRIVATE_SYNTHETIC_CHUNK`.

- [ ] **Step 7: Implement `_run_evidence_judge`**

Provide compact provenance only:

```json
{
  "expert_id": "strategy",
  "knowledge_status": "ok",
  "sources": [
    {"doc_id": "synthetic-doc", "title": "Synthetic Source", "source_type": "synthesis", "score": 0.9}
  ]
}
```

Do not include the chunk `text` field in the Evidence Judge source inventory or external result. Parse into `EvidenceAssessment`; malformed output sets `parse_error=True` and adds an evidence gap.

- [ ] **Step 8: Run tests GREEN and Ruff**

```bash
uv run pytest tests/test_council_os.py -v --tb=short --no-cov
uv run ruff check src/council/council_os.py tests/test_council_os.py
```

Expected: all phase tests pass.

---

### Task 5: Chairman verdict and complete CouncilOS result

**Files:**
- Modify: `src/council/council_os.py`
- Test: `tests/test_council_os.py`

**Interfaces:**
- Produces: `async CouncilOS.deliberate(query: str) -> CouncilOSResult`.

- [ ] **Step 1: Write failing Chairman-last test**

Extend fake provider to answer `[STAGE:CHAIRMAN]`. Assert the last LLM stage call is exactly `CHAIRMAN` and the returned verdict is Pydantic typed.

- [ ] **Step 2: Implement Chairman prompt and parser**

Chairman prompt contains:

- query and problem profile;
- route ids;
- successful blind memos;
- rebuttals;
- Red Team report;
- Evidence Assessment;
- orchestration evidence gaps;
- explicit instruction that `TEST` is preferred for reversible discriminating experiments and `DEFER` for critical evidence outages/dependencies.

It must not contain raw retrieved chunks.

- [ ] **Step 3: Write malformed Chairman fallback test**

Return `not-json` from the fake Chairman and assert:

```python
assert result.verdict.verdict == DecisionVote.DEFER
assert "chairman_parse_error" in result.verdict.evidence_gaps
```

- [ ] **Step 4: Implement fewer-than-two-memos fallback**

If fewer than two blind expert calls parse successfully, skip rebuttal/Red Team/Evidence Judge/Chairman and return a `DEFER` verdict with `insufficient_domain_memos` evidence gap. Tests must assert no Chairman call occurred.

- [ ] **Step 5: Implement sanitized result assembly**

`CouncilOSResult` contains:

- `profile`
- `routed_experts` ids
- `memos`
- `rebuttals`
- `red_team`
- `evidence`
- `verdict`
- `knowledge_status_by_expert`
- `errors`

It contains no retrieval chunks/context fields.

- [ ] **Step 6: Add synthetic end-to-end ordering test**

Assert call-stage order grouped as:

```text
BLIND* -> REBUTTAL* -> RED_TEAM -> EVIDENCE_JUDGE -> CHAIRMAN
```

and `"PRIVATE_SYNTHETIC_CHUNK" not in result.model_dump_json()`.

- [ ] **Step 7: Run focused tests GREEN**

```bash
uv run pytest tests/test_council_os_models.py tests/test_business_routing.py tests/test_council_os.py -v --tb=short --no-cov
uv run ruff check src/council/council_os_models.py src/council/expert_registry.py src/council/business_routing.py src/council/council_os.py tests/test_council_os_models.py tests/test_business_routing.py tests/test_council_os.py
```

Expected: all pass.

---

### Task 6: Integrate Council OS into the existing Council Mode API

**Files:**
- Modify: `src/council/modes.py`
- Modify: `tests/test_council_mode_api.py`
- Test: `tests/test_council_os_mode.py`

**Interfaces:**
- Consumes: `CouncilOS` and existing `CouncilMode._sse` contract.
- Produces: mode id `council_os` through existing `COUNCIL_MODES` / `/api/council/mode/stream` surface.

- [ ] **Step 1: Write failing mode registry/API test**

```python
from src.council.modes import get_mode


def test_council_os_mode_is_registered():
    mode = get_mode("council_os")
    assert mode is not None
    assert mode.name == "council_os"
```

Extend API regression test so `mode=council_os` is not rejected as unknown while the existing unknown-mode 404 test remains unchanged. Mock the actual run to avoid production LLM calls.

- [ ] **Step 2: Run mode tests RED**

```bash
uv run pytest tests/test_council_os_mode.py tests/test_council_mode_api.py -v --tb=short --no-cov
```

Expected: `council_os` is absent from registry.

- [ ] **Step 3: Implement thin `CouncilOSMode` adapter**

Add a class in `src/council/modes.py` with:

```python
class CouncilOSMode(CouncilMode):
    name = "council_os"
    emoji = "🏛️"
    description = "Decision Council: blind experts, Red Team, Evidence Judge, Chairman"
```

`run_stream` uses the supplied `llm` or repository default provider, emits `mode_start`, calls `CouncilOS.deliberate`, emits sanitized `council_os_result` using `result.model_dump(mode="json")`, and emits `complete`.

Add `"council_os": CouncilOSMode` to `COUNCIL_MODES`.

- [ ] **Step 4: Test SSE payload does not contain raw private context**

Use a fake `CouncilOS` or monkeypatch so the event contains a synthetic typed result. Assert the serialized SSE does not expose any private context/chunk field.

- [ ] **Step 5: Run focused integration tests GREEN and Ruff**

```bash
uv run pytest tests/test_council_os_mode.py tests/test_council_mode_api.py -v --tb=short --no-cov
uv run ruff check src/council/modes.py tests/test_council_os_mode.py tests/test_council_mode_api.py
```

Expected: all pass.

---

### Task 7: Documentation, full regression verification, and PR review

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-15-council-os-v1-design.md` only if implementation revealed a contract correction.
- Modify: `.github/workflows/ci.yml` only if a focused Council OS step is needed for fast fail; do not weaken existing gates.

**Interfaces:** None; this task verifies the complete feature.

- [ ] **Step 1: Document Council OS mode**

README must explain:

- mode id `council_os`;
- 4–5 routed domain experts plus Red Team, Evidence Judge, Chairman;
- blind first pass;
- per-expert private RAG;
- `GO/NO-GO/TEST/DEFER` verdict contract;
- no claim of real multi-model independence when a single provider/model is configured.

- [ ] **Step 2: Run focused Council OS suite**

```bash
uv run pytest \
  tests/test_council_os_models.py \
  tests/test_business_routing.py \
  tests/test_council_os.py \
  tests/test_council_os_mode.py \
  tests/test_council_mode_api.py \
  -v --tb=short --no-cov
```

Expected: 0 failures.

- [ ] **Step 3: Run full lint and privacy guard**

```bash
uv run ruff check tests
uv run ruff check src/council/council_os_models.py src/council/expert_registry.py src/council/business_routing.py src/council/council_os.py src/council/modes.py
uv run python scripts/check_private_corpus.py --tracked-only
```

Expected: all checks pass, corpus guard exit 0.

- [ ] **Step 4: Run full test suite and deterministic quality gate**

```bash
uv run pytest tests/ -v --tb=short --no-cov
uv run python tests/quality_gate.py
```

Expected: all tests pass and quality gate satisfies the existing threshold.

- [ ] **Step 5: Review the PR diff for privacy and architecture**

Explicitly verify:

- no raw private source passage or real Drive id is present;
- no new generic Council behavior changed unintentionally;
- no existing mode was removed;
- blind prompts exclude peer memos;
- Chairman is last;
- external result has no raw retrieval contexts;
- route is bounded;
- fallback verdicts are explicit.

- [ ] **Step 6: Merge only after fresh head verification**

Prefer squash merge after final GitHub Actions success so the implementation branch's TDD/debug history does not clutter `main`.
