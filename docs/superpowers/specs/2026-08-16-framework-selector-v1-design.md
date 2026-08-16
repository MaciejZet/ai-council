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

Infrastructure failure remains distinct from `no_matches`. An `unavailable` framework-specific retrieval does not trigger repeated backend calls unless the fallback is explicitly safe under the existing retriever contract.

## Architecture

### `framework_registry.py`

Create `src/council/framework_registry.py`.

The module owns immutable framework definitions and registry versioning.

Suggested model:

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

The description and diagnostic questions must be short, original wording. They must not quote or reconstruct book passages.

Registry constant:

```text
FRAMEWORK_POLICY_VERSION = "framework-selector-v1"
```

### Initial registry

V1 starts with a small set that maps cleanly to current Council OS roles.

#### `strategic_choice`

Purpose: isolate the real strategic challenge, the explicit choice, trade-offs, and a coherent action set.

Primary domains: `strategy`, `business`.

Experts: `strategy`, `operator`, `chairman`.

Example tags: `strategic_choice`, `good_strategy`, `resource_allocation`.

Diagnostic questions:

- What is the decisive constraint or challenge?
- Which real alternative is being rejected?
- What actions must be mutually reinforcing for the choice to work?

#### `competitive_advantage`

Purpose: test whether the proposal creates a durable reason to win rather than temporary activity.

Primary domains: `strategy`, `innovation`, `business`.

Experts: `strategy`, `product_customer`, `chairman`.

Example tags: `competitive_advantage`, `moat`, `zero_to_one`.

Diagnostic questions:

- What is meaningfully different from the closest substitute?
- Why would that advantage persist after competitors respond?
- Which assumption would make the claimed advantage disappear?

#### `positioning_category`

Purpose: clarify category, target customer, contrast, message, and mental availability.

Primary domains: `marketing`, `strategy`.

Experts: `marketing`, `sales`.

Example tags: `positioning`, `category`, `marketing_laws`.

Diagnostic questions:

- What category does the buyer use to understand this offer?
- What is the clearest contrast with the main alternative?
- Which customer segment is most likely to care about that contrast now?

#### `value_equation`

Purpose: stress-test perceived value, speed, effort, risk, packaging, and price logic.

Primary domains: `pricing`, `marketing`, `business`.

Experts: `offer_pricing`, `sales`, `marketing`.

Example tags: `value_equation`, `offer`, `pricing`, `risk_reversal`.

Diagnostic questions:

- Which outcome matters enough to pay for?
- What slows the buyer's path to that outcome?
- Which effort, risk, or uncertainty suppresses perceived value?

#### `customer_job_evidence`

Purpose: separate the stated product idea from evidence of a real customer problem and adoption behavior.

Primary domains: `business`, `innovation`, `design`.

Experts: `product_customer`, `growth`.

Example tags: `jtbd`, `customer_research`, `problem_evidence`.

Diagnostic questions:

- What job is the customer already trying to complete?
- What current behavior proves the problem matters?
- What evidence would show that the proposed solution is not the real answer?

#### `growth_loop`

Purpose: test whether acquisition and retention can reinforce one another instead of relying on isolated campaign spend.

Primary domains: `marketing`, `business`.

Experts: `growth`, `marketing`, `product_customer`.

Example tags: `growth_loop`, `acquisition`, `retention`, `referral`.

Diagnostic questions:

- What user action creates the next unit of growth?
- Where does the loop lose energy?
- Which metric would prove that the loop compounds rather than merely spikes?

#### `operating_constraint`

Purpose: turn a recommendation into an executable sequence with one primary bottleneck, ownership, and stop conditions.

Primary domains: `business`, `productivity`.

Experts: `operator`, `strategy`.

Example tags: `operations`, `constraint`, `execution`, `principles`.

Diagnostic questions:

- What is the current bottleneck?
- Who owns the next irreversible or gating step?
- Which operating signal should trigger a stop, escalation, or resource shift?

#### `reversibility_experiment`

Purpose: choose the smallest reversible action that can resolve the key uncertainty before larger commitment.

Primary domains: broad business applicability.

Experts: `growth`, `product_customer`, `operator`, `strategy`.

Example tags: `experiment`, `reversibility`, `test`, `decision_making`.

Diagnostic questions:

- Which assumption currently drives the decision most strongly?
- What is the cheapest test that could falsify it?
- What threshold would justify scaling, stopping, or deferring?

## Selection contract

Create `src/council/framework_selector.py`.

### Typed result

Suggested models in `council_os_models.py`:

```text
FrameworkMatch
- framework_id
- score
- reason_labels
- assigned_expert_ids

FrameworkSelection
- policy_version
- matches
- by_expert

FrameworkSelectionSummary
- policy_version
- selected_framework_ids
- by_expert
- reason_labels_by_framework
- retrieval_status_by_expert
```

No field contains book text, private notes, retrieved passages, or source ids.

### Inputs

The selector accepts only:

- the current query string;
- `ProblemProfile`;
- routed domain expert ids.

It does not accept:

- Decision Memory history;
- prior outcomes;
- blind memos;
- rebuttals;
- Red Team output;
- Evidence Judge output;
- private RAG chunks.

### Scoring

Use explicit integer scoring.

Suggested score:

```text
+4 primary-domain match
+2 matching secondary domain, capped at +4
+3 decision-kind match
+2 each routed expert supported by the framework, capped at +4
+1 matching trigger keyword, capped at +3
+1 if `reversibility_experiment` matches a reversible or low/medium-risk decision with test/experiment language
+1 if `strategic_choice` matches a hard-to-reverse or high-risk decision
```

A framework must score at least `5` to be eligible.

Ties resolve by:

1. higher score;
2. registry order;
3. stable framework id.

Select at most 3 frameworks globally.

For each routed expert, assign only selected frameworks whose `expert_ids` include that expert. Cap expert assignment at 2 using the global score/order.

If no framework reaches the threshold, return an empty valid selection.

### Keyword matching

Use the same boundary-aware deterministic style already used by `business_routing.py`. Multi-word phrases may use casefolded substring matching. Single words must respect word boundaries.

Polish trigger aliases may be included directly in the registry where useful. Do not use translation or LLM calls during selection.

## Framework-aware retrieval

Extend the existing retrieval functions with an optional parameter:

```text
framework_tags: list[str] | None = None
```

`_build_filter` adds a `framework_tags` clause when the list is non-empty, using the same metadata-filter semantics currently used for `domains` and `experts`.

### Per-expert policy

For each routed expert:

1. collect framework tags from that expert's assigned framework lenses;
2. if there are no assigned framework tags, use the existing retrieval path unchanged;
3. query with `domains + experts + framework_tags`;
4. when the result status is `ok`, use it;
5. when the result status is `no_matches`, retry once with the current `domains + experts` filters and no framework tags;
6. when the result is `unavailable`, preserve `unavailable` and avoid a second backend call by default;
7. expose only a sanitized retrieval diagnostic, not the tag-filtered raw source payload.

The fallback must be deterministic and covered by tests.

### Retrieval diagnostics

Per expert, track one of:

```text
framework_match
framework_no_match_fallback_ok
framework_no_match_fallback_no_matches
framework_unavailable
base_retrieval
```

These labels may appear in `FrameworkSelectionSummary` and Decision Memory capture.

## Blind-round prompt behavior

Framework selection happens before expert retrieval and before any blind LLM call.

Each blind expert sees only the framework cards assigned to that expert. A card contains:

- framework id;
- short public description;
- 2-3 diagnostic questions.

Prompt doctrine:

```text
Selected frameworks are analysis lenses. They do not establish facts about this case.
Use [FMW] for material claims that come mainly from a framework.
Use [F] only when supplied evidence independently supports the factual claim.
A framework may be rejected when it does not fit the current case.
```

Experts are not required to use every assigned framework.

Blind prompts still contain no peer memos, consensus, historical Decision Memory context, or Chairman preference.

## Red Team behavior

Red Team receives the sanitized framework selection used by the domain experts.

It must challenge:

- whether the selected framework is actually applicable;
- whether the council ignored a material alternative lens;
- whether multiple experts produced correlated reasoning because they shared the same framework;
- whether a framework is being treated as empirical evidence.

Red Team does not select new frameworks in v1.

## Evidence Judge behavior

Evidence Judge receives:

- selected framework ids and expert assignments;
- expert claims with existing claim labels;
- current provenance/status;
- the normal Red Team and rebuttal material;
- Decision Memory learning context under the existing v2 rules.

Extend `EvidenceAssessment` with a small typed framework assessment, for example:

```text
FrameworkAssessment
- misclassified_fact_claims
- framework_overreach_labels
- rejected_framework_ids
```

`misclassified_fact_claims` should use stable claim identifiers or sanitized short labels when available. Avoid copying long private text into the assessment.

Evidence Judge may mark a selected framework as inapplicable for final synthesis. This does not retroactively alter the blind memo; it limits downstream reliance on the framework.

## Chairman behavior

Chairman receives the framework selection plus Evidence Judge framework assessment.

Instructions:

- current evidence outranks framework precedent;
- a rejected framework must not support the final recommendation;
- framework agreement across experts is not independent confirmation;
- the final explanation should identify a framework only when it materially shaped the reasoning;
- a framework cannot independently raise confidence.

No automatic vote or confidence multiplier is added in v1.

## Decision Memory integration

Extend `CouncilOSResult` with optional `framework_selection_summary`.

Decision Memory persists only that sanitized summary. No new historical text fields are introduced.

The stored summary supports later analysis such as:

- which framework ids were active;
- which experts received each framework;
- whether framework-specific retrieval matched or fell back;
- whether Evidence Judge rejected a framework;
- policy version used for the decision.

V1 does not use Decision Memory outcomes to change future framework scores. That feedback loop can be evaluated only after enough resolved decisions exist.

### Storage migration

Add an optional `framework_selection_json` column to the existing `decisions` table using the same additive migration pattern as `learning_context_json`.

Existing v1/v2 databases must retain all rows and continue to load when the new column is absent before initialization.

## Privacy boundary

The public repository may contain:

- framework ids;
- short original descriptions;
- generic diagnostic questions;
- public tag names;
- deterministic selection rules.

It must not contain:

- private book text;
- private book summaries;
- Drive file ids;
- raw retrieved chunks;
- private source paths;
- copyrighted chapter excerpts;
- historical postmortem/notes copied into framework prompts.

Framework-aware retrieval can use private chunks internally exactly as current private RAG does. External `CouncilOSResult`, Decision Memory diagnostics, logs, and public source displays remain sanitized.

## Failure behavior

Framework selection is non-critical.

If the selector raises unexpectedly:

- Council OS continues with an empty framework selection;
- retrieval uses the current expert/domain path;
- the result records a fixed sanitized label such as `framework_selector_unavailable`;
- no exception text is exposed to prompts or API output.

If framework-filtered retrieval returns no matches:

- retry base expert/domain retrieval once;
- record the fallback diagnostic.

If the knowledge backend is unavailable:

- preserve the existing knowledge status semantics;
- do not manufacture a framework-based answer as a replacement for missing evidence.

## Backward compatibility

`query_knowledge_result` and `query_knowledge` keep their existing behavior when `framework_tags` is omitted.

`CouncilOS` remains usable with no explicit framework selector dependency by using the deterministic default selector or a disabled selector in tests/configuration.

New result fields use defaults so older construction paths remain valid.

Decision Memory API endpoints remain additive. Existing clients can ignore the new framework summary.

## Testing strategy

Implementation follows TDD.

### Registry and selector tests

Cover:

- registry ids are unique;
- registry descriptions/questions contain no obvious private-source identifiers;
- deterministic scoring for representative strategy, pricing, marketing, product, growth, and operations queries;
- exact threshold behavior at score `5`;
- max 3 selected globally;
- max 2 assigned per expert;
- deterministic tie breaking;
- empty selection when all candidates score below threshold;
- selector accepts only current-case inputs and has no Decision Memory dependency.

### Retrieval tests

Cover:

- `framework_tags` enters the Pinecone metadata filter only when supplied;
- existing retrieval calls without framework tags produce the old filter shape;
- framework match returns directly;
- `no_matches` performs exactly one base fallback;
- `unavailable` does not silently become `no_matches`;
- fallback diagnostics are deterministic;
- returned chunks retain current `framework_tags` metadata behavior.

### Council OS tests

Cover:

- selector runs after routing and before any retrieval/blind LLM call;
- blind prompt includes only frameworks assigned to that expert;
- blind prompt contains no Decision Memory learning context;
- framework cards contain no private source text;
- `[FMW]` doctrine appears in blind prompt;
- Red Team receives sanitized framework ids/assignments;
- Evidence Judge can reject a framework;
- Chairman cannot rely on a framework rejected by Evidence Judge;
- selector failure falls back to normal Council OS;
- existing learning-context ordering remains `blind -> Decision Memory -> rebuttal`.

### Decision Memory tests

Cover:

- additive migration of a v2 database to include `framework_selection_json`;
- capture persists only `FrameworkSelectionSummary`;
- decision detail exposes sanitized framework diagnostics;
- no framework prompt text, RAG chunk, private note, or source id is persisted.

### Privacy regression tests

Use unique sentinels in:

- private RAG chunk text;
- Drive/source ids;
- simulated private notes;
- Decision Memory postmortems;
- selector exception messages.

Assert those sentinels do not enter:

- framework registry output;
- selection summary;
- Decision Memory framework JSON;
- public Council OS result;
- logs or error labels under tested paths.

## Local verification policy

GitHub Actions are not an acceptance gate for this phase and workflow files are not modified as part of the feature.

Before merge, run locally on code matching the PR head:

- focused Framework Selector tests;
- Council OS and Decision Memory regression tests relevant to changed contracts;
- full available pytest suite when the local reconstructed checkout supports it;
- project quality gate;
- `python -m compileall`;
- Ruff only if the local environment has it installed.

Any unavailable local tool must be reported explicitly rather than treated as passing.

## Acceptance criteria

Framework Selector v1 is complete when all of the following hold:

1. Selection is deterministic and uses only the current query, profile, routed experts, and a versioned registry.
2. At most 3 frameworks are selected globally and at most 2 are assigned to one expert.
3. Weak matches below score 5 produce no forced framework.
4. Framework-specific RAG falls back once to ordinary expert/domain RAG on `no_matches`.
5. Blind experts receive framework lenses before analysis but receive no Decision Memory history or peer output.
6. Framework-derived claims remain explicitly separated from factual claims through `[FMW]` doctrine.
7. Evidence Judge can reject framework applicability before final synthesis.
8. Chairman cannot use an Evidence-Judge-rejected framework as support for the verdict.
9. Council OS continues normally when framework selection fails or is disabled.
10. Decision Memory stores only sanitized framework diagnostics.
11. Existing v2 SQLite databases migrate additively without data loss.
12. No private corpus text, source identifiers, Drive ids, notes, or historical postmortems enter public framework artifacts.
13. Existing Council OS and Decision Memory behavior remains compatible when framework selection is empty or disabled.
14. Local tests, quality gate, and compilation pass on the code being merged, with any unavailable tooling disclosed.
