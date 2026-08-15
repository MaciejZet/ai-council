from __future__ import annotations

import hashlib
from typing import Any

from src.knowledge.ingest import chunk_text, get_embeddings, get_pinecone_index
from src.knowledge.private_models import PrivateSourceMetadata


def content_sha256(content: bytes | str) -> str:
    raw = content.encode() if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def stable_doc_id(source_kind: str, source_id: str) -> str:
    raw = f"{source_kind}:{source_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:28]


def generate_chunk_id(doc_id: str, content_hash: str, chunk_index: int) -> str:
    raw = f"{doc_id}:{content_hash}:{chunk_index}".encode()
    return hashlib.sha256(raw).hexdigest()


def _with_namespace(namespace: str | None) -> dict[str, str]:
    return {"namespace": namespace} if namespace is not None else {}


def upsert_text_document(
    text: str,
    metadata: PrivateSourceMetadata,
    *,
    namespace: str | None = None,
    batch_size: int = 100,
) -> dict[str, Any]:
    if not text.strip():
        return {"status": "error", "message": "Empty source text", "chunks_count": 0}

    chunks = chunk_text(text)
    chunk_texts = [chunk["text"] for chunk in chunks]
    embeddings = get_embeddings(chunk_texts)
    if len(embeddings) != len(chunks):
        raise ValueError("Embedding count does not match chunk count")

    index = get_pinecone_index()
    vectors: list[dict[str, Any]] = []
    category = metadata.domains[0] if metadata.domains else "ogólne"

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        chunk_index = int(chunk["chunk_index"])
        vector_metadata: dict[str, Any] = {
            "text": chunk["text"],
            "title": metadata.title[:500],
            "category": category,
            "language": metadata.language,
            "source_type": metadata.source_type,
            "domains": metadata.domains,
            "experts": metadata.experts,
            "framework_tags": metadata.framework_tags,
            "chunk_index": chunk_index,
            "total_chunks": len(chunks),
            "doc_id": metadata.doc_id,
            "drive_file_id": metadata.drive_file_id,
            "content_hash": metadata.content_hash,
            "embedding_version": "v2",
        }
        if metadata.modified_time:
            vector_metadata["modified_time"] = metadata.modified_time

        vectors.append(
            {
                "id": generate_chunk_id(metadata.doc_id, metadata.content_hash, chunk_index),
                "values": embedding,
                "metadata": vector_metadata,
            }
        )

    namespace_kwargs = _with_namespace(namespace)
    for offset in range(0, len(vectors), batch_size):
        batch = vectors[offset : offset + batch_size]
        index.upsert(vectors=batch, **namespace_kwargs)

    stale_filter = {
        "$and": [
            {"doc_id": {"$eq": metadata.doc_id}},
            {"content_hash": {"$ne": metadata.content_hash}},
        ]
    }
    index.delete(filter=stale_filter, **namespace_kwargs)

    return {
        "status": "success",
        "title": metadata.title,
        "chunks_count": len(chunks),
        "characters_count": len(text),
        "doc_id": metadata.doc_id,
        "content_hash": metadata.content_hash,
    }
