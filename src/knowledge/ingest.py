"""
PDF Ingestion Pipeline
=======================
Przetwarza PDF-y do wektorów i zapisuje do Pinecone
Z rozszerzonym systemem metadanych (tytuł, kategoria, język)
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import hashlib

load_dotenv()


# ========== MAPOWANIE KSIĄŻEK NA KATEGORIE ==========

BOOK_CATEGORIES: Dict[str, Dict[str, Any]] = {
    # Marketing
    "$100M Leads": {"category": "marketing", "language": "en"},
    "$100M Offers": {"category": "marketing", "language": "en"},
    "22 niezmienne prawa marketingu": {"category": "marketing", "language": "pl"},
    "Marketing przyzwoleń": {"category": "marketing", "language": "pl"},
    "This Is Marketing": {"category": "marketing", "language": "en"},
    "Plemiona": {"category": "marketing", "language": "pl"},
    
    # Produktywność
    "Atomowe nawyki": {"category": "produktywność", "language": "pl"},
    "Get Things Done": {"category": "produktywność", "language": "en"},
    "Essentialism": {"category": "produktywność", "language": "en"},
    "Czas skupienia": {"category": "produktywność", "language": "pl"},
    "Flow": {"category": "produktywność", "language": "en"},
    "Budowanie Drugiego Mózgu": {"category": "produktywność", "language": "pl"},
    
    # Strategia
    "48 Praw Władzy": {"category": "strategia", "language": "pl"},
    "Sztuka wojny": {"category": "strategia", "language": "pl"},
    "Dobra strategia, zła strategia": {"category": "strategia", "language": "pl"},
    "Sztuka Strategii": {"category": "strategia", "language": "pl"},
    "Przetrwają tylko paranoicy": {"category": "strategia", "language": "pl"},
    "Księga Pięciu Pierścieni": {"category": "strategia", "language": "pl"},
    
    # Biznes
    "Good to Great": {"category": "biznes", "language": "en"},
    "CEO Excellence": {"category": "biznes", "language": "en"},
    "Running Lean": {"category": "biznes", "language": "en"},
    "Wielka gra biznesowa": {"category": "biznes", "language": "pl"},
    "Mierz to, co ważne": {"category": "biznes", "language": "pl"},
    "Świetny z wyboru": {"category": "biznes", "language": "pl"},
    "Jak upadek Potężnego": {"category": "biznes", "language": "pl"},
    "Przygody biznesowe": {"category": "biznes", "language": "pl"},
    "Mechanizm zegarowy": {"category": "biznes", "language": "pl"},
    "Problem zimnego startu": {"category": "biznes", "language": "pl"},
    "Wygranej": {"category": "biznes", "language": "pl"},
    "Zacznij od Nie": {"category": "biznes", "language": "pl"},
    "Zasada piramidy": {"category": "biznes", "language": "pl"},
    "The Diary of a CEO": {"category": "biznes", "language": "en"},
    "Same as Ever": {"category": "biznes", "language": "en"},
    "Pozwól moim ludziom surfować": {"category": "biznes", "language": "pl"},
    "Inteligentny inwestor": {"category": "biznes", "language": "pl"},
    "Ołów z przyszłości": {"category": "biznes", "language": "pl"},
    
    # Psychologia
    "The Laws Of Human Nature": {"category": "psychologia", "language": "en"},
    "Nastawienie": {"category": "psychologia", "language": "pl"},
    "Cues": {"category": "psychologia", "language": "en"},
    "The Mountain Is You": {"category": "psychologia", "language": "en"},
    "Codzienne Prawa": {"category": "psychologia", "language": "pl"},
    "Odwaga, by być nielubianym": {"category": "psychologia", "language": "pl"},
    "Poszukiwanie sensu przez człowieka": {"category": "psychologia", "language": "pl"},
    "Spark": {"category": "psychologia", "language": "en"},
    
    # Rozwój osobisty
    "12 zasad życia": {"category": "rozwój_osobisty", "language": "pl"},
    "Medytacje": {"category": "rozwój_osobisty", "language": "pl"},
    "Ikigai & Kaizen": {"category": "rozwój_osobisty", "language": "pl"},
    "Mastery": {"category": "rozwój_osobisty", "language": "en"},
    "Republika": {"category": "rozwój_osobisty", "language": "pl"},
    "Ponowne uruchomienie": {"category": "rozwój_osobisty", "language": "pl"},
    
    # Komunikacja
    "Better Small Talk": {"category": "komunikacja", "language": "en"},
    "Mów jak TED": {"category": "komunikacja", "language": "pl"},
    "Radykalna szczerość": {"category": "komunikacja", "language": "pl"},
    "The Next Conversation": {"category": "komunikacja", "language": "en"},
    
    # Innowacje / Design
    "Dziesięć rodzajów innowacji": {"category": "innowacje", "language": "pl"},
    "User Friendly": {"category": "innowacje", "language": "en"},
    "Projektowanie rzeczy codziennego użytku": {"category": "innowacje", "language": "pl"},
    "Teoria zabawy w projektowaniu gier": {"category": "innowacje", "language": "pl"},
    
    # Edukacja
    "Uncommon Sense Teaching": {"category": "edukacja", "language": "en"},
    "Wszystko, co chcesz": {"category": "rozwój_osobisty", "language": "pl"},
}


def get_book_metadata(filename: str) -> Dict[str, str]:
    """
    Zwraca metadane dla książki na podstawie nazwy pliku
    
    Args:
        filename: Nazwa pliku (bez rozszerzenia)
    
    Returns:
        Słownik z category i language
    """
    # Szukaj dokładnego dopasowania
    if filename in BOOK_CATEGORIES:
        return BOOK_CATEGORIES[filename]
    
    # Szukaj częściowego dopasowania
    for book_name, metadata in BOOK_CATEGORIES.items():
        if book_name.lower() in filename.lower() or filename.lower() in book_name.lower():
            return metadata
    
    # Domyślne wartości
    # Wykryj język na podstawie znaków polskich
    is_polish = any(char in filename for char in 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')
    return {
        "category": "ogólne",
        "language": "pl" if is_polish else "en"
    }


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Ekstraktuje tekst z pliku PDF
    
    Args:
        pdf_path: Ścieżka do pliku PDF
    
    Returns:
        Tekst z PDF-a
    """
    import pdfplumber
    
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    
    return "\n\n".join(text_parts)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Dzieli tekst na chunki z overlap
    
    Args:
        text: Tekst do podzielenia
        chunk_size: Rozmiar chunka w znakach
        overlap: Nakładanie się chunków
    
    Returns:
        Lista chunków z metadanymi
    """
    chunks = []
    start = 0
    chunk_index = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]
        
        # Znajdź koniec zdania jeśli to możliwe
        if end < len(text):
            last_period = chunk_text.rfind('.')
            last_newline = chunk_text.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk_text = chunk_text[:break_point + 1]
                end = start + break_point + 1
        
        chunks.append({
            "text": chunk_text.strip(),
            "chunk_index": chunk_index,
            "start_char": start,
            "end_char": end
        })
        
        start = end - overlap
        chunk_index += 1
    
    return chunks


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generuje embeddingi dla listy tekstów używając OpenAI
    
    Args:
        texts: Lista tekstów do embeddingu
    
    Returns:
        Lista wektorów embeddingów
    """
    from openai import OpenAI
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    
    return [item.embedding for item in response.data]


def get_pinecone_index():
    """Zwraca połączony index Pinecone"""
    from pinecone import Pinecone
    
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME", "ebook-library")
    
    return pc.Index(index_name)


def generate_chunk_id(filename: str, chunk_index: int) -> str:
    """Generuje unikalny ID dla chunka"""
    content = f"{filename}_{chunk_index}"
    return hashlib.md5(content.encode()).hexdigest()


def ingest_pdf(pdf_path: str, source_type: str = "book", batch_size: int = 100) -> Dict[str, Any]:
    """
    Przetwarza pojedynczy PDF i zapisuje do Pinecone
    Z rozszerzonymi metadanymi (tytuł, kategoria, język)
    
    Args:
        pdf_path: Ścieżka do pliku PDF
        source_type: Typ źródła (book, summary, article)
        batch_size: Rozmiar batch przy upsert
    
    Returns:
        Słownik z informacjami o przetworzeniu
    """
    path = Path(pdf_path)
    filename = path.stem  # Nazwa bez rozszerzenia = tytuł
    
    # Pobierz metadane książki
    book_meta = get_book_metadata(filename)
    category = book_meta["category"]
    language = book_meta["language"]
    
    # Ekstraktuj tekst
    print(f"📄 Ekstrakcja tekstu z: {filename}")
    print(f"   📁 Kategoria: {category} | 🌐 Język: {language}")
    text = extract_text_from_pdf(pdf_path)
    
    if not text.strip():
        return {"status": "error", "message": "Nie udało się wyekstraktować tekstu"}
    
    # Podziel na chunki
    print(f"✂️  Dzielenie na chunki...")
    chunks = chunk_text(text)
    print(f"   Utworzono {len(chunks)} chunków")
    
    # Generuj embeddingi
    print(f"🧠 Generowanie embeddingów...")
    chunk_texts = [c["text"] for c in chunks]
    embeddings = get_embeddings(chunk_texts)
    
    # Przygotuj dane do Pinecone
    index = get_pinecone_index()
    
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = generate_chunk_id(filename, i)
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "text": chunk["text"],
                "title": filename,              # Tytuł książki
                "category": category,           # Kategoria tematyczna
                "language": language,           # Język (pl/en)
                "source_type": source_type,     # book/summary/article
                "chunk_index": chunk["chunk_index"],
                "total_chunks": len(chunks),
                "source_path": str(pdf_path)
            }
        })
    
    # Upsert do Pinecone w batchach
    print(f"📤 Zapisywanie do Pinecone...")
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)
        print(f"   Zapisano {min(i + batch_size, len(vectors))}/{len(vectors)}")
    
    return {
        "status": "success",
        "title": filename,
        "category": category,
        "language": language,
        "chunks_count": len(chunks),
        "characters_count": len(text)
    }


def ingest_directory(directory_path: str, source_type: str = "book") -> List[Dict[str, Any]]:
    """
    Przetwarza wszystkie PDF-y w katalogu
    
    Args:
        directory_path: Ścieżka do katalogu z PDF-ami
        source_type: Typ źródła
    
    Returns:
        Lista wyników przetwarzania
    """
    path = Path(directory_path)
    pdf_files = sorted(list(path.glob("*.pdf")))  # Posortowane alfabetycznie
    
    print(f"📚 Znaleziono {len(pdf_files)} plików PDF")
    print("=" * 50)
    
    results = []
    total_chunks = 0
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Przetwarzanie: {pdf_file.name}")
        try:
            result = ingest_pdf(str(pdf_file), source_type)
            results.append(result)
            if result["status"] == "success":
                total_chunks += result["chunks_count"]
        except Exception as e:
            print(f"   ❌ Błąd: {e}")
            results.append({
                "status": "error",
                "title": pdf_file.stem,
                "message": str(e)
            })
    
    # Podsumowanie
    print("\n" + "=" * 50)
    print(f"✅ Zakończono import!")
    print(f"   📚 Książek: {len([r for r in results if r['status'] == 'success'])}")
    print(f"   📄 Chunków łącznie: {total_chunks}")
    print(f"   ❌ Błędów: {len([r for r in results if r['status'] == 'error'])}")
    
    return results


def get_ingestion_stats() -> Dict[str, Any]:
    """
    Zwraca statystyki bazy wiedzy w Pinecone
    
    Returns:
        Słownik ze statystykami
    """
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        
        # Serialize safely - extract only primitive values
        namespaces_dict = {}
        if stats.namespaces:
            for ns_name, ns_info in stats.namespaces.items():
                namespaces_dict[ns_name] = {
                    "vector_count": getattr(ns_info, 'vector_count', 0)
                }
        
        return {
            "total_vectors": int(stats.total_vector_count) if stats.total_vector_count else 0,
            "dimension": int(stats.dimension) if stats.dimension else 0,
            "namespaces": namespaces_dict
        }
    except Exception as e:
        return {
            "total_vectors": 0,
            "dimension": 0,
            "namespaces": {},
            "error": str(e)
        }


if __name__ == "__main__":
    # Test ingestion
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        result = ingest_pdf(pdf_path)
        print(f"\n✅ Wynik: {result}")
    else:
        print("Użycie: python ingest.py <ścieżka_do_pdf>")
        print("\nStatystyki bazy:")
        print(get_ingestion_stats())
