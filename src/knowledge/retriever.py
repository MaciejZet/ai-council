"""
Knowledge Retriever
====================
Odpytuje Pinecone i zwraca relevantny kontekst wraz z bezpieczną proweniencją.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv

from src.knowledge.errors import KnowledgeConfigError, KnowledgeEmbeddingError, KnowledgeFilterError
from src.knowledge.private_models import KnowledgeRetrievalResult
from src.utils.logger import setup_logger

load_dotenv()

_retriever_log = setup_logger("ai_council.knowledge")


def _keyword_overlap_score(query: str, text: str) -> float:
    """Simple token overlap ratio for hybrid reranking."""
    if not query.strip() or not text.strip():
        return 0.0
    q_tokens = {token.lower() for token in query.replace("/", " ").split() if len(token) > 2}
    if not q_tokens:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for token in q_tokens if token in text_lower)
    return hits / max(len(q_tokens), 1)


def _validate_metadata_filters(category: Optional[str], source_type: Optional[str]) -> None:
    allowed_categories = set(get_all_categories())
    if category is not None and category not in allowed_categories:
        raise KnowledgeFilterError(
            f"Invalid category {category!r}. Allowed: {sorted(allowed_categories)}"
        )
    allowed_source = {
        "book",
        "summary",
        "personal_note",
        "synthesis",
        "internal_doc",
        "article",
        "ogólne",
        "web",
        "notion",
        "file",
    }
    if source_type is not None and source_type not in allowed_source:
        raise KnowledgeFilterError(
            f"Invalid source_type {source_type!r}. Allowed: {sorted(allowed_source)}"
        )


def get_pinecone_index():
    """Zwraca połączony index Pinecone."""
    key = os.getenv("PINECONE_API_KEY")
    if not key or key.strip() in ("", "dummy-key", "your_pinecone_key"):
        raise KnowledgeConfigError("PINECONE_API_KEY is missing or not configured")
    from pinecone import Pinecone

    pc = Pinecone(api_key=key)
    index_name = os.getenv("PINECONE_INDEX_NAME", "ebook-library")
    return pc.Index(index_name)


def get_query_embedding(query: str) -> list[float]:
    """Generuje embedding dla zapytania."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip() in ("", "dummy-key"):
        raise KnowledgeConfigError("OPENAI_API_KEY is missing or not configured for embeddings")
    from openai import OpenAI

    client = OpenAI(api_key=key)
    try:
        response = client.embeddings.create(model="text-embedding-3-small", input=query[:8000])
    except Exception as exc:
        raise KnowledgeEmbeddingError(f"Embedding request failed: {exc}") from exc
    return response.data[0].embedding


def _build_filter(
    *,
    category: str | None,
    source_type: str | None,
    domains: list[str] | None,
    experts: list[str] | None,
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if source_type:
        clauses.append({"source_type": {"$eq": source_type}})
    if category:
        clauses.append({"category": {"$eq": category}})
    if domains:
        clauses.append({"domains": {"$in": domains}})
    if experts:
        clauses.append({"experts": {"$in": experts}})
    if len(clauses) > 1:
        return {"$and": clauses}
    if clauses:
        return clauses[0]
    return None


def query_knowledge_result(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    source_type: str | None = None,
    domains: list[str] | None = None,
    experts: list[str] | None = None,
    min_score: float = 0.3,
    hybrid: bool = False,
    namespace: str | None = None,
) -> KnowledgeRetrievalResult:
    """Query knowledge with explicit availability status and provenance metadata."""
    if not query or not query.strip():
        return KnowledgeRetrievalResult(status="no_matches")

    _validate_metadata_filters(category, source_type)

    try:
        query_embedding = get_query_embedding(query)
    except KnowledgeConfigError:
        _retriever_log.warning("Knowledge retrieval unavailable: embedding configuration missing")
        return KnowledgeRetrievalResult(
            status="unavailable",
            error_code="embedding_config_missing",
        )
    except KnowledgeEmbeddingError:
        _retriever_log.warning("Knowledge retrieval unavailable: embedding request failed")
        return KnowledgeRetrievalResult(status="unavailable", error_code="embedding_failed")

    filter_dict = _build_filter(
        category=category,
        source_type=source_type,
        domains=domains,
        experts=experts,
    )

    try:
        index = get_pinecone_index()
    except KnowledgeConfigError:
        _retriever_log.warning("Knowledge retrieval unavailable: Pinecone configuration missing")
        return KnowledgeRetrievalResult(
            status="unavailable",
            error_code="pinecone_config_missing",
        )

    fetch_k = top_k * 3 if hybrid else top_k
    query_kwargs: dict[str, Any] = {
        "vector": query_embedding,
        "top_k": max(fetch_k, top_k),
        "include_metadata": True,
        "filter": filter_dict,
    }
    if namespace is not None:
        query_kwargs["namespace"] = namespace

    try:
        results = index.query(**query_kwargs)
    except Exception as exc:
        _retriever_log.warning(
            "Knowledge retrieval unavailable: Pinecone query error_type=%s",
            type(exc).__name__,
        )
        return KnowledgeRetrievalResult(status="unavailable", error_code="pinecone_query_failed")

    relevant_chunks: list[dict[str, Any]] = []
    for match in results.matches:
        if match.score is None or match.score < min_score:
            continue
        meta = match.metadata or {}
        vector_score = float(match.score)
        text = meta.get("text", "")
        keyword_score = _keyword_overlap_score(query, text) if hybrid else 0.0
        combined = 0.65 * vector_score + 0.35 * keyword_score if hybrid else vector_score
        relevant_chunks.append(
            {
                "text": text,
                "title": meta.get("title", meta.get("filename", "Unknown")),
                "category": meta.get("category", "ogólne"),
                "language": meta.get("language", "pl"),
                "source_type": meta.get("source_type", "book"),
                "domains": list(meta.get("domains", [])),
                "experts": list(meta.get("experts", [])),
                "framework_tags": list(meta.get("framework_tags", [])),
                "score": combined,
                "vector_score": vector_score,
                "keyword_score": keyword_score if hybrid else None,
                "chunk_index": meta.get("chunk_index", 0),
                "total_chunks": meta.get("total_chunks", 0),
                "tags": meta.get("tags", ""),
                "doc_id": meta.get("doc_id", ""),
                "content_hash": meta.get("content_hash", ""),
            }
        )

    if hybrid and relevant_chunks:
        relevant_chunks.sort(key=lambda item: float(item.get("score", 0)), reverse=True)
        relevant_chunks = relevant_chunks[:top_k]

    return KnowledgeRetrievalResult(
        status="ok" if relevant_chunks else "no_matches",
        chunks=relevant_chunks,
    )


def query_knowledge(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    source_type: str | None = None,
    min_score: float = 0.3,
    hybrid: bool = False,
    domains: list[str] | None = None,
    experts: list[str] | None = None,
    namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible list-only wrapper around structured retrieval."""
    return query_knowledge_result(
        query=query,
        top_k=top_k,
        category=category,
        source_type=source_type,
        domains=domains,
        experts=experts,
        min_score=min_score,
        hybrid=hybrid,
        namespace=namespace,
    ).chunks


def format_context_for_agent(
    chunks: list[dict[str, Any]],
    include_provenance: bool = False,
) -> str:
    """Format retrieved chunks for an agent, optionally retaining provenance."""
    if not chunks:
        return "Brak relevantnego kontekstu z bazy wiedzy."
    if not include_provenance:
        return "\n\n---\n\n".join(chunk["text"] for chunk in chunks)

    context_parts: list[str] = []
    for chunk in chunks:
        context_parts.append(
            "\n".join(
                [
                    "[SOURCE]",
                    f"title: {chunk.get('title', 'Unknown')}",
                    f"source_type: {chunk.get('source_type', 'unknown')}",
                    f"doc_id: {chunk.get('doc_id', '')}",
                    f"chunk: {chunk.get('chunk_index', 0)}",
                    f"score: {float(chunk.get('score', 0)):.4f}",
                    "",
                    str(chunk.get("text", "")),
                ]
            )
        )
    return "\n\n---\n\n".join(context_parts)


def format_sources_for_display(
    chunks: list[dict[str, Any]],
    include_excerpt: bool = False,
) -> list[dict[str, Any]]:
    """Return display-safe provenance; excerpts are opt-in."""
    sources_by_title: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        title = chunk["title"]
        if title not in sources_by_title:
            sources_by_title[title] = {
                "title": title,
                "category": chunk.get("category", "ogólne"),
                "language": chunk.get("language", "pl"),
                "source_type": chunk.get("source_type", "book"),
                "domains": chunk.get("domains", []),
                "chunks_used": [],
                "max_score": 0.0,
            }
        chunk_payload: dict[str, Any] = {
            "chunk_index": chunk.get("chunk_index", 0),
            "score": chunk.get("score", 0),
        }
        if include_excerpt:
            text = str(chunk.get("text", ""))
            chunk_payload["text"] = text[:300] + "..." if len(text) > 300 else text
        sources_by_title[title]["chunks_used"].append(chunk_payload)
        sources_by_title[title]["max_score"] = max(
            float(sources_by_title[title]["max_score"]),
            float(chunk.get("score", 0)),
        )

    return sorted(
        sources_by_title.values(),
        key=lambda item: item["max_score"],
        reverse=True,
    )


def get_category_emoji(category: str) -> str:
    """Zwraca emoji dla kategorii."""
    emojis = {
        "marketing": "📣",
        "produktywność": "⚡",
        "strategia": "♟️",
        "biznes": "💼",
        "psychologia": "🧠",
        "rozwój_osobisty": "🌱",
        "komunikacja": "💬",
        "innowacje": "💡",
        "edukacja": "📚",
        "ogólne": "📖",
    }
    return emojis.get(category, "📖")


def search_by_category(category: str, query: str = "", top_k: int = 10) -> list[dict[str, Any]]:
    """Wyszukuje w określonej kategorii."""
    return query_knowledge(query or "wiedza", top_k=top_k, category=category)


def delete_vectors_by_doc_id(doc_id: str, namespace: str | None = None) -> bool:
    """Usuwa wszystkie wektory z metadanymi doc_id."""
    if not doc_id or not doc_id.strip():
        return False
    try:
        index = get_pinecone_index()
    except KnowledgeConfigError:
        return False
    delete_kwargs: dict[str, Any] = {"filter": {"doc_id": {"$eq": doc_id.strip()}}}
    if namespace is not None:
        delete_kwargs["namespace"] = namespace
    try:
        index.delete(**delete_kwargs)
        return True
    except Exception as exc:
        _retriever_log.warning(
            "Pinecone delete by doc_id failed error_type=%s",
            type(exc).__name__,
        )
        return False


def get_all_categories() -> list[str]:
    """Zwraca listę wszystkich kategorii."""
    return [
        "marketing",
        "produktywność",
        "strategia",
        "biznes",
        "psychologia",
        "rozwój_osobisty",
        "komunikacja",
        "innowacje",
        "edukacja",
        "ogólne",
    ]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"🔍 Szukam: {query}\n")
        results = query_knowledge(query)
        if results:
            print("📚 Źródła:")
            for source in format_sources_for_display(results):
                emoji = get_category_emoji(source["category"])
                print(f"\n{emoji} {source['title']} [{source['category']}]")
                print(f"   Trafność: {source['max_score']:.2f}")
        else:
            print("Brak wyników")
    else:
        print("Użycie: python retriever.py <zapytanie>")
