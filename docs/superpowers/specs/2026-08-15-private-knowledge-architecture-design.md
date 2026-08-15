# Private knowledge architecture for AI Council

Date: 2026-08-15
Status: approved direction, design for implementation planning

## Goal

AI Council remains a public codebase while using a private, user-owned knowledge corpus sourced from Google Drive. Book PDFs, summaries, notes, extracted text, chunks and embeddings must never be committed to the public repository.

The public repository contains the engine: agent definitions, routing, retrieval interfaces, metadata schemas, debate protocol, tests with synthetic fixtures and deployment code. Private knowledge stays in Google Drive and a private Pinecone index or namespace.

## Decision

Use this data flow:

```text
Google Drive (private source of truth)
        |
        v
Private ingestion/sync process
        |
        | extract -> normalize -> chunk -> embed
        v
Pinecone (private retrieval store)
        |
        v
AI Council runtime
        |
        v
Per-expert retrieval -> debate -> red team -> evidence judge -> chairman
```

The Council runtime does not require book files to exist inside the repository. It queries Pinecone using credentials supplied at runtime through environment variables or a secret manager.

## Approaches considered

### A. Keep books and summaries in the repository

Rejected. This is operationally convenient but incompatible with a public repository containing copyrighted or otherwise private source material. It also creates a high risk of accidental propagation through forks, Git history, CI artifacts and caches.

### B. Google Drive -> private ingestion -> Pinecone -> Council

Chosen. Drive remains the human-managed source library. A private ingestion process converts approved documents into retrieval records. The public Council code only consumes the retrieval API.

Advantages:

- no raw corpus in Git;
- one private source of truth for books and notes;
- current Pinecone-based RAG code can be extended rather than replaced;
- the runtime can retrieve only the context needed by each expert;
- updates to the library do not require code commits.

Trade-off: ingestion requires credentials and a sync process outside the public data plane.

### C. Query Google Drive directly during each deliberation

Deferred. This removes Pinecone ingestion but makes deliberations slower, couples the runtime to Drive permissions and complicates ranking, chunking and filtering. It may later be useful for fresh internal documents, but it should not be the primary path for the book library.

## Public/private boundary

### Allowed in the public repository

- application and ingestion code;
- agent and expert definitions;
- debate and routing logic;
- metadata schemas;
- category and framework identifiers written in original wording;
- book title and author metadata when useful for routing;
- configuration examples containing placeholders only;
- synthetic or public-domain test fixtures;
- hashes, IDs and interfaces that do not expose source text.

### Must remain private

- PDFs and ebooks;
- book summaries;
- highlights and annotations;
- personal notes derived from books;
- extracted source text;
- retrieval chunks containing source text;
- embeddings and vector-store payloads derived from the private corpus;
- local exports of Drive documents;
- ingestion caches containing source text;
- logs that contain retrieved book passages;
- test fixtures copied from the private corpus.

The implementation should treat the private corpus as sensitive data even where copyright is not the only concern.

## Source model

Google Drive is the source of truth for the private library. The ingestion layer should operate only on explicitly approved folders or file IDs rather than crawling the entire Drive account.

Each ingested document receives metadata similar to:

```json
{
  "doc_id": "stable-private-id",
  "title": "source title",
  "author": "source author",
  "source_type": "book|summary|personal_note|synthesis|internal_doc",
  "domains": ["strategy", "pricing"],
  "experts": ["strategy", "monetization"],
  "framework_tags": ["category_strategy"],
  "language": "pl|en",
  "drive_file_id": "private-reference",
  "content_hash": "sha256...",
  "chunk_index": 12,
  "page_or_section": "optional locator",
  "ingested_at": "timestamp"
}
```

`title`, `author` and tags may be used for retrieval provenance. The source text itself stays only in the private retrieval store.

## Ingestion and synchronization

For v1, ingestion should run as an explicit local/admin command rather than inside normal Council requests. This keeps Drive credentials out of the public runtime and makes the security boundary easier to audit.

The sync process should:

1. read an allowlist of Drive folders or file IDs from private configuration;
2. list eligible files;
3. compare stable file IDs and content hashes with the last ingestion state;
4. fetch only new or changed files;
5. extract text in memory or into a local ignored working directory;
6. normalize and chunk text;
7. attach metadata and provenance;
8. create embeddings;
9. upsert records to a private Pinecone namespace;
10. remove or tombstone Pinecone records for deleted sources when requested;
11. write an ingestion report that contains counts and IDs, but no source text.

The sync state must be local/private. It must not require committing an inventory of the user's library.

## Retrieval architecture

The existing retriever should evolve from broad category search to expert-aware retrieval.

A request should be classified before retrieval:

```text
question
  -> problem classifier
  -> expert router
  -> framework selector
  -> per-expert retrieval query
  -> bounded context bundle
```

Each expert receives its own context bundle. A pricing expert should not receive the same corpus slice as a creative or red-team expert unless the retrieved evidence overlaps naturally.

Retrieval records returned internally should retain provenance:

```text
source title
source type
relevance score
chunk locator
framework tags
retrieved text
```

The model may reason from retrieved text, while the final Council output should normally cite source titles or user-approved provenance rather than reproduce long passages.

## Expert knowledge model

Books are evidence sources and framework sources, not agent personas. An expert can combine multiple schools of thought and must be allowed to report conflicts between them.

Planned expert families:

- Strategy and competitive advantage
- Marketing and positioning
- Sales and negotiation
- Offer and monetization
- Growth and acquisition
- Product and customer
- Operator and execution
- Creative and behavioral psychology
- Red team
- Evidence judge
- Chairman / decision architect

The expert registry belongs in the public repo. The actual book-derived material used by an expert is retrieved privately at runtime.

## Evidence handling

Every retrieved claim should keep enough provenance for the Evidence Judge to distinguish:

- current business fact;
- personal note;
- book or summary;
- synthesis document;
- live external source;
- model inference.

The Council should not treat agreement between agents as evidence. Consensus and evidentiary support are separate signals.

For decision-oriented outputs, the Chairman should return one of:

- GO
- NO-GO
- TEST
- DEFER

and include confidence, key assumptions, strongest dissent, evidence gaps and the smallest useful next experiment when the verdict is TEST.

## Repository safeguards

The current repository already ignores `books_pdf/`. The implementation should broaden this into a defense-in-depth policy.

Recommended ignored paths/patterns:

```text
books_pdf/
private_knowledge/
knowledge_private/
drive_exports/
ingestion_cache/
*.epub
*.mobi
*.azw
*.azw3
```

PDFs should not be ignored globally because the project may legitimately contain public documentation or test assets. Private PDF storage must live only under explicit ignored directories.

Add a repository safety check that fails when staged files appear to contain private corpus material. The check should inspect paths and file types first, then optionally scan text files for high-risk markers. It must not upload files to a third-party scanning service.

CI should use synthetic knowledge fixtures. CI must not require Drive or Pinecone production credentials.

## Logging, cache and observability

Retrieved private text must not be written to normal application logs. Logs may record:

- document ID;
- source title if acceptable;
- retrieval score;
- chunk number;
- token counts;
- timing and error metadata.

Redis or other caches can contain model responses that indirectly reflect private context. Production deployments should therefore treat response caches as private application data, give them an explicit TTL and never serialize them into repository artifacts.

## Secrets

The public repository may contain `.env.example` with placeholder names only. Real values remain outside Git.

Expected private configuration includes:

```text
GOOGLE_DRIVE_* credentials or delegated auth
PINECONE_API_KEY
PINECONE_INDEX_NAME
PINECONE_NAMESPACE
OPENAI_API_KEY or another embedding provider key
PRIVATE_KNOWLEDGE_ALLOWLIST
```

Where feasible, use a separate Pinecone namespace or index for the private library rather than mixing it with public demo data.

## Failure behavior

If private knowledge is unavailable, the Council should degrade explicitly:

- deliberation can continue without book context if the selected mode allows it;
- the result must state that private knowledge retrieval was unavailable;
- the system must not invent citations or imply that a book was consulted;
- ingestion failures must not delete previously valid vectors unless the operation is explicitly a delete/tombstone action.

## Testing

Implementation should cover at least these cases:

1. the app starts without Drive credentials;
2. deliberation works with knowledge retrieval disabled;
3. ingestion refuses files outside the allowlist;
4. changed Drive content is re-ingested using content hashes;
5. unchanged documents are skipped;
6. per-expert retrieval applies metadata filters correctly;
7. retrieved text is absent from normal logs;
8. CI uses only synthetic fixtures;
9. repository safety checks reject files placed under known private-corpus paths if they are staged despite ignore overrides;
10. a missing Pinecone connection produces an explicit degraded-mode result rather than a fabricated source claim.

## Implementation scope for the first iteration

The first implementation should stay narrow:

1. formalize the private/public boundary in code and documentation;
2. strengthen `.gitignore` and add a local repository safety check;
3. add a Drive allowlist-based ingestion command;
4. add stable source metadata and content hashing;
5. keep source text out of logs;
6. add a dedicated private Pinecone namespace configuration;
7. extend retrieval so expert/domain metadata can filter results;
8. add tests for isolation, degraded mode and retrieval metadata.

Dynamic expert routing, Evidence Judge upgrades and the full Council debate redesign should be the next design/implementation slice after the private knowledge boundary is working and tested.

## Success criteria

The design is successful when all of the following are true:

- a fresh clone of the public repository contains no private corpus material;
- a contributor can run the test suite without access to the user's Drive or Pinecone;
- an authorized local/admin sync can ingest approved Drive sources into the private vector store;
- Council retrieval can use that private knowledge without persisting source text to Git or normal logs;
- disabling or losing the private store causes an explicit degraded mode, not a misleading answer;
- adding or updating a book in Drive requires no repository commit.
