"""
Per-Character Knowledge Base
=============================
Każda postać historyczna ma własną bazę wiedzy (namespace w Pinecone)
z książkami, cytatami i materiałami autorskimi.
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# Mapowanie postaci na namespaces w Pinecone
CHARACTER_NAMESPACES: Dict[str, str] = {
    # Philosophy
    "aristotle": "aristotle",
    "seneca": "seneca",
    "marcus_aurelius": "marcus_aurelius",
    # Strategy
    "napoleon": "napoleon",
    "sun_tzu": "sun_tzu",
    # Business
    "buffett": "buffett",
    "hormozi": "hormozi",
    # Innovation
    "musk": "musk",
    "jobs": "jobs",
    # Creativity
    "da_vinci": "da_vinci",
    "disney": "disney",
}


# Rekomendowane książki/materiały dla każdej postaci
CHARACTER_SOURCES: Dict[str, List[Dict[str, str]]] = {
    "aristotle": [
        {"title": "Etyka Nikomachejska", "type": "book"},
        {"title": "Polityka", "type": "book"},
        {"title": "Metafizyka", "type": "book"},
        {"title": "Retoryka", "type": "book"},
    ],
    "seneca": [
        {"title": "Listy do Lucyliusza", "type": "book"},
        {"title": "O krótkości życia", "type": "book"},
        {"title": "O gniewie", "type": "book"},
    ],
    "marcus_aurelius": [
        {"title": "Rozmyślania (Meditations)", "type": "book"},
    ],
    "napoleon": [
        {"title": "Maksymy Napoleona", "type": "book"},
        {"title": "Korespondencja Napoleona", "type": "letters"},
    ],
    "sun_tzu": [
        {"title": "Sztuka Wojny", "type": "book"},
    ],
    "buffett": [
        {"title": "Listy do akcjonariuszy Berkshire Hathaway", "type": "letters"},
        {"title": "The Snowball: Warren Buffett and the Business of Life", "type": "book"},
        {"title": "The Essays of Warren Buffett", "type": "book"},
    ],
    "hormozi": [
        {"title": "$100M Offers", "type": "book"},
        {"title": "$100M Leads", "type": "book"},
        {"title": "Gym Launch Secrets", "type": "book"},
    ],
    "musk": [
        {"title": "Elon Musk (Ashlee Vance)", "type": "biography"},
        {"title": "Wywiady i przemówienia Muska", "type": "interviews"},
    ],
    "jobs": [
        {"title": "Steve Jobs (Walter Isaacson)", "type": "biography"},
        {"title": "Prezentacje Steve'a Jobsa", "type": "speeches"},
    ],
    "da_vinci": [
        {"title": "Notatniki Leonarda da Vinci", "type": "notebooks"},
        {"title": "Leonardo da Vinci (Walter Isaacson)", "type": "biography"},
    ],
    "disney": [
        {"title": "The Ride of a Lifetime (Bob Iger)", "type": "book"},
        {"title": "Walt Disney: The Triumph of the American Imagination", "type": "biography"},
    ],
}


def get_pinecone_index():
    """Zwraca połączony index Pinecone"""
    from pinecone import Pinecone
    
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME", "ebook-library")
    
    return pc.Index(index_name)


def get_query_embedding(query: str) -> List[float]:
    """Generuje embedding dla zapytania"""
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    
    return response.data[0].embedding


def query_character_knowledge(
    query: str,
    character_id: str,
    top_k: int = 3,
    min_score: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Odpytuje bazę wiedzy KONKRETNEJ postaci (namespace w Pinecone)
    
    Args:
        query: Zapytanie użytkownika
        character_id: ID postaci (np. "buffett", "aristotle")
        top_k: Liczba wyników
        min_score: Minimalny score podobieństwa
    
    Returns:
        Lista relevantnych fragmentów z wiedzy postaci
    """
    namespace = CHARACTER_NAMESPACES.get(character_id)
    if not namespace:
        return []
    
    try:
        query_embedding = get_query_embedding(query)
        index = get_pinecone_index()
        
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=namespace
        )
        
        relevant_chunks = []
        for match in results.matches:
            if match.score >= min_score:
                relevant_chunks.append({
                    "text": match.metadata.get("text", ""),
                    "title": match.metadata.get("title", "Unknown"),
                    "character": character_id,
                    "score": match.score,
                    "source_type": match.metadata.get("source_type", "book")
                })
        
        return relevant_chunks
    except Exception as e:
        print(f"⚠️ Błąd pobierania wiedzy dla {character_id}: {e}")
        return []


def format_character_context(chunks: List[Dict[str, Any]], character_name: str) -> str:
    """
    Formatuje kontekst z wiedzy postaci
    
    Args:
        chunks: Lista chunków z query_character_knowledge
        character_name: Nazwa postaci (do formatowania)
    
    Returns:
        Sformatowany tekst kontekstu
    """
    if not chunks:
        return ""
    
    header = f"## Z moich dzieł i słów ({character_name}):\n\n"
    texts = [chunk["text"] for chunk in chunks]
    
    return header + "\n\n---\n\n".join(texts)


def ingest_pdf_for_character(
    pdf_path: str,
    character_id: str,
    title: str,
    source_type: str = "book",
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Dict[str, Any]:
    """
    Importuje PDF do bazy wiedzy konkretnej postaci
    
    Args:
        pdf_path: Ścieżka do pliku PDF
        character_id: ID postaci
        title: Tytuł książki/dokumentu
        source_type: Typ źródła (book, letters, biography, etc.)
        chunk_size: Rozmiar chunku
        chunk_overlap: Nakładanie chunków
    
    Returns:
        Statystyki importu
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import PyPDFLoader
    
    namespace = CHARACTER_NAMESPACES.get(character_id)
    if not namespace:
        raise ValueError(f"Unknown character: {character_id}")
    
    # Wczytaj PDF
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    
    # Podziel na chunki
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    
    # Przygotuj do Pinecone
    index = get_pinecone_index()
    
    vectors = []
    for i, chunk in enumerate(chunks):
        text = chunk.page_content
        embedding = get_query_embedding(text)
        
        vector_id = f"{character_id}_{title.replace(' ', '_')[:20]}_{i}"
        
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "text": text,
                "title": title,
                "character": character_id,
                "source_type": source_type,
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
        })
    
    # Upsert do namespace postaci
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch, namespace=namespace)
    
    return {
        "character": character_id,
        "namespace": namespace,
        "title": title,
        "chunks_imported": len(vectors),
        "source_type": source_type
    }


def get_character_knowledge_stats(character_id: str) -> Dict[str, Any]:
    """
    Zwraca statystyki bazy wiedzy postaci
    
    Args:
        character_id: ID postaci
    
    Returns:
        Statystyki (liczba wektorów, źródła, etc.)
    """
    namespace = CHARACTER_NAMESPACES.get(character_id)
    if not namespace:
        return {"error": f"Unknown character: {character_id}"}
    
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        namespace_stats = stats.namespaces.get(namespace, {})
        
        return {
            "character": character_id,
            "namespace": namespace,
            "vector_count": namespace_stats.get("vector_count", 0),
            "recommended_sources": CHARACTER_SOURCES.get(character_id, [])
        }
    except Exception as e:
        return {"error": str(e)}


def list_all_character_knowledge() -> Dict[str, Dict[str, Any]]:
    """
    Zwraca statystyki wiedzy dla wszystkich postaci
    
    Returns:
        Słownik z statystykami każdej postaci
    """
    result = {}
    for character_id in CHARACTER_NAMESPACES.keys():
        result[character_id] = get_character_knowledge_stats(character_id)
    return result


if __name__ == "__main__":
    # Test
    import sys
    
    if len(sys.argv) > 2:
        char = sys.argv[1]
        query = " ".join(sys.argv[2:])
        print(f"🔍 Szukam w wiedzy {char}: {query}\n")
        
        results = query_character_knowledge(query, char)
        if results:
            for chunk in results:
                print(f"📖 {chunk['title']} (score: {chunk['score']:.2f})")
                print(f"   {chunk['text'][:200]}...\n")
        else:
            print("Brak wyników lub postać nie ma bazy wiedzy")
    else:
        print("Użycie: python character_knowledge.py <character_id> <query>")
        print("Przykład: python character_knowledge.py buffett value investing")
