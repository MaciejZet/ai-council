# Private knowledge workflow

AI Council can use a private Google Drive library without storing the library in this public repository.

## Data boundary

The intended flow is:

```text
Google Drive (private source of truth)
        -> allowlist-only local/admin sync
        -> private Pinecone namespace
        -> AI Council retrieval
```

Keep these outside Git:

- books, PDFs and ebooks;
- book summaries and highlights;
- personal notes and synthesis documents;
- Drive exports;
- extracted text and chunks;
- embeddings and private vector payloads;
- sync state;
- Google credentials and private allowlist files.

The repository may contain code, schemas, source titles/authors used as metadata, framework identifiers, and synthetic/public-domain test data.

## 1. Create a Drive allowlist outside the repository

Use explicit file IDs and/or folder IDs. Folder access is bounded to children of the listed folders; recursive traversal stays inside those folder trees.

Example:

```json
{
  "folders": [
    {
      "id": "DRIVE_FOLDER_ID",
      "source_type": "book",
      "domains": ["strategy"],
      "experts": ["strategy"],
      "framework_tags": [],
      "recursive": true
    }
  ],
  "files": [
    {
      "id": "DRIVE_DOCUMENT_ID",
      "source_type": "synthesis",
      "domains": ["strategy", "marketing"],
      "experts": ["strategy", "marketing"],
      "framework_tags": [],
      "recursive": false
    }
  ]
}
```

Do not commit this file when it contains real Drive IDs.

Supported private source types are `book`, `summary`, `personal_note`, `synthesis`, `internal_doc`, `article`, `web`, `notion`, and `file`.

The allowlist is the authorization boundary and source of truth. When a previously synchronized file is removed from the allowlist, the next non-dry-run sync deletes that document's private vectors and removes it from local sync state. If deletion fails, state is retained so a later sync can retry instead of silently forgetting the stale vectors.

## 2. Configure read-only Drive access

Use Google Application Default Credentials or another ADC-compatible credential outside the repository. The Drive adapter requests only:

```text
https://www.googleapis.com/auth/drive.readonly
```

Example environment configuration:

```env
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/outside/repo/drive-readonly.json
PRIVATE_KNOWLEDGE_ALLOWLIST_FILE=/absolute/path/outside/repo/private-knowledge-allowlist.json
PRIVATE_KNOWLEDGE_STATE_FILE=.private_knowledge/state.json
PINECONE_API_KEY=your_private_pinecone_key
PINECONE_INDEX_NAME=ebook-library
PINECONE_PRIVATE_NAMESPACE=private-library
OPENAI_API_KEY=your_embedding_provider_key
PRIVATE_KNOWLEDGE_DEBUG_TITLES=false
```

`.private_knowledge/` is ignored by Git. Keep credential files outside the repository entirely.

## 3. Preview the sync

```bash
uv run python scripts/sync_private_knowledge.py --dry-run
```

Dry-run mode enumerates allowlisted records and reports counts. It does not download source content, create embeddings, prune removed sources, write sync state, or mutate Pinecone.

## 4. Run the sync

```bash
uv run python scripts/sync_private_knowledge.py
```

For each new or changed source, the sync:

1. reads the allowlisted Drive record;
2. calculates a stable content hash;
3. extracts text in memory or, for PDFs, inside a temporary OS directory;
4. chunks and embeds the text;
5. writes the new vector version to `PINECONE_PRIVATE_NAMESPACE`;
6. deletes older vector versions only after the new upsert succeeds;
7. updates local sync state atomically.

If a multi-batch upsert fails after one or more batches were written, the sync attempts to remove only the incomplete new content version and leaves the previous version intact. If cleanup itself is unavailable, the sync still reports failure and does not advance local state.

Unchanged sources are skipped before their content is downloaded. Sources no longer present in the allowlist are pruned from the private namespace before changed sources are processed.

## State and logs

Sync state contains technical identifiers, remote versions, content hashes, timestamps, and chunk counts. It does not contain source text or source titles.

Normal logs contain technical document IDs and error types. They do not contain retrieved passages or source titles. `PRIVATE_KNOWLEDGE_DEBUG_TITLES=true` explicitly enables titles for local diagnostics; do not use that setting in public CI logs.

## Runtime retrieval

Set `PINECONE_PRIVATE_NAMESPACE` in the Council runtime to query the private namespace. Retrieval supports filters for source type, domain, and expert. Internal retrieval objects retain provenance such as document ID, source type, chunk index, and relevance score.

If the embedding provider or Pinecone is unavailable, Council continues in degraded mode unless `kb_only` behavior is requested. The deliberation carries `knowledge_status="unavailable"`; it must not imply that private sources were verified.

## Repository safeguards

The repository guard rejects tracked/staged files under private-corpus working paths and rejects common ebook formats:

```bash
uv run python scripts/check_private_corpus.py
```

CI runs the tracked-file form automatically:

```bash
uv run python scripts/check_private_corpus.py --tracked-only
```

The guard deliberately does not reject all PDFs because public documentation and public-domain test fixtures may legitimately be committed.

Before opening a public PR, verify that you have not pasted private source content, credentials, real Drive IDs, sync-state contents, or retrieved passages into commits, tests, PR descriptions, or issue attachments.
