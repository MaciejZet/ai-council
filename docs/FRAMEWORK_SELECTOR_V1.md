# Framework Selector v1

Framework Selector gives Council OS a small, deterministic set of analytical lenses before expert retrieval and the blind memo round. A framework organizes questions. It does not establish facts about the current case.

## Decision flow

```text
problem profile
-> expert routing
-> framework selection
-> framework-aware private RAG
-> blind expert memos
-> Decision Memory learning
-> rebuttals
-> Red Team
-> Evidence Judge
-> Chairman
```

The selector uses only the current question, `ProblemProfile`, and routed expert ids. It never reads Decision Memory history, expert memos, outcomes, Red Team output, Chairman output, or private RAG chunks.

## Selection policy

Policy version: `framework-selector-v1`.

A framework needs a score of at least `5`. Council OS selects at most `3` frameworks for one decision and assigns at most `2` to any routed expert. Ties are deterministic: higher score, then registry order, then framework id.

The initial registry contains:

- `strategic_choice`
- `competitive_advantage`
- `positioning_category`
- `value_equation`
- `customer_job_evidence`
- `growth_loop`
- `operating_constraint`
- `reversibility_experiment`

The public registry contains short original descriptions, generic diagnostic questions, and public metadata tags. It does not contain book passages or private summaries.

## Framework-aware retrieval

For an expert with assigned framework lenses, retrieval first uses the normal domain/expert filters plus the combined `framework_tags` from those lenses.

If that query returns `ok`, Council OS uses it directly. If it returns `no_matches`, Council OS retries once with the existing domain/expert filters and no framework tag filter. If the framework-aware query is `unavailable`, Council OS preserves that state and does not issue a second backend call.

The retrieval diagnostic is one of:

- `framework_match`
- `framework_no_match_fallback_ok`
- `framework_no_match_fallback_no_matches`
- `framework_unavailable`
- `framework_disabled`
- `base_retrieval`

These labels are safe diagnostics. `framework_disabled` means knowledge use was intentionally disabled, so no backend retry is attempted. Raw retrieved text is not copied into the framework summary.

## Epistemic rule: `[FMW]`

Blind experts see only their assigned framework cards and the current private evidence. The prompt states that frameworks are analysis lenses and may be rejected when they do not fit the case.

A material claim that comes mainly from a framework must use `[FMW]`. `[F]` is reserved for a factual claim supported independently by the supplied evidence.

Red Team checks whether a lens is applicable, whether shared lenses caused correlated reasoning, and whether a framework was treated as empirical evidence.

Evidence Judge receives stable claim references in the form `<expert_id>:<zero-based claim_index>`. It can flag a framework-derived statement that was mislabeled as `[F]` and can reject a framework for final synthesis. Unknown claim references and unknown framework ids are discarded during sanitization.

Chairman receives only the framework set left active after Evidence Judge review. A rejected framework cannot support the final recommendation. Agreement produced by a shared framework is not independent confirmation, and framework use cannot independently raise confidence.

## Decision Memory

`CouncilOSResult` exposes a sanitized `framework_selection_summary`. Decision Memory stores that summary in the additive `framework_selection_json` column.

The summary records:

- policy version
- selected framework ids
- expert assignments
- deterministic reason labels
- per-expert retrieval diagnostics
- framework ids rejected by Evidence Judge
- fixed selector error labels

It does not store retrieved passages, book text, source paths, Drive ids, postmortems, or notes in the framework field.

Existing Decision Memory databases migrate by adding the nullable column. Existing rows are preserved.

## Failure behavior

Framework selection is non-critical. If the selector raises, Council OS proceeds with an empty selection and records `framework_selector_unavailable`. Normal expert/domain retrieval still runs.

Knowledge-backend outages keep the existing `unavailable` semantics. Council OS never replaces missing evidence with a framework rule.

## Verification policy

This feature is accepted from local tests and local quality checks. GitHub Actions are not used as the acceptance gate for this phase, and workflow files are not modified by the feature.
