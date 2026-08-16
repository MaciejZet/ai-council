# Live Evidence v1

Live Evidence adds a bounded current-web evidence stage to Council OS. It runs after peer rebuttals and before Red Team, so blind expert opinions and rebuttals form without a shared web-search anchor.

## Pipeline

```text
problem profile
-> expert routing
-> Framework Selector
-> framework-aware private RAG
-> blind expert memos
-> Decision Memory learning
-> rebuttals
-> Live Evidence
-> Red Team
-> Evidence Judge
-> Chairman
```

Live Evidence is non-critical infrastructure. A missing Tavily key disables the layer. Search failure marks it unavailable and the council continues. A search with no usable results produces `no_matches`; absence of search results is not evidence that a claim is false.

## Search boundary

The default provider reuses `TavilySearchPlugin` and requests at most 2 deterministic queries with at most 5 results per query. It ignores Tavily's generated `answer` field.

Only the current decision question, public `ProblemProfile`, and selected framework ids may influence query planning. The provider does not receive private RAG chunks, private source inventory, expert memo or rebuttal prose, Decision Memory notes or postmortems, attachment text, user credentials, or API keys.

Before a query leaves the application, the provider removes obvious email addresses, bearer/API-key-like secrets, long opaque tokens, URL query strings, URL fragments, and URL user credentials. If redaction leaves no useful query, the layer is disabled for that deliberation rather than sending a generic query.

## Source cards

Each usable result becomes a bounded `LiveEvidenceSource` with:

- deterministic `evidence_id`;
- query index;
- title, capped at 180 characters;
- canonical HTTP(S) URL with credentials, query and fragment removed;
- normalized domain;
- snippet, capped at 600 characters;
- Tavily relevance score clamped to `0..1`;
- collection timestamp.

A context can hold at most 10 source cards. Results are sorted deterministically and deduplicated by canonical URL, then by normalized domain plus materially identical title.

Tavily relevance measures search relevance. It is not a credibility score.

## Untrusted external content

Titles and snippets are untrusted external data. Council prompts explicitly instruct review roles to ignore any commands or prompt-like text embedded in sources.

Red Team receives all sanitized cards and challenges relevance, independence, freshness, snippet support, syndicated reporting, and instruction-like source text.

Evidence Judge receives stable evidence ids and decides which source cards are usable. Unknown ids are removed. Rejection reasons and source-conflict labels use fixed allowlists; free-form model output collapses to safe generic labels.

Chairman receives only Evidence-Judge-accepted source cards. Rejected titles, snippets and URLs never reach the Chairman prompt. A single web source cannot independently raise confidence, and duplicated or syndicated reporting does not count as independent confirmation.

## Status and failure behavior

`LiveEvidenceContext.status` is one of:

- `ok`: at least one usable source;
- `no_matches`: search completed but no usable source survived normalization;
- `disabled`: no Tavily configuration or query was fully redacted;
- `unavailable`: provider/search infrastructure failed.

`disabled` and `no_matches` are normal non-error states. `unavailable` adds the fixed orchestration label `live_evidence_unavailable`; provider exception text is discarded.

## Decision Memory

`CouncilOSResult` exposes a sanitized `live_evidence_summary` containing only:

- status;
- query count;
- source count;
- source domains;
- accepted evidence ids;
- rejected evidence ids;
- fixed error labels.

Decision Memory stores only this summary in the additive nullable `live_evidence_json` column. It does not store live search queries, titles, URLs, snippets, Tavily answers, or raw provider errors.

## Verification

The acceptance gate for this feature is local and deterministic. GitHub Actions are not used as the merge gate. Tests cover query redaction, URL normalization, result limits, prompt-injection boundaries, blind/rebuttal firewalls, Evidence Judge gating, Chairman accepted-only exposure, Decision Memory migration and persistence, and compatibility with Framework Selector and Decision Memory v2.
