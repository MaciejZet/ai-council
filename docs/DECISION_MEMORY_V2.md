# Decision Memory v2

Decision Memory v2 lets Council OS use resolved historical decisions as a controlled calibration signal. Historical data enters the deliberation only after all blind expert memos have completed.

## Decision flow

```text
problem profile + routing
-> current private RAG
-> blind expert memos
-> user-scoped Decision Memory learning context
-> rebuttals
-> Red Team
-> Evidence Judge
-> Chairman
-> sanitized learning diagnostics
```

The blind round never receives prior decisions, outcomes, calibration metrics, prior verdicts, postmortems, notes, or historical queries.

## Sample gates

Historical calibration uses fixed sample-strength thresholds in the current primary domain:

- `0-4` scored decisions: `none`; no decision authority;
- `5-14`: `weak`; may trigger scrutiny or support a reversible test;
- `15+`: `normal`; may affect confidence or tie-breaking when current evidence is otherwise comparable.

A scored decision has a non-null hindsight `resolved_vote`.

## Analog decisions

The learning layer selects at most 3 user-owned resolved decisions using deterministic metadata similarity:

- primary domain: +4;
- decision kind: +3;
- reversibility: +2;
- risk level: +2;
- matching secondary domains: +1 each, capped at 2.

Historical queries, memo prose, recommendations, postmortems, notes, RAG text, Drive ids, and source inventory are excluded from analog payloads.

## Evidence Judge gate

Rebuttals and Red Team can inspect sanitized calibration and analog metadata. Evidence Judge then decides which analog ids and expert calibration signals are usable for the final stage.

Chairman receives only the approved subset. Rejected analogies do not appear in the Chairman's historical-context payload. Bias alerts are derived only from expert signals approved for the final stage.

Current evidence always has priority over historical precedent.

## Minority protection

A dissenting expert becomes a protected minority signal only when:

1. its domain sample strength is `normal`;
2. its historical calibration is stronger than the majority experts under deterministic ranking;
3. its blind vote differs from the current majority.

Red Team and Chairman must address that dissent. The mechanism never forces the final verdict to follow it.

## Privacy and user isolation

All Decision Memory learning reads are scoped by `user_id` in SQLite. Historical learning never shares records across users.

The persistent v2 addition is a sanitized `learning_context_json` summary on the current decision. Existing v1 databases are migrated with an additive column and no destructive rewrite.

The stored summary contains diagnostic metadata such as learning status, accepted-analogy count, active sample strengths, approved bias labels, protected minority ids, and rejected analogy id/reason labels. It does not contain the full learning context or historical free text.

## Failure behavior

Learning is non-critical infrastructure. If the learning store or provider fails, Council OS continues using the current case and records a fixed sanitized error label. Exception text is not exposed in the result.

Anonymous or invalid-session Council OS requests run with historical learning disabled. Request-scoped state is reset after every Council OS request.

## Verification policy for this phase

This phase is verified locally, not through GitHub Actions. The repository workflow files are intentionally unchanged. Focused Decision Memory v2 tests, reconstructed v1 Decision Memory regressions, and Python bytecode compilation are used as the current acceptance evidence.
