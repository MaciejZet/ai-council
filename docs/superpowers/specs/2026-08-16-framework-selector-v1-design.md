# Framework Selector / Decision Doctrine v1

## Goal

Framework Selector v1 gives Council OS a deterministic way to choose a small set of decision lenses before expert analysis starts. The selected lenses shape questions and retrieval, but they never count as evidence about the current case.

The feature must preserve the existing Council OS guarantees:

- blind experts do not see peer opinions, Decision Memory history, Red Team output, or Chairman preferences;
- framework-derived claims remain distinct from supplied-evidence facts;
- private book text, private summaries, Drive ids, and retrieved chunks do not enter the public repository or Decision Memory diagnostics;
- a missing or poorly tagged framework source cannot prevent an expert from receiving ordinary domain knowledge;
- Decision Memory v2 keeps its current post-blind position in the pipeline.

Target flow:

```text
question
  -> problem profile
  -> expert routing
  -> deterministic framework selection
  -> per-expert framework-aware private RAG
  -> blind independent memos
  -> Decision Memory learning context
  -> rebuttals
  -> Red Team
  -> Evidence Judge
  -> Chairman
  -> verdict + sanitized framework diagnostics
```

## Scope

V1 adds:

- a versioned framework registry with short original descriptions and diagnostic questions;
- deterministic framework scoring from the current question, `ProblemProfile`, and routed expert ids;
- at most 3 selected frameworks globally and at most 2 framework lenses per expert;
- optional `framework_tags` filtering in the existing knowledge retriever;
- a two-step retrieval policy: framework-aware retrieval first, then normal expert/domain retrieval when the framework-filtered query returns no matches;
- blind-prompt framework cards that contain only public registry metadata and diagnostic questions;
- Evidence Judge checks for framework-vs-fact confusion;
- a sanitized `framework_selection_summary` in `CouncilOSResult` and Decision Memory capture;
- deterministic tests for selection, retrieval fallback, privacy, prompt ordering, and backward compatibility.

V1 does not add an LLM framework router, automatic framework generation, framework embeddings, cross-user framework learning, or automatic mutation of the registry based on Decision Memory results.

## Design principles

### Frameworks are analysis tools

A framework can suggest what to inspect. It cannot establish a fact about a company, market, customer, or outcome.

Every material claim that depends mainly on a selected framework must remain labeled `[FMW]`. A claim may be labeled `[F]` only when the supplied evidence supports the factual statement independently of the framework.

### Selection is deterministic

For a fixed query, profile, routed-expert list, registry version, and configuration, framework selection returns the same result.

No LLM call is allowed inside the selector in v1.

### Selection is sparse

The selector prefers an empty result over weak forced matches. A normal decision should usually receive 1-3 lenses, not every applicable framework.

### Retrieval failure degrades safely

A framework tag is a retrieval preference. It is not a hard dependency. If framework-specific retrieval returns `no_matches`, Council OS retries with the existing domain/expert filters.

Infrastructure failure remains distinct from `no_matches`. An `unavailable` framework-specific retrieval does not trigger a second backend call in v1.

## Architecture

### `framework_registry.py`

Create `src/council/framework_registry.py`.

The module owns immutable framework definitions and registry versioning.

Use this contract:

```python
@dataclass(frozen=True)
class FrameworkDefinition:
    id: str
    name: str
    profile_domains: tuple[str, ...]
    decision_kinds: tuple[str, ...]
    expert_ids: tuple[str, ...]
    trigger_keywords: tuple[str, ...]
    framework_tags: tuple[str, ...]
    diagnostic_questions: tuple[str, ...]
    description: str
```

`profile_domains` uses the existing `ProblemProfile.primary_domain` and `secondary_domains` vocabulary: `strategy`, `marketing`, `sales`, `offer_pricing`, `product_customer`, `growth`, `operator`.

The description and diagnostic questions must be short, original wording. They must not quote or reconstruct book passages.

Registry constant:

```text
FRAMEWORK_POLICY_VERSION = "framework-selector-v1"
```

Registry order is part of the deterministic tie-break contract.

## Initial registry

V1 starts with 8 frameworks. The ids, matching fields, tags, and questions below are normative for v1.

### `strategic_choice`

- profile domains: `strategy`, `operator`
- decision kinds: `strategy`, `operations`
- expert ids: `strategy`, `operator`
- trigger keywords: `strategy`, `strategic`, `competition`, `competitive`, `focus`, `resource allocation`, `expansion`, `acquisition`, `merger`, `strategia`, `strategiczny`, `konkurencja`, `przewaga`, `alokacja zasobów`, `ekspansja`, `przejęcie`, `fuzja`
- framework tags: `strategic_choice`, `good_strategy`, `resource_allocation`
- description: isolate the decisive challenge, the actual choice, the trade-off, and the actions that must reinforce one another
- diagnostic questions:
  - What is the decisive constraint or challenge?
  - Which real alternative is being rejected?
  - What actions must reinforce one another for the choice to work?

### `competitive_advantage`

- profile domains: `strategy`, `product_customer`
- decision kinds: `strategy`, `product_customer`
- expert ids: `strategy`, `product_customer`
- trigger keywords: `competitive advantage`, `advantage`, `moat`, `differentiate`, `differentiation`, `unique`, `proprietary`, `substitute`, `przewaga`, `przewaga konkurencyjna`, `wyróżnik`, `unikalny`, `substytut`
- framework tags: `competitive_advantage`, `moat`, `zero_to_one`
- description: test whether the proposal creates a durable reason to win after customers and competitors react
- diagnostic questions:
  - What is meaningfully different from the closest substitute?
  - Why would that advantage persist after competitors respond?
  - Which assumption would make the claimed advantage disappear?

### `positioning_category`

- profile domains: `marketing`, `sales`
- decision kinds: `marketing`, `sales`
- expert ids: `marketing`, `sales`
- trigger keywords: `positioning`, `position`, `category`, `brand`, `message`, `messaging`, `segment`, `audience`, `pozycjonowanie`, `kategoria`, `marka`, `komunikat`, `segment`
- framework tags: `positioning`, `category`, `marketing_laws`
- description: clarify the buyer's category, target customer, useful contrast, and message
- diagnostic questions:
  - What category does the buyer use to understand this offer?
  - What is the clearest contrast with the main alternative?
  - Which customer segment is most likely to care about that contrast now?

### `value_equation`

- profile domains: `offer_pricing`, `sales`, `marketing`
- decision kinds: `pricing`, `sales`, `marketing`
- expert ids: `offer_pricing`, `sales`, `marketing`
- trigger keywords: `price`, `pricing`, `offer`, `package`, `packaging`, `guarantee`, `discount`, `margin`, `willingness to pay`, `cena`, `ceny`, `oferta`, `pakiet`, `gwarancja`, `rabat`, `marża`
- framework tags: `value_equation`, `offer`, `pricing`, `risk_reversal`
- description: stress-test perceived outcome value, speed, effort, risk, packaging, and price logic
- diagnostic questions:
  - Which outcome matters enough to pay for?
  - What slows the buyer's path to that outcome?
  - Which effort, risk, or uncertainty suppresses perceived value?

### `customer_job_evidence`

- profile domains: `product_customer`, `growth`
- decision kinds: `product_customer`, `growth`
- expert ids: `product_customer`, `growth`
- trigger keywords: `customer`, `user`, `problem`, `pain`, `job to be done`, `jtbd`, `adoption`, `retention`, `churn`, `research`, `klient`, `użytkownik`, `problem`, `ból`, `adopcja`, `retencja`, `badania klientów`
- framework tags: `jtbd`, `customer_research`, `problem_evidence`
- description: separate the proposed product idea from evidence of a real customer job, pain, and adoption behavior
- diagnostic questions:
  - What job is the customer already trying to complete?
  - What current behavior proves the problem matters?
  - What evidence would show that the proposed solution is not the real answer?

### `growth_loop`

- profile domains: `growth`, `marketing`, `product_customer`
- decision kinds: `growth`, `marketing`, `product_customer`
- expert ids: `growth`, `marketing`, `product_customer`
- trigger keywords: `growth`, `referral`, `viral`, `acquisition`, `activation`, `retention`, `channel`, `conversion`, `loop`, `wzrost`, `akwizycja`, `aktywacja`, `retencja`, `kanał`, `konwersja`, `pętla`
- framework tags: `growth_loop`, `acquisition`, `retention`, `referral`
- description: test whether acquisition, activation, retention, or referral creates a repeatable reinforcing loop
- diagnostic questions:
  - What user action creates the next unit of growth?
  - Where does the loop lose energy?
  - Which metric would prove that the loop compounds rather than merely spikes?

### `operating_constraint`

- profile domains: `operator`, `strategy`
- decision kinds: `operations`, `strategy`
- expert ids: `operator`, `strategy`
- trigger keywords: `operations`, `process`, `implementation`, `execution`, `owner`, `kpi`, `cadence`, `workflow`, `bottleneck`, `constraint`, `operacje`, `proces`, `wdrożenie`, `egzekucja`, `właściciel`, `wąskie gardło`, `ograniczenie`
- framework tags: `operations`, `constraint`, `execution`, `principles`
- description: turn a recommendation into a sequence with one primary constraint, clear ownership, and stop conditions
- diagnostic questions:
  - What is the current bottleneck?
  - Who owns the next irreversible or gating step?
  - Which operating signal should trigger a stop, escalation, or resource shift?

### `reversibility_experiment`

- profile domains: none
- decision kinds: none
- expert ids: `strategy`, `product_customer`, `growth`, `operator`
- trigger keywords: `test`, `experiment`, `pilot`, `a/b test`, `reversible`, `validate`, `validation`, `eksperyment`, `test`, `pilotaż`, `odwracalny`, `walidacja`
- framework tags: `experiment`, `reversibility`, `test`, `decision_making`
- description: choose the smallest reversible action that can resolve the key uncertainty before a larger commitment
- diagnostic questions:
  - Which assumption currently drives the decision most strongly?
  - What is the cheapest test that could falsify it?
  - What threshold would justify scaling, stopping, or deferring?

This framework intentionally has no domain or decision-kind score. It becomes eligible only when current-case language and reversibility make it relevant.

## Selection contract

Create `src/council/framework_selector.py`.

### Typed models

Add these models to `council_os_models.py`:

```text
FrameworkMatch
- framework_id: str
- score: int
- reason_labels: list[str]
- assigned_expert_ids: list[str]

FrameworkSelection
- status: ok | empty | disabled | unavailable
- policy_version: str
- matches: list[FrameworkMatch]
- by_expert: dict[str, list[str]]
- error_labels: list[str]

FrameworkClaimRef
- expert_id: str
- claim_index: int
- issue_label: framework_as_fact | framework_overreach

FrameworkAssessment
- misclassified_fact_claims: list[FrameworkClaimRef]
- rejected_framework_ids: list[str]
- overreach_labels: list[str]

FrameworkSelectionSummary
- status: ok | empty | disabled | unavailable
- policy_version: str
- selected_framework_ids: list[str]
- by_expert: dict[str, list[str]]
- reason_labels_by_framework: dict[str, list[str]]
- retrieval_status_by_expert: dict[str, str]
- rejected_framework_ids: list[str]
- framework_issue_labels: list[str]
```

No field contains book text, private notes, retrieved passages, historical postmortems, or private source ids.

### Selector interface

Use a callable boundary equivalent to:

```text
FrameworkSelector(query, profile, routed_expert_ids) -> FrameworkSelection
```

The selector accepts only:

- the current query string;
- `ProblemProfile`;
- routed domain expert ids.

It does not accept Decision Memory history, prior outcomes, blind memos, rebuttals, Red Team output, Evidence Judge output, or private RAG chunks.

### Scoring

Use this exact integer scoring policy:

```text
+4 primary profile-domain match
+2 per matching secondary profile domain, capped at +4
+3 decision-kind match
+1 per routed expert supported by the framework, capped at +2
+1 per matching trigger keyword, capped at +3
+2 `reversibility_experiment` bonus when:
   - profile.reversibility == "reversible", and
   - query contains at least one of that framework's trigger keywords
+2 `strategic_choice` bonus when:
   - profile.reversibility == "hard_to_reverse" or profile.risk_level == "high"
```

A framework must score at least `5` to be eligible.

Stable reason labels are:

```text
primary_domain:<domain>
secondary_domain:<domain>
decision_kind:<kind>
routed_expert:<expert_id>
keyword:<normalized_keyword>
reversibility_bonus
high_risk_strategy_bonus
```

Ties resolve by:

1. higher score;
2. registry order;
3. stable framework id.

Select at most 3 frameworks globally.

For each routed expert, assign only selected frameworks whose `expert_ids` include that expert. Cap expert assignment at 2 using the global score and order.

If no framework reaches score 5, return `FrameworkSelection(status="empty")` with no matches.

### Keyword matching

Use the same boundary-aware deterministic style already used by `business_routing.py`:

- multi-word phrases use casefolded substring matching;
- single words use word boundaries;
- duplicate keyword matches after normalization count once;
- no translation, stemming service, or LLM call is used during selection.

## Framework-aware retrieval

Extend `query_knowledge_result`, `query_knowledge`, and the internal filter builder with:

```text
framework_tags: list[str] | None = None
```

When supplied, the Pinecone metadata filter adds one `framework_tags` clause using the same array-filter convention already used for `domains` and `experts`.

When omitted or empty, the filter shape and behavior remain backward compatible.

### Per-expert retrieval policy

For each routed expert:

1. collect the union of `framework_tags` from that expert's assigned selected frameworks;
2. if the union is empty, use the existing retrieval path unchanged;
3. query once with `domains + experts + framework_tags`;
4. if status is `ok`, use that result;
5. if status is `no_matches`, retry exactly once with the existing `domains + experts` filters and no framework tags;
6. if status is `unavailable`, preserve `unavailable` and do not issue the base fallback query;
7. expose a sanitized retrieval diagnostic only.

Per-expert diagnostic labels are exactly:

```text
framework_match
framework_no_match_fallback_ok
framework_no_match_fallback_no_matches
framework_unavailable
base_retrieval_ok
base_retrieval_no_matches
base_retrieval_unavailable
```

## Council OS integration

Framework selection runs after `profile_problem` and `route_experts`, before any private retrieval or blind LLM call.

`CouncilOS` accepts an optional selector dependency. Production defaults to the deterministic v1 selector. Tests and explicit configuration may inject a disabled selector returning `FrameworkSelection(status="disabled")`.

If the selector raises unexpectedly, Council OS converts the failure to `FrameworkSelection(status="unavailable", error_labels=["framework_selector_unavailable"])` and continues with base retrieval.

### Blind round

Each blind expert sees only the framework cards assigned to that expert. A card contains:

- framework id;
- short registry description;
- the 3 registry diagnostic questions.

The blind prompt includes this doctrine:

```text
Selected frameworks are analysis lenses. They do not establish facts about this case.
Use [FMW] for material claims that come mainly from a framework.
Use [F] only when supplied evidence independently supports the factual claim.
Reject a framework when it does not fit the current case.
```

Experts are not required to use every assigned framework.

Blind prompts still contain no peer memos, consensus, Decision Memory learning context, prior outcomes, or Chairman preference.

### Decision Memory ordering

Decision Memory v2 remains after blind memos. The order is fixed:

```text
framework selection
-> framework-aware retrieval
-> blind memos
-> Decision Memory learning context
-> rebuttals
```

Framework selection never consumes Decision Memory in v1.

### Rebuttals

Rebuttals may see the selected framework ids used by the participating experts so they can challenge a shared lens or explain why a framework does not fit. They receive no registry source provenance beyond the public framework card metadata.

### Red Team

Red Team receives the sanitized framework selection used by the domain experts.

It must challenge:

- whether each selected framework is applicable;
- whether a material alternative lens was ignored;
- whether several experts produced correlated reasoning because they shared the same lens;
- whether a framework rule is being treated as empirical evidence.

Red Team does not select or add frameworks in v1.

### Evidence Judge

Extend `EvidenceAssessment` with:

```text
framework_assessment: FrameworkAssessment
```

Evidence Judge receives selected framework ids and expert assignments, the existing expert claims and labels, current provenance/status, rebuttals, Red Team output, and the existing Decision Memory learning context.

When a `[F]` claim appears to depend mainly on a framework, Evidence Judge records a `FrameworkClaimRef` using `expert_id` and the zero-based position of the claim in that expert's `claims` list. It does not copy the claim text into `FrameworkAssessment`.

Evidence Judge may reject a selected framework as inapplicable for final synthesis. This does not alter the historical blind memo; it limits downstream reliance on the lens.

### Chairman

Chairman receives the framework selection plus `FrameworkAssessment`.

The Chairman prompt states:

- current evidence outranks framework precedent;
- a rejected framework must not support the final recommendation;
- agreement caused by a shared framework is not independent confirmation;
- a framework may be named in the explanation only when it materially shaped the reasoning;
- a framework cannot independently raise confidence or determine a vote.

No vote multiplier or confidence multiplier is added in v1.

## Decision Memory integration

Extend `CouncilOSResult` with optional `framework_selection_summary`.

`FrameworkSelectionSummary` is built after Evidence Judge so it can include rejected framework ids and issue labels. Decision Memory persists only this summary.

The summary supports later analysis of:

- active framework ids;
- expert assignments;
- deterministic reason labels;
- framework-specific retrieval success or fallback;
- Evidence Judge rejection;
- policy version.

V1 does not use resolved outcomes to alter future framework scores or registry order.

### Storage migration

Add nullable `framework_selection_json` to `decisions` using the same additive migration pattern as `learning_context_json`.

Existing v1/v2 databases retain every row. Before adding the column, initialization checks `PRAGMA table_info(decisions)` and executes one `ALTER TABLE` only when the column is absent.

Decision detail responses may expose the sanitized framework summary as an additive field. Existing list and calibration endpoints do not need new framework fields in v1.

## Privacy boundary

The public repository may contain framework ids, short original descriptions, generic diagnostic questions, deterministic tag names, and selection rules.

It must not contain private book text, private book summaries, Drive file ids, private source paths, raw retrieved chunks, copyrighted chapter excerpts, or historical postmortem/notes copied into framework prompts.

Framework-aware retrieval can use private chunks internally exactly as current private RAG does. External `CouncilOSResult`, Decision Memory diagnostics, logs, and public source displays remain sanitized.

## Failure behavior

Framework selection and framework-specific retrieval are non-critical.

Selector exception:

```text
status = unavailable
error_labels = ["framework_selector_unavailable"]
behavior = continue with base expert/domain retrieval
```

Framework-specific `no_matches`:

```text
behavior = one base expert/domain fallback query
```

Framework-specific `unavailable`:

```text
behavior = preserve unavailable; no second retrieval call
```

Evidence Judge framework-assessment parse failure:

```text
framework_assessment = empty safe FrameworkAssessment
error label = framework_assessment_parse_error
```

No raw exception text enters prompts, SSE payloads, Decision Memory, or public API errors.

## Backward compatibility

`query_knowledge_result` and `query_knowledge` keep their existing behavior when `framework_tags` is omitted.

New `EvidenceAssessment` and `CouncilOSResult` fields have safe defaults so older construction paths remain valid.

Council OS remains usable with framework selection disabled or empty.

Decision Memory API changes are additive. Existing clients can ignore `framework_selection_summary`.

No `.github/workflows` file is changed by this phase.

## Testing strategy

Implementation follows TDD.

### Registry and selector tests

Cover:

- registry ids are unique;
- registry order is stable;
- registry descriptions/questions contain no private-source identifiers or copied source text;
- deterministic scoring for representative strategy, pricing, marketing, product, growth, and operations queries;
- exact threshold behavior at score 5;
- exact score-reason labels;
- max 3 selected globally;
- max 2 assigned per expert;
- deterministic tie breaking;
- `reversibility_experiment` does not qualify merely because common experts are routed;
- empty selection when all candidates score below 5;
- selector has no Decision Memory dependency.

### Retrieval tests

Cover:

- `framework_tags` enters the metadata filter only when supplied;
- existing calls without framework tags produce the old filter shape;
- framework match returns directly;
- `no_matches` performs exactly one base fallback;
- `unavailable` performs no fallback;
- diagnostics use only the specified labels;
- returned chunks retain current `framework_tags` metadata behavior.

### Council OS tests

Cover:

- selector runs after routing and before retrieval;
- framework-aware retrieval runs before blind LLM calls;
- blind prompt includes only frameworks assigned to that expert;
- blind prompt contains no Decision Memory learning context or peer output;
- framework cards contain no private source text;
- `[FMW]` doctrine appears in blind prompts;
- Decision Memory still begins only after blind memos;
- Red Team receives sanitized framework ids/assignments;
- Evidence Judge can reject a framework;
- a `[F]` framework misuse is referenced by `expert_id + claim_index` without copying claim text into assessment;
- Chairman cannot rely on an Evidence-Judge-rejected framework;
- selector failure falls back to normal Council OS;
- disabled/empty selection preserves existing behavior.

### Decision Memory tests

Cover:

- additive migration of a v2 database to include `framework_selection_json`;
- capture persists only `FrameworkSelectionSummary`;
- decision detail exposes sanitized framework diagnostics;
- no framework prompt, RAG chunk, private note, postmortem, or source id is persisted in the new JSON field.

### Privacy regression tests

Use unique sentinels in private RAG chunk text, Drive/source ids, simulated private notes, Decision Memory postmortems, and selector exception messages.

Assert those sentinels do not enter the framework registry, selection summary, Decision Memory framework JSON, public Council OS result, or sanitized error labels.

## Local verification policy

GitHub Actions are not an acceptance gate for this phase and workflow files are not modified.

Before merge, run locally on code matching the PR head:

- focused Framework Selector tests;
- Council OS and Decision Memory regressions relevant to changed contracts;
- the full available pytest suite when the local checkout supports it;
- project quality gate;
- `python -m compileall`;
- Ruff only if the local environment has it installed.

Any unavailable local tool is reported explicitly rather than treated as passing.

## Acceptance criteria

Framework Selector v1 is complete when all of the following hold:

1. Selection is deterministic and uses only the current query, profile, routed experts, and the versioned registry.
2. At most 3 frameworks are selected globally and at most 2 are assigned to one expert.
3. Weak matches below score 5 produce no forced framework.
4. Framework-specific RAG falls back exactly once to ordinary expert/domain RAG on `no_matches` and does not fallback on `unavailable`.
5. Blind experts receive framework lenses before analysis but receive no Decision Memory history or peer output.
6. Framework-derived claims remain explicitly separated from factual claims through `[FMW]` doctrine.
7. Evidence Judge identifies framework-as-fact misuse by stable claim reference without storing the claim text in framework diagnostics.
8. Evidence Judge can reject framework applicability before final synthesis.
9. Chairman cannot use an Evidence-Judge-rejected framework as support for the verdict.
10. Council OS continues normally when framework selection fails, is empty, or is disabled.
11. Decision Memory stores only sanitized framework diagnostics.
12. Existing v2 SQLite databases migrate additively without data loss.
13. No private corpus text, private source identifiers, Drive ids, notes, or historical postmortems enter public framework artifacts.
14. Existing Council OS, retriever, and Decision Memory behavior remains compatible when framework selection is empty or disabled.
15. Local tests, quality gate, and compilation pass on the code being merged, with any unavailable tooling disclosed.
