# Decision Memory v1 Design

## Goal

Add persistent decision memory to Council OS so completed deliberations can be revisited, resolved against real outcomes, and used to measure calibration over time.

Decision Memory v1 records a sanitized snapshot of each authenticated `council_os` run, lets the user attach an outcome/postmortem later, and computes simple calibration metrics for domain experts and the Chairman. It does not feed historical decisions back into future prompts yet.

## Scope

The v1 flow is:

```text
council_os run
  -> sanitized decision snapshot
  -> user-scoped persistence
  -> later outcome / postmortem
  -> calibration aggregation
```

This phase covers storage, API contracts, authenticated automatic capture, outcome updates, and read-only calibration reports.

Historical-decision retrieval, automatic learning loops, prompt personalization from prior outcomes, scheduled follow-ups, and model fine-tuning remain out of scope.

## Design choices

### Separate decision database

Use a dedicated SQLite module and database:

- module: `src/storage/decision_memory.py`
- default database: `data/ai_council_decisions.db`

The repository already has `user_db.py` for users/projects and JSON-backed session history. Decision Memory needs relational filtering and aggregation across outcomes, experts, domains, and confidence values. Keeping it separate avoids turning `user_db.py` into a catch-all storage module and avoids doing calibration scans over JSON session files.

The database path must be injectable for tests. Production uses the default path under `data/`, which is already excluded from Git.

### User ownership

Every persisted decision belongs to the authenticated user resolved from the existing `X-User-Session` header through `user_store.validate_session`.

Automatic capture is best-effort:

- valid user session: persist the `council_os` result;
- missing or invalid session: run Council OS normally, but do not persist;
- persistence failure: do not fail the streamed business decision. Emit/log a sanitized persistence error without private source text.

All read and update endpoints require a valid user session and scope every query by `user_id`.

### Persistence boundary

`CouncilOS` stays a pure decision engine. It does not import storage code and does not know about users.

Persistence sits at the Council Mode/API boundary. `CouncilOSMode` may receive an optional completion callback or equivalent narrow hook. The API supplies a callback only when a valid authenticated user exists.

This keeps orchestration testable and prevents storage failures from affecting reasoning behavior.

## Data model

Decision Memory stores deliberation structure, not private RAG content.

### `decisions`

One row per captured Council OS run.

Fields:

- `id` TEXT primary key
- `user_id` TEXT not null
- `created_at` TEXT not null
- `updated_at` TEXT not null
- `query` TEXT not null
- `primary_domain` TEXT not null
- `secondary_domains_json` TEXT not null
- `decision_kind` TEXT not null
- `reversibility` TEXT not null
- `risk_level` TEXT not null
- `routed_experts_json` TEXT not null
- `verdict` TEXT not null
- `verdict_confidence` REAL not null
- `recommendation` TEXT not null
- `consensus` TEXT not null
- `key_disagreement` TEXT not null
- `minority_report` TEXT not null
- `assumptions_json` TEXT not null
- `evidence_gaps_json` TEXT not null
- `what_would_change_decision_json` TEXT not null
- `next_experiment_json` TEXT nullable
- `knowledge_status_json` TEXT not null
- `orchestration_errors_json` TEXT not null

Indexes:

- `(user_id, created_at DESC)`
- `(user_id, primary_domain)`
- `(user_id, verdict)`

### `decision_expert_votes`

One row per expert memo in the captured run.

Fields:

- `decision_id` TEXT not null
- `expert_id` TEXT not null
- `blind_vote` TEXT not null
- `blind_confidence` REAL not null
- `revised_vote` TEXT nullable
- `revised_confidence` REAL nullable
- `knowledge_status` TEXT not null
- primary key `(decision_id, expert_id)`

The table intentionally does not persist memo prose, claims, retrieved passages, source inventory, or book-derived text. Calibration needs the vote, confidence, role, and outcome, not the full private reasoning transcript.

### `decision_outcomes`

At most one current outcome per decision.

Fields:

- `decision_id` TEXT primary key
- `user_id` TEXT not null
- `updated_at` TEXT not null
- `status` TEXT not null: `success | failure | mixed | inconclusive`
- `resolved_vote` TEXT nullable: `GO | NO-GO | TEST | DEFER`
- `experiment_result` TEXT nullable
- `postmortem` TEXT nullable
- `notes` TEXT nullable

`resolved_vote` is the decision direction that hindsight supports. It is nullable because many outcomes are informative without yielding one clean counterfactual answer.

## Sanitization contract

Decision Memory must never persist:

- raw RAG chunk text;
- source excerpts;
- source inventory objects;
- Drive IDs or file-system paths;
- credentials or API keys;
- full blind memo recommendation prose;
- full rebuttal prose;
- book text or book summaries.

It may persist public or user-authored decision metadata already present in the structured Council OS result, including the original business question, role ids, votes, confidence, verdict fields, assumptions, evidence-gap labels, and next-experiment fields.

The storage API accepts a `CouncilOSResult` or a dedicated sanitized snapshot model and constructs SQL values explicitly. It must not call `model_dump()` and blindly persist the entire result.

## Capture behavior

### Authenticated `council_os`

For `/api/council/mode/stream?mode=council_os...`:

1. Resolve `X-User-Session` before creating the stream.
2. Do not reject the request if the header is absent or invalid; existing anonymous behavior remains supported.
3. When authenticated, supply a completion hook to `CouncilOSMode`.
4. After `CouncilOS.deliberate()` returns a typed result, invoke the hook with the query and result.
5. Persist before the final `complete` event where practical, but never expose database internals in SSE.
6. Add `decision_id` to the `council_os_result` event only when persistence succeeds.

The structured `CouncilOSResult` Pydantic model does not gain storage-specific fields.

### Idempotency

One mode execution should create at most one decision row. The completion callback is invoked once by `CouncilOSMode` after deliberation. No automatic deduplication by query text is attempted because repeated runs may intentionally represent distinct decisions at different times.

## Outcome and postmortem API

All endpoints require `X-User-Session`.

### List decisions

`GET /api/decision-memory`

Query parameters:

- `limit` default 50, bounded to 1–200;
- optional `primary_domain`;
- optional `verdict`;
- optional `outcome_status`.

Response items contain compact decision metadata, verdict, outcome summary, and whether an outcome exists. They do not include private knowledge or full Council transcripts.

### Get one decision

`GET /api/decision-memory/{decision_id}`

Returns the sanitized decision snapshot, expert vote rows, and outcome if present.

A decision owned by another user returns 404, not 403, to avoid leaking record existence.

### Write or replace outcome

`PUT /api/decision-memory/{decision_id}/outcome`

Request schema:

```json
{
  "status": "success | failure | mixed | inconclusive",
  "resolved_vote": "GO | NO-GO | TEST | DEFER | null",
  "experiment_result": "string | null",
  "postmortem": "string | null",
  "notes": "string | null"
}
```

Validation limits cap free-text fields to prevent accidental large-document storage. `resolved_vote` is optional.

The operation is an upsert so the user can revise the postmortem as evidence matures.

## Calibration

`GET /api/decision-memory/calibration`

The report is computed from decisions that have an outcome with non-null `resolved_vote`.

For each expert and for the Chairman, return:

- `sample_size`;
- `correct_count`;
- `hit_rate`;
- `mean_confidence`;
- `brier_like_error`;
- optional breakdown by `primary_domain`.

### Correctness

For a domain expert:

```text
correct = blind_vote == resolved_vote
```

For the Chairman:

```text
correct = verdict == resolved_vote
```

The first calibration version uses blind votes, not revised votes, because the blind vote is the cleanest signal of each expert's independent judgment. Revised votes remain stored for analysis but do not affect the headline score.

### Brier-like error

For each scored prediction:

```text
correctness = 1.0 if predicted_vote == resolved_vote else 0.0
error = (confidence - correctness) ** 2
```

The aggregate is the arithmetic mean of `error`.

This is deliberately labeled `brier_like_error`, not a multiclass Brier score. The stored confidence is confidence in the chosen class only, not a probability distribution across all four verdicts.

### Outcome statuses

`success`, `failure`, `mixed`, and `inconclusive` describe what happened operationally. They do not determine calibration correctness by themselves. Calibration includes a row only when `resolved_vote` is present.

## Error handling

- Storage initialization uses `CREATE TABLE IF NOT EXISTS` and indexes, guarded by a module-level lock like existing SQLite storage.
- Malformed JSON in stored rows is treated as a storage error; API returns a normalized 500 rather than silently inventing defaults.
- Cross-user reads/updates return 404.
- Invalid verdict/outcome enums return 422 through Pydantic validation.
- Automatic capture failures are logged without query text, memo text, retrieved text, titles, or source ids. The Council OS stream still completes.
- Calibration over zero scored decisions returns an empty list and totals with `sample_size=0`.

## API integration

Add request/response models in `main.py` only where needed, but keep database logic in `src/storage/decision_memory.py`.

Add `"/api/decision-memory"` to the core API contract path set so validation/rate-limit/internal errors follow the existing normalized response envelope where practical.

Council mode routing remains backward compatible for all existing modes.

## Testing

Tests use temporary SQLite files and synthetic Council OS results only.

Required tests:

1. Schema initializes in a temporary database.
2. Capturing a synthetic Council OS result stores only sanitized fields.
3. Raw chunk/source sentinel text cannot appear anywhere in persisted decision rows.
4. Blind and revised expert votes are captured correctly.
5. Two users cannot read or update each other's decisions.
6. List filters by domain, verdict, and outcome status.
7. Outcome upsert can be revised.
8. Outcome field validation rejects invalid enums and oversized text.
9. Calibration uses blind expert vote and Chairman verdict.
10. Calibration excludes decisions without `resolved_vote`.
11. Hit rate, mean confidence, and `brier_like_error` are deterministic on a small fixture.
12. Domain breakdown is scoped correctly.
13. Authenticated `council_os` stream persists once and returns `decision_id`.
14. Anonymous or invalid-session `council_os` stream still succeeds and creates no decision.
15. Storage failure during automatic capture does not fail the Council OS stream and does not leak sensitive content.
16. Existing Council OS tests, full repository tests, Ruff checks, corpus guard, and quality gate stay green.

## Acceptance criteria

Decision Memory v1 is complete when an authenticated synthetic Council OS run can be captured, fetched by its owner, resolved with an outcome, and reflected in a deterministic calibration report, while:

- anonymous Council OS remains backward compatible;
- another user cannot access the record;
- raw private retrieval data is absent from the decision database and API payloads;
- history is not yet injected into future Council prompts;
- the full repository CI remains green.
