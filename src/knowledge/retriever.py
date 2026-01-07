"""
Knowledge Retriever
====================
Odpytuje Pinecone i zwraca relevantny kontekst
Z rozszerzonymi metadanymi (tytuł, kategoria, język)
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


def get_pinecone_index():
    """Zwraca połączony index Pinecone"""
    from pinecone import Pinecone
    
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
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
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    
    return response.data[0].embedding


def query_knowledge(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    min_score: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Odpytuje bazę wiedzy i zwraca relevantne fragmenty
    
    Args:
        query: Zapytanie użytkownika
        top_k: Liczba wyników do zwrócenia
        category: Filtr kategorii (marketing, biznes, etc.)
        source_type: Filtr typu źródła (book, summary, article)
        min_score: Minimalny score podobieństwa
    
    Returns:
        Lista relevantnych fragmentów z metadanymi
    """
    # Generuj embedding zapytania
    query_embedding = get_query_embedding(query)
    
    # Przygotuj filtr
    filter_dict = {}
    if source_type:
        filter_dict["source_type"] = source_type
    if category:
        filter_dict["category"] = category
    
    # Odpytaj Pinecone
    index = get_pinecone_index()
    
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict if filter_dict else None
    )
    
    # Przetwórz wyniki z rozszerzonymi metadanymi
    relevant_chunks = []
    for match in results.matches:
        if match.score >= min_score:
            relevant_chunks.append({
                "text": match.metadata.get("text", ""),
                "title": match.metadata.get("title", match.metadata.get("filename", "Unknown")),
                "category": match.metadata.get("category", "ogólne"),
                "language": match.metadata.get("language", "pl"),
                "source_type": match.metadata.get("source_type", "book"),
                "score": match.score,
                "chunk_index": match.metadata.get("chunk_index", 0),
                "total_chunks": match.metadata.get("total_chunks", 0)
            })
    
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


def get_all_categories() -> List[str]:
    """Zwraca listę wszystkich kategorii"""
    return [
        "marketing", "produktywność", "strategia", "biznes",
        "psychologia", "rozwój_osobisty", "komunikacja", 
        "innowacje", "edukacja"
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
