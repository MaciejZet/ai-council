"""
Knowledge Retriever
====================
Odpytuje Pinecone i zwraca relevantny kontekst
Z rozszerzonymi metadanymi (tytuł, kategoria, język)
"""

import os
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

from src.knowledge.errors import KnowledgeConfigError, KnowledgeEmbeddingError, KnowledgeFilterError
from src.utils.logger import setup_logger

load_dotenv()

_retriever_log = setup_logger("ai_council.knowledge")


def _keyword_overlap_score(query: str, text: str) -> float:
    """Simple token overlap ratio for hybrid reranking."""
    if not query.strip() or not text.strip():
        return 0.0
    q_tokens = set(t.lower() for t in query.replace("/", " ").split() if len(t) > 2)
    if not q_tokens:
        return 0.0
    t_lower = text.lower()
    hits = sum(1 for t in q_tokens if t in t_lower)
    return hits / max(len(q_tokens), 1)


def _validate_metadata_filters(
    category: Optional[str],
    source_type: Optional[str],
) -> None:
    allowed_categories = set(get_all_categories())
    if category is not None and category not in allowed_categories:
        raise KnowledgeFilterError(
            f"Invalid category {category!r}. Allowed: {sorted(allowed_categories)}"
        )
    allowed_source = {"book", "summary", "article", "ogólne", "web", "notion", "file"}
    if source_type is not None and source_type not in allowed_source:
        raise KnowledgeFilterError(
            f"Invalid source_type {source_type!r}. Allowed: {sorted(allowed_source)}"
        )


def get_pinecone_index():
    """Zwraca połączony index Pinecone"""
    key = os.getenv("PINECONE_API_KEY")
    if not key or key.strip() in ("", "dummy-key", "your_pinecone_key"):
        raise KnowledgeConfigError("PINECONE_API_KEY is missing or not configured")
    from pinecone import Pinecone

    pc = Pinecone(api_key=key)
    index_name = os.getenv("PINECONE_INDEX_NAME", "ebook-library")

    return pc.Index(index_name)


def get_query_embedding(query: str) -> List[float]:
    """
    Generuje embedding dla zapytania

    Args:
        query: Tekst zapytania

    Returns:
        Wektor embeddingu
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip() in ("", "dummy-key"):
        raise KnowledgeConfigError("OPENAI_API_KEY is missing or not configured for embeddings")
    from openai import OpenAI

    client = OpenAI(api_key=key)

    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query[:8000],
        )
    except Exception as exc:
        raise KnowledgeEmbeddingError(f"Embedding request failed: {exc}") from exc

    return response.data[0].embedding


def query_knowledge(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    min_score: float = 0.3,
    hybrid: bool = False,
) -> List[Dict[str, Any]]:
    """
    Odpytuje bazę wiedzy i zwraca relevantne fragmenty

    Args:
        query: Zapytanie użytkownika
        top_k: Liczba wyników do zwrócenia
        category: Filtr kategorii (marketing, biznes, etc.)
        source_type: Filtr typu źródła (book, summary, article)
        min_score: Minimalny score podobieństwa
        hybrid: Pobierz więcej wyników wektorowych i przesortuj z użyciem nakładania słów kluczowych

    Returns:
        Lista relevantnych fragmentów z metadanymi (pusta przy błędzie odzyskiwalnym).
    """
    if not query or not query.strip():
        return []

    try:
        _validate_metadata_filters(category, source_type)
    except KnowledgeFilterError:
        raise

    try:
        query_embedding = get_query_embedding(query)
    except KnowledgeConfigError as e:
        _retriever_log.warning("Knowledge base skipped: %s", e)
        return []
    except KnowledgeEmbeddingError as e:
        _retriever_log.error("Embedding error: %s", e)
        return []

    filter_dict: Dict[str, Any] = {}
    if source_type:
        filter_dict["source_type"] = source_type
    if category:
        filter_dict["category"] = category

    try:
        index = get_pinecone_index()
    except KnowledgeConfigError as e:
        _retriever_log.warning("Pinecone unavailable: %s", e)
        return []

    fetch_k = top_k * 3 if hybrid else top_k
    try:
        results = index.query(
            vector=query_embedding,
            top_k=max(fetch_k, top_k),
            include_metadata=True,
            filter=filter_dict if filter_dict else None,
        )
    except Exception as exc:
        _retriever_log.error("Pinecone query failed: %s", exc)
        return []

    relevant_chunks = []
    for match in results.matches:
        if match.score is not None and match.score >= min_score:
            meta = match.metadata or {}
            vec_score = float(match.score)
            text = meta.get("text", "")
            kw = _keyword_overlap_score(query, text) if hybrid else 0.0
            combined = 0.65 * vec_score + 0.35 * kw if hybrid else vec_score
            relevant_chunks.append(
                {
                    "text": text,
                    "title": meta.get("title", meta.get("filename", "Unknown")),
                    "category": meta.get("category", "ogólne"),
                    "language": meta.get("language", "pl"),
                    "source_type": meta.get("source_type", "book"),
                    "score": combined,
                    "vector_score": vec_score,
                    "keyword_score": kw if hybrid else None,
                    "chunk_index": meta.get("chunk_index", 0),
                    "total_chunks": meta.get("total_chunks", 0),
                    "tags": meta.get("tags", ""),
                    "doc_id": meta.get("doc_id", ""),
                }
            )

    if hybrid and relevant_chunks:
        relevant_chunks.sort(key=lambda x: float(x.get("score", 0)), reverse=True)
        relevant_chunks = relevant_chunks[:top_k]

    return relevant_chunks


def format_context_for_agent(chunks: List[Dict[str, Any]]) -> str:
    """
    Formatuje chunki jako kontekst dla agenta (bez cytowań inline)
    
    Args:
        chunks: Lista chunków z query_knowledge
    
    Returns:
        Sformatowany tekst kontekstu (tylko treść)
    """
    if not chunks:
        return "Brak relevantnego kontekstu z bazy wiedzy."
    
    # Agent dostaje tylko tekst, bez źródeł inline
    context_parts = [chunk["text"] for chunk in chunks]
    return "\n\n---\n\n".join(context_parts)


def format_sources_for_display(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Formatuje źródła do wyświetlenia w UI
    
    Args:
        chunks: Lista chunków z query_knowledge
    
    Returns:
        Lista uproszczonych źródeł do wyświetlenia
    """
    # Grupuj po tytule
    sources_by_title = {}
    for chunk in chunks:
        title = chunk["title"]
        if title not in sources_by_title:
            sources_by_title[title] = {
                "title": title,
                "category": chunk["category"],
                "language": chunk["language"],
                "chunks_used": [],
                "max_score": 0
            }
        sources_by_title[title]["chunks_used"].append({
            "text": chunk["text"][:300] + "..." if len(chunk["text"]) > 300 else chunk["text"],
            "score": chunk["score"]
        })
        sources_by_title[title]["max_score"] = max(
            sources_by_title[title]["max_score"], 
            chunk["score"]
        )
    
    # Sortuj po max_score
    return sorted(
        sources_by_title.values(),
        key=lambda x: x["max_score"],
        reverse=True
    )


def get_category_emoji(category: str) -> str:
    """Zwraca emoji dla kategorii"""
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
        "ogólne": "📖"
    }
    return emojis.get(category, "📖")


def search_by_category(category: str, query: str = "", top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Wyszukuje w określonej kategorii
    
    Args:
        category: Kategoria do przeszukania
        query: Opcjonalne zapytanie
        top_k: Liczba wyników
    
    Returns:
        Lista wyników
    """
    return query_knowledge(query or "wiedza", top_k=top_k, category=category)


def delete_vectors_by_doc_id(doc_id: str) -> bool:
    """Usuwa wszystkie wektory z metadanymi doc_id (odświeżanie embeddingów)."""
    if not doc_id or not doc_id.strip():
        return False
    try:
        index = get_pinecone_index()
    except KnowledgeConfigError:
        return False
    try:
        index.delete(filter={"doc_id": {"$eq": doc_id.strip()}})
        return True
    except Exception as exc:
        _retriever_log.error("Pinecone delete by doc_id failed: %s", exc)
        return False


def get_all_categories() -> List[str]:
    """Zwraca listę wszystkich kategorii"""
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
    # Test retrieval
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
