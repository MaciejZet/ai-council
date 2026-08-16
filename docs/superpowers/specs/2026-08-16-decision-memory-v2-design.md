# Decision Memory v2 Design

## Goal

Decision Memory v2 turns stored outcomes into a controlled calibration signal for future Council OS deliberations.

The system may learn from resolved decisions, but historical outcomes must not contaminate the blind round, override current evidence, or create a self-confirming loop. Historical data is introduced only after independent expert memos exist and only when the available sample is large enough to justify influence.

The target flow is:

```text
current question
  -> profile + expert routing
  -> private knowledge retrieval
  -> blind expert memos
  -> Decision Memory learning context
  -> rebuttals
  -> Red Team
  -> Evidence Judge
  -> Chairman
  -> verdict + learning diagnostics
  -> sanitized Decision Memory capture
  -> later outcome
  -> updated calibration
```

## Scope

This version adds:

- a user-scoped learning-context read model over resolved Decision Memory records;
- deterministic calibration signals by expert and primary domain;
- conservative sample-size gates;
- deterministic retrieval of a small set of analogous resolved decisions;
- bias alerts derived from historical voting and outcome patterns;
- controlled injection of learning context after the blind round;
- minority protection for historically well-calibrated dissent;
- explicit Evidence Judge authority to reject historical analogies;
- a sanitized `learning_context_summary` in Council OS output;
- capture of the learning signals that were active when a decision was made;
- tests proving privacy, user isolation, blind-round independence, and threshold behavior.

This version does not add embeddings for historical decisions, model fine-tuning, automatic expert creation, automatic mutation of expert prompts, cross-user learning, or autonomous changes to routing policy.

## Core policy

Historical performance is a calibration input, not a source of business truth.

The current question and current evidence retain priority. A historical signal can adjust how much attention downstream stages pay to an expert or analogy, but it cannot independently determine a verdict.

The blind round remains unchanged by Decision Memory. No past decision, outcome, calibration metric, postmortem, bias alert, or prior verdict is visible to an expert before that expert submits the initial memo and vote.

## Architecture

### Components

Decision Memory v2 adds two focused components and one integration boundary.

#### `DecisionLearningStore`

Location: `src/storage/decision_learning.py`.

Responsibilities:

- read only user-owned, resolved Decision Memory records;
- aggregate calibration inputs needed by the learning layer;
- return structured rows without raw RAG content or source inventory;
- enforce user scoping at every query;
- expose deterministic methods that are easy to test independently.

The store may reuse the same SQLite database as Decision Memory v1. It should not duplicate the write path or become responsible for Council orchestration.

#### `LearningContextBuilder`

Location: `src/council/learning_context.py`.

Responsibilities:

- compute expert/domain calibration signals;
- classify sample strength;
- select analogous resolved decisions;
- produce bias alerts;
- detect historically strong minority experts;
- produce a compact, typed `LearningContext` for downstream Council stages;
- expose a sanitized summary suitable for API output and Decision Memory capture.

The builder must be deterministic for a fixed database state and problem profile. LLM calls are not used to choose analogies or calibration levels in v2.

#### Council OS integration

`CouncilOS` receives an optional learning-context provider or builder dependency. The default Council OS behavior remains valid when no learning component is configured or when learning is unavailable.

The integration point is after `_run_blind_memos` has completed successfully enough to continue deliberation and before rebuttals begin.

This creates a hard sequencing guarantee:

```text
profile -> route -> blind memos -> build learning context -> later stages
```

The learning layer never participates in expert routing in v2.

## Data contracts

### `SampleStrength`

```text
none
weak
normal
```

Sample-strength policy for an expert in the current primary domain:

- `0-4` scored decisions: `none`;
- `5-14` scored decisions: `weak`;
- `15+` scored decisions: `normal`.

A scored decision is one with a non-null `resolved_vote`.

The thresholds are constants with tests. They are not configurable through prompts.

### `ExpertCalibrationSignal`

Each signal contains only fields needed for downstream calibration:

- `expert_id`;
- `primary_domain`;
- `sample_size`;
- `sample_strength`;
- `hit_rate`;
- `mean_confidence`;
- `brier_like_error`;
- `confidence_bias`;
- `reliability_rank` or equivalent deterministic ordering metadata;
- optional flags such as `overconfident`, `underconfident`, `strong_minority_candidate`.

`confidence_bias` is descriptive. It must not be presented as a statistically rigorous calibration curve.

### `AnalogDecision`

An analogy contains a sanitized subset of an earlier resolved decision:

- `decision_id`;
- `primary_domain`;
- `decision_kind`;
- `reversibility`;
- `risk_level`;
- `verdict`;
- `verdict_confidence`;
- `resolved_vote`;
- `outcome_status`;
- a deterministic similarity score;
- matching dimensions used to produce that score.

The analogy does not contain:

- prior memo prose;
- prior rebuttal prose;
- retrieved source text;
- source inventory;
- Drive ids or paths;
- book text;
- prior postmortem or notes;
- prior recommendation prose.

The original historical query is not passed into Council prompts in v2. This reduces prompt leakage and prevents the historical store from turning into an uncontrolled text retrieval layer.

### `LearningContext`

The typed context contains:

- current problem metadata;
- `expert_signals`;
- `analog_decisions`;
- `bias_alerts`;
- `minority_protection` metadata;
- `sample_summary`;
- `status`: `ok | insufficient_history | disabled | unavailable`;
- sanitized error labels when needed.

The current user id exists only at the storage boundary and is never sent in model prompts.

### `LearningContextSummary`

Council OS output exposes a smaller diagnostics structure:

- learning status;
- number of scored historical decisions considered;
- number of analogies used;
- active expert calibration levels;
- bias-alert labels;
- minority-protection labels;
- analogies rejected by Evidence Judge, represented by ids/reason labels only;
- whether learning signals were active in the final decision.

No historical free text is exposed through this summary.

## Historical analogy ranking

V2 uses a deterministic metadata score rather than vector similarity.

Candidate records must:

- belong to the current user;
- have a non-null `resolved_vote`;
- exclude the current decision when an id is available;
- satisfy storage-level privacy constraints.

Suggested scoring:

```text
+4 primary_domain match
+3 decision_kind match
+2 reversibility match
+2 risk_level match
+1 each matching secondary-domain signal when available, capped
```

Ties are resolved deterministically by:

1. higher similarity score;
2. more recent outcome timestamp;
3. stable decision id ordering.

Return at most 3 analogies in v2. Fewer are acceptable.

An analogy can be included when expert calibration sample strength is `none`, but its influence is informational only. Downstream prompts must label such context accordingly.

## Calibration behavior

### Expert calibration

The v1 blind-vote calibration definition remains the basis for expert performance:

```text
correct = blind_vote == resolved_vote
```

For the current primary domain, calculate each routed expert's sample size, hit rate, mean confidence, and Brier-like error over scored decisions.

Signals are ordered primarily by sample strength, then by lower Brier-like error, then higher hit rate, then stable expert id. This ranking is advisory.

### Confidence correction

The learning layer may flag systematic confidence bias. The downstream Council must not mutate the stored blind confidence value.

Downstream prompts receive guidance equivalent to:

```text
Expert X has NORMAL historical calibration evidence in this domain.
Treat the historical signal as an attention modifier, not as a vote multiplier.
```

A weak or normal signal can affect scrutiny and discussion priority. V2 does not numerically rewrite votes or confidence values.

### Chairman behavior

The Chairman may use learning context only after considering current evidence, rebuttals, Red Team, and Evidence Judge output.

The Chairman prompt must state:

- historical performance cannot override current evidence;
- analogies are precedents, not facts about the current situation;
- sample strength `none` must not affect the verdict;
- `weak` can justify additional scrutiny or a `TEST`, but cannot independently decide the verdict;
- `normal` may materially affect confidence and tie-breaking when current evidence is otherwise comparable;
- the final recommendation must remain explainable from the current case.

## Anti-self-confirmation controls

### Blind-round firewall

The blind system and user prompts must contain no learning context. Tests inspect prompt inputs or provider call order to prove this property.

### Current-evidence supremacy

Evidence Judge receives analogies and calibration metadata after the blind round and may reject an analogy as irrelevant, outdated in structure, weakly matched, or contradicted by current evidence.

Rejected analogies are excluded from Chairman influence. The diagnostics summary records only the rejected decision id and a short reason label.

### Minority protection

When a routed expert has:

- `normal` sample strength in the current domain;
- stronger calibration than the majority experts under the deterministic ranking; and
- a blind vote that differs from the early majority,

mark that expert as a protected minority signal.

This creates a Chairman obligation to address the dissent explicitly. It does not force the Chairman to adopt the dissenting vote.

The Red Team receives the same signal so it can test whether the majority is repeating a known failure pattern.

### Anti-lock-in

A prior resolved vote must never be copied into the current verdict by rule.

There is no function equivalent to `historical_majority_vote -> verdict`. Learning context is passed to reasoning stages with explicit constraints and can be rejected by Evidence Judge.

### No low-sample authority

With fewer than 5 scored decisions for an expert in the current primary domain, that expert's calibration signal is `none`. The system may report the metric for diagnostics, but prompts must state that it has no decision influence.

## Bias alerts

V2 may emit deterministic labels when enough history exists. Alerts should remain few and auditable.

Initial alerts:

- `go_bias`: an expert or Chairman chooses `GO` at an unusually high rate relative to resolved outcomes;
- `test_bias`: persistent `TEST` preference with poor resolution accuracy;
- `overconfidence`: high mean confidence paired with elevated Brier-like error;
- `underconfidence`: good hit rate paired with persistently low confidence;
- `consensus_failure_pattern`: historical decisions with strong agreement that were later resolved against that agreement, when enough examples exist.

Bias alerts require at least `weak` sample strength. Thresholds must be explicit constants and covered by tests. If the available data cannot support an alert cleanly, v2 emits no alert.

## Stage-specific prompt exposure

### Blind experts

Receive:

- current decision question;
- current private knowledge retrieval;
- current problem context already supported by Council OS.

They receive no Decision Memory history.

### Rebuttals

Receive a compact expert-calibration section and at most the sanitized analogy metadata. They may use this to identify which disagreement deserves more scrutiny.

### Red Team

Receives:

- sample strengths;
- active bias alerts;
- protected minority signals;
- analogies.

Red Team is asked to look for repetition of a historical failure mode without assuming that similarity implies the same outcome.

### Evidence Judge

Receives learning context plus current provenance. It returns an explicit historical-context assessment:

- accepted analogy ids;
- rejected analogy ids with reason labels;
- calibration signals that are usable;
- calibration signals that are too weak;
- any conflict between historical precedent and current evidence.

### Chairman

Receives only Evidence-Judge-approved learning context plus the normal Council OS deliberation artifacts.

This keeps the Chairman from seeing rejected historical analogies as if they were valid evidence.

## Result-model changes

Extend `CouncilOSResult` with an optional, sanitized `learning_context_summary`.

Extend the Evidence Judge result or add a focused nested structure for historical-context adjudication. Prefer a dedicated `HistoricalContextAssessment` if that keeps `EvidenceAssessment` readable.

All additions must have defaults so existing callers and tests that construct `CouncilOSResult` directly remain compatible where practical.

## Decision Memory capture changes

The `decisions` table gains a sanitized JSON column such as `learning_context_json`, nullable or non-null with an empty default.

The captured payload contains only `LearningContextSummary` fields. It does not store the full learning context, analog decision rows, historical queries, or postmortems copied from earlier records.

This record exists so later analysis can answer:

- Was learning active when this decision was made?
- Which experts had weak or normal calibration signals?
- Did minority protection fire?
- Were historical analogies rejected?
- Does performance improve when normal-strength calibration is available?

Database initialization must migrate an existing v1 SQLite database safely. `CREATE TABLE IF NOT EXISTS` alone is insufficient for adding a column to an existing table; initialization must detect and add the v2 column without destroying data.

## Failure behavior

Learning is non-critical infrastructure.

If the learning store or builder fails:

- Council OS continues;
- blind memos remain valid;
- later stages receive `LearningContext(status="unavailable")` or equivalent;
- errors are reduced to fixed labels such as `learning_store_unavailable`;
- exception text, SQL, paths, ids from private sources, and credentials are not inserted into prompts or API output.

If history is too small:

- status is `insufficient_history`;
- deliberation continues normally;
- no calibration signal has decision authority.

## User isolation and privacy

Every learning query is scoped by `user_id` at the SQL layer.

Cross-user history must not influence:

- calibration;
- analogy selection;
- bias alerts;
- minority protection;
- output diagnostics.

Tests insert distinct sentinel data for two users and verify that the other user's decision ids, outcome values, queries, notes, and postmortems never appear in the builder output, LLM prompts, result model, or captured SQLite row.

The existing private-knowledge contract remains unchanged: Decision Memory v2 never stores or retrieves raw Pinecone/Drive chunks through the historical-learning path.

## API behavior

Existing Decision Memory endpoints remain backward compatible.

`GET /api/decision-memory/calibration` may be extended with learning-oriented fields if they are additive and sanitized, but a separate endpoint is not required for v2.

Decision detail responses may include the stored `learning_context_summary` for that decision.

No endpoint exposes the full internal `LearningContext` or historical analogy source records.

## Testing strategy

Implementation follows TDD.

### Storage tests

Cover:

- safe migration from a v1 database;
- user-scoped resolved-decision reads;
- cross-user isolation;
- deterministic ordering;
- no historical free-text leakage from analogy records;
- persisted learning summary contains only approved fields.

### Learning-builder tests

Cover:

- sample thresholds `0-4 -> none`, `5-14 -> weak`, `15+ -> normal`;
- deterministic calibration ordering;
- deterministic analogy ranking;
- maximum of 3 analogies;
- bias alerts only when minimum history exists;
- protected minority detection;
- no protected minority at weak/none strength;
- `insufficient_history` and `unavailable` fallbacks.

### Council OS tests

Cover:

- blind prompts contain no historical context;
- learning builder runs after blind memo generation;
- rebuttal, Red Team, Evidence Judge, and Chairman receive only their allowed learning subset;
- Chairman receives no Evidence-Judge-rejected analogy;
- current evidence can defeat historical precedent;
- protected minority is addressed but not automatically adopted;
- learning failure does not break deliberation;
- existing no-learning Council OS behavior remains valid.

### Privacy regression tests

Use unique private sentinels in:

- another user's history;
- prior postmortems;
- prior notes;
- raw memo-like text;
- simulated source identifiers.

Assert those sentinels never reach:

- blind prompts;
- later-stage prompts except fields explicitly allowed by this spec;
- `LearningContextSummary`;
- Decision Memory capture for the current decision;
- API responses that should contain diagnostics only.

### Integration and quality gates

CI should add focused Decision Memory v2 tests and lint before the existing corpus guard, full Ruff run, full pytest suite, and quality gate.

The implementation is complete only when the focused suite, full suite, privacy guard, and quality gate all pass on the PR head and again on `main` after merge.

## Rollout behavior

V2 is backward compatible and conservative by default.

A user with no resolved history gets normal Council OS behavior plus `insufficient_history` diagnostics. A user with 1-4 scored decisions gets the same decision influence. At 5 scored decisions in a domain, the signal becomes weak. At 15, it becomes normal.

The feature should be easy to disable through dependency configuration so tests and deployments can run Council OS without the learning layer.

## Explicit non-goals

V2 does not:

- modify expert routing based on historical performance;
- rewrite expert system prompts permanently;
- expose or persist raw historical Council transcripts;
- train or fine-tune an LLM;
- share learning across users;
- use historical embeddings;
- numerically multiply votes into a synthetic score;
- automatically resolve outcomes;
- treat historical success as proof that the same action is correct now.

## Acceptance criteria

Decision Memory v2 is acceptable when all of the following hold:

1. Blind expert prompts are byte-for-byte free of Decision Memory history and calibration metadata.
2. Historical learning begins only after blind memos complete.
3. Sample strengths follow the fixed `5/15` thresholds.
4. Analogies are user-scoped, deterministic, sanitized, and capped at 3.
5. Cross-user records cannot influence any learning output or prompt.
6. Evidence Judge can reject analogies before Chairman review.
7. Normal-strength minority dissent creates an explicit review obligation, never an automatic verdict change.
8. Low-sample history has no decision authority.
9. Learning infrastructure failure cannot fail the Council OS decision path.
10. Council output and Decision Memory capture expose only sanitized learning diagnostics.
11. Existing v1 databases migrate without data loss.
12. Existing Decision Memory and Council OS public API behavior stays compatible except for additive fields.
13. Focused tests, full tests, lint, privacy guards, and the project quality gate pass before merge.
14. Post-merge CI on `main` passes before the phase is considered complete.
