# Council OS v1 Design

## Goal

Turn the existing AI Council repository into a decision-oriented business council that routes a bounded set of relevant experts, gives them independent first-pass analysis, forces adversarial review, judges evidence quality, and ends with a structured Chairman verdict.

Council OS v1 must reuse the repository's existing LLM provider abstraction and Pinecone retrieval layer. It is not a second product or a replacement for the existing Council, debate, or specialty modes.

## Scope

Council OS v1 implements the decision pipeline only:

```text
question
  -> business problem profile
  -> expert routing
  -> per-expert knowledge retrieval
  -> blind independent memos
  -> peer rebuttal
  -> Red Team
  -> Evidence Judge
  -> Chairman
  -> structured verdict
```

Decision Memory, calibration by historical outcomes, live web evidence collection, company-context connectors, and automatic framework-tag selection remain later phases. The v1 retrieval layer can already use `domains` and `experts` metadata written by the private-knowledge pipeline.

## Non-goals

- Do not rewrite `Council` or `DebateOrchestrator`.
- Do not remove or change current modes.
- Do not add a new external dependency.
- Do not store private source text, Drive IDs, notes, or book content in Git.
- Do not make Red Team or Evidence Judge ordinary domain experts in the initial vote.
- Do not let the Chairman see or express a preference before the adversarial phases are complete.
- Do not claim that a factual statement is verified merely because an LLM agrees with it.

## Architecture

### 1. Expert registry

A static registry defines business roles independently of the existing generic core agents. Each `ExpertDefinition` contains:

- `id`
- display name and role
- domains used for retrieval
- expert metadata aliases used for retrieval
- routing keywords
- a system prompt describing the role and decision discipline

Domain experts in v1:

- `strategy`
- `marketing`
- `sales`
- `offer_pricing`
- `product_customer`
- `growth`
- `operator`

Mandatory review roles:

- `red_team`
- `evidence_judge`
- `chairman`

The mandatory roles are never counted toward the 4–6 domain-expert routing cap.

### 2. Business router

`profile_problem(query)` performs deterministic rule-based classification. It emits a `ProblemProfile` with:

- `primary_domain`
- `secondary_domains`
- `decision_kind`
- `reversibility`: `reversible` or `hard_to_reverse`
- `risk_level`: `low`, `medium`, or `high`

`route_experts(profile, min_experts=4, max_experts=5)` scores domain experts from their keyword sets and profile domains. It always returns a bounded deterministic list. Strategy is used as a tie-break/fallback for decisions with broad consequences, but the router must not select every role by default.

The first version deliberately avoids an LLM router. Deterministic routing is cheaper, testable, and cannot silently change because a model changed.

### 3. Per-expert retrieval

Before the blind memo round, each selected domain expert receives its own retrieval result through the existing `query_knowledge_result` API.

The call uses:

- the original user question;
- that expert's `domains`;
- that expert's retrieval expert aliases;
- `PINECONE_PRIVATE_NAMESPACE` through the existing runtime configuration;
- provenance-preserving context formatting.

Private chunks may enter internal LLM prompts, because that is the purpose of the private RAG system. They must not be written to application logs or added to public source-display payloads.

Retrieval status is tracked per expert. `unavailable` is distinct from `no_matches`. A retrieval outage does not stop the council, but the Evidence Judge and Chairman are explicitly told that private evidence was unavailable.

### 4. Blind independent memos

Round 1 is structurally blind. Every selected domain expert is called independently and in parallel. Its prompt contains:

- original question;
- problem profile;
- role instructions;
- only that expert's retrieved context and provenance;
- a strict JSON memo schema.

It does not contain another expert's memo, consensus, routing score, Chairman preference, Red Team analysis, or peer summary.

Each `ExpertMemo` contains:

- `expert_id`
- `vote`: `GO`, `NO-GO`, `TEST`, or `DEFER`
- `recommendation`
- `confidence` in `[0, 1]`
- `claims`, each labeled `F`, `A`, `I`, `FMW`, or `O`
- `assumptions`
- `risks`
- `what_changes_my_mind`
- `knowledge_status`

The explicit `vote` is the deterministic signal used to measure early directional consensus. Free-form recommendation text is never used to calculate the >80% threshold.

Claim labels mean:

- `F`: fact asserted as supported by supplied evidence/context;
- `A`: assumption;
- `I`: inference;
- `FMW`: framework-derived claim;
- `O`: expert judgment/opinion.

An `F` label is not independently verified truth. Evidence Judge decides whether the supplied provenance actually supports it.

### 5. Peer rebuttal

After all blind memos exist, each domain expert gets a compact view of the other domain memos and produces a `Rebuttal` with:

- strongest agreement;
- strongest disagreement;
- assumption to test;
- `revised_vote`: `GO`, `NO-GO`, `TEST`, or `DEFER`;
- revised confidence.

The rebuttal phase is the first point where domain experts can see one another. Early-consensus detection uses the blind `vote` values, not revised votes, so the contrarian trigger cannot be suppressed by post-hoc convergence.

### 6. Red Team

Red Team receives all blind memos and rebuttals. Its mandate is adversarial, not merely negative. It must look for:

- hidden incentives;
- base-rate neglect;
- second-order effects;
- irreversible downside;
- correlated assumptions;
- premature consensus;
- contradictions;
- ways the plan fails even if the central thesis is broadly correct.

It emits a structured `RedTeamReport` containing failure modes, challenged assumptions, double-crux questions, and a `premature_consensus` flag.

If more than 80% of successful blind domain memos have the same `vote`, the Red Team prompt explicitly requires a contrarian case before synthesis. With four domain experts this means unanimity; with five domain experts it means all five because 4/5 equals 80%, not more than 80%.

### 7. Evidence Judge

Evidence Judge runs after Red Team. It sees:

- expert memos;
- rebuttals;
- Red Team report;
- source provenance and retrieval statuses.

It does not decide the business recommendation. It classifies the epistemic quality of the debate:

- supported claims;
- unsupported or weakly supported claims;
- contradictions;
- evidence gaps;
- private-knowledge availability;
- framework-vs-fact confusion.

A claim is `supported` only relative to evidence provided to the council. The judge must not imply universal verification.

### 8. Chairman

Chairman is called last and only once the previous phases are complete. It receives the full structured record and must return strict JSON matching `CouncilVerdict`:

```json
{
  "verdict": "GO | NO-GO | TEST | DEFER",
  "recommendation": "...",
  "confidence": 0.0,
  "consensus": "...",
  "key_disagreement": "...",
  "minority_report": "...",
  "assumptions": ["..."],
  "evidence_gaps": ["..."],
  "what_would_change_decision": ["..."],
  "next_experiment": {
    "action": "...",
    "metric": "...",
    "threshold": "...",
    "timeline": "...",
    "kill_criteria": "..."
  }
}
```

`TEST` is preferred when the decision is reversible and a discriminating experiment can resolve the main uncertainty. `DEFER` is appropriate when evidence is unavailable or a critical unresolved dependency prevents a responsible decision.

If Chairman output cannot be parsed after safe JSON extraction, Council OS returns a deterministic fallback verdict of `DEFER` with an evidence gap indicating malformed Chairman output. The orchestration does not silently substitute free-form prose for the contract.

## Model boundaries and dependencies

`CouncilOS` accepts a normal repository `LLMProvider` and an injectable retrieval function. Tests use fakes; production uses `query_knowledge_result`.

The new orchestration layer calls `LLMProvider.generate`, not the existing `BaseAgent` subclasses. This keeps the existing generic agents backward compatible while allowing business roles to have explicit prompts and machine-checkable schemas.

No model is assumed to be genuinely independent when the same provider/model is used for all roles. Independence in v1 means blind prompt isolation and separate calls. The architecture permits different providers later without changing the decision schema.

## Integration with existing modes

Council OS is exposed through the existing Council Mode surface under mode id `council_os`.

A thin adapter in `src/council/modes.py`:

- emits `mode_start`;
- emits phase/agent progress events;
- calls `CouncilOS`;
- emits one structured `council_os_result` event containing route, memos summaries, Red Team report, Evidence Judge assessment, and Chairman verdict;
- emits `complete`.

Existing mode ids and API contracts stay valid. No second HTTP API is required for v1.

## Error handling

- One domain expert failing does not necessarily abort the council. The failure becomes a missing memo/evidence gap; execution continues if at least two domain memos are available.
- Fewer than two successful domain memos causes a deterministic `DEFER` result without pretending a council deliberation occurred.
- Retrieval `unavailable` is preserved as status metadata and disclosed to Evidence Judge/Chairman.
- JSON parsing never uses `eval`. It strips optional markdown fences, extracts the outer JSON object, validates with Pydantic, and uses typed fallbacks.
- Red Team or Evidence Judge parse failure is represented explicitly in their typed fallback object and passed to Chairman as an evidence gap.
- Raw private retrieved passages are never included in SSE result payloads.

## Testing strategy

All new tests use synthetic text and fake LLM/retrieval objects.

Required tests:

1. Routing selects relevant experts and respects 4–5 domain-expert bounds.
2. Pricing questions include `offer_pricing`; growth questions include `growth`; operational questions include `operator`.
3. Hard-to-reverse language increases risk/reversibility classification deterministically.
4. Per-expert retrieval is called with role-specific domain/expert filters.
5. Blind memo prompts do not contain peer memo content.
6. Rebuttal prompts do contain peer memo summaries only after blind round completes.
7. Red Team runs after all blind/rebuttal calls.
8. >80% matching blind `vote` values marks/requests a contrarian challenge.
9. Evidence Judge sees provenance/status but result payload does not leak raw private chunks.
10. Chairman is last and validates the strict verdict schema.
11. Malformed Chairman JSON returns typed `DEFER`.
12. Knowledge `unavailable` remains distinct from `no_matches` through the verdict pipeline.
13. Existing `/api/council/mode/stream` recognizes `council_os` while unknown modes still return 404.
14. Existing full repository tests, Ruff checks, private corpus guard, and quality gate remain green.

## Acceptance criteria

Council OS v1 is complete when a synthetic end-to-end test proves the exact phase ordering:

```text
route
-> retrieve per expert
-> blind memos
-> rebuttals
-> red_team
-> evidence_judge
-> chairman
```

and the final typed result contains a valid `GO`, `NO-GO`, `TEST`, or `DEFER` verdict without exposing raw private retrieved text in the external result payload.
