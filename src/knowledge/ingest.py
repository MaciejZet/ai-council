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
    doc_id = hashlib.sha256(f"{str(pdf_path)}|{filename}".encode()).hexdigest()[:28]

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
                "source_path": str(pdf_path),
                "doc_id": doc_id,
                "tags": "",
                "embedding_version": "v1",
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
        "characters_count": len(text),
        "doc_id": doc_id,
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


def _upsert_text_to_pinecone(
    title: str,
    text: str,
    *,
    source_type: str,
    category: str,
    language: str,
    source_path: str,
    tags: str = "",
    embedding_version: str = "v1",
    batch_size: int = 100,
) -> Dict[str, Any]:
    """Shared upsert for raw text (URL, Notion, txt/md)."""
    if not text.strip():
        return {"status": "error", "message": "Pusty tekst"}

    doc_id = hashlib.sha256(f"{title}|{source_path}|{embedding_version}".encode()).hexdigest()[:28]
    chunks = chunk_text(text)
    chunk_texts = [c["text"] for c in chunks]
    embeddings = get_embeddings(chunk_texts)
    index = get_pinecone_index()

    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = hashlib.md5(f"{doc_id}_{i}".encode()).hexdigest()
        vectors.append(
            {
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "text": chunk["text"],
                    "title": title[:500],
                    "category": category,
                    "language": language,
                    "source_type": source_type,
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": len(chunks),
                    "source_path": source_path[:1000],
                    "doc_id": doc_id,
                    "tags": tags[:500],
                    "embedding_version": embedding_version,
                },
            }
        )

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch)

    return {
        "status": "success",
        "title": title,
        "category": category,
        "language": language,
        "chunks_count": len(chunks),
        "characters_count": len(text),
        "doc_id": doc_id,
    }


def extract_text_from_html(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def fetch_url_text(url: str, timeout: float = 30.0) -> tuple[str, str]:
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AICouncilBot/1.0; +https://example.local)"
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "text/html" in ctype.lower():
            title = url
            text = extract_text_from_html(r.text)
            # crude title from <title>
            try:
                from bs4 import BeautifulSoup

                t = BeautifulSoup(r.text, "html.parser").find("title")
                if t and t.string:
                    title = t.string.strip()[:200]
            except Exception:
                pass
            return title, text
        return url, r.text


def ingest_url(
    url: str,
    *,
    category: str = "ogólne",
    tags: str = "",
    embedding_version: str = "v1",
) -> Dict[str, Any]:
    """Pobiera stronę HTTP i indeksuje treść."""
    try:
        title, text = fetch_url_text(url)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    return _upsert_text_to_pinecone(
        title,
        text,
        source_type="web",
        category=category,
        language="pl",
        source_path=url,
        tags=tags,
        embedding_version=embedding_version,
    )


def ingest_notion_page(
    page_id: str,
    *,
    category: str = "ogólne",
    tags: str = "",
    embedding_version: str = "v1",
) -> Dict[str, Any]:
    """Pobiera treść strony Notion (wymaga NOTION_API_KEY)."""
    token = os.getenv("NOTION_API_KEY")
    if not token or token.strip() in ("", "dummy-key"):
        return {"status": "error", "message": "NOTION_API_KEY nie jest ustawiony"}

    import httpx

    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
    base = "https://api.notion.com/v1"
    with httpx.Client(timeout=60.0, headers=headers) as client:
        pr = client.get(f"{base}/pages/{page_id}")
        if pr.status_code != 200:
            return {"status": "error", "message": pr.text[:500]}
        page = pr.json()
        title = "Notion"
        try:
            props = page.get("properties") or {}
            for _k, v in props.items():
                if isinstance(v, dict) and v.get("type") == "title":
                    parts = v.get("title") or []
                    title = "".join(p.get("plain_text", "") for p in parts) or title
                    break
        except Exception:
            pass

        texts: list[str] = []

        def walk_blocks(block_id: str) -> None:
            r = client.get(f"{base}/blocks/{block_id}/children")
            if r.status_code != 200:
                return
            data = r.json()
            for block in data.get("results") or []:
                btype = block.get("type")
                payload = block.get(btype) or {}
                if btype in ("paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "quote", "to_do"):
                    rich = payload.get("rich_text") or []
                    line = "".join(p.get("plain_text", "") for p in rich)
                    if line.strip():
                        texts.append(line)
                if block.get("has_children"):
                    walk_blocks(block["id"])

        walk_blocks(page_id)
        body = "\n\n".join(texts)

    if not body.strip():
        return {"status": "error", "message": "Brak tekstu w blokach Notion (tylko pierwsze poziomy)."}

    return _upsert_text_to_pinecone(
        title,
        body,
        source_type="notion",
        category=category,
        language="pl",
        source_path=f"notion:{page_id}",
        tags=tags,
        embedding_version=embedding_version,
    )


def ingest_text_file(path: str, source_type: str = "file", category: str = "ogólne", tags: str = "") -> Dict[str, Any]:
    """Import pojedynczego pliku .txt lub .md."""
    p = Path(path)
    if not p.is_file():
        return {"status": "error", "message": "Plik nie istnieje"}
    if p.suffix.lower() not in (".txt", ".md", ".markdown"):
        return {"status": "error", "message": "Obsługiwane: .txt, .md"}
    text = p.read_text(encoding="utf-8", errors="replace")
    lang = "pl" if any(c in p.stem for c in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ") else "en"
    return _upsert_text_to_pinecone(
        p.stem,
        text,
        source_type=source_type,
        category=category,
        language=lang,
        source_path=str(p.resolve()),
        tags=tags,
    )


def ingest_mixed_directory(directory_path: str, source_type_default: str = "book") -> List[Dict[str, Any]]:
    """PDF, TXT, MD w jednym katalogu."""
    path = Path(directory_path)
    if not path.is_dir():
        return [{"status": "error", "message": "To nie jest katalog"}]
    results: List[Dict[str, Any]] = []
    for pdf_file in sorted(path.glob("*.pdf")):
        results.append(ingest_pdf(str(pdf_file), source_type_default))
    for ext in ("*.txt", "*.md", "*.markdown"):
        for f in sorted(path.glob(ext)):
            results.append(ingest_text_file(str(f), source_type="file"))
    return results


def refresh_document_embeddings(doc_id: str, embedding_version: str = "v2") -> Dict[str, Any]:
    """
    Usuń stare wektory doc_id i ponownie załaduj — wymaga ponownego ingestu źródła
    (ten endpoint tylko czyści Pinecone po doc_id).
    """
    from src.knowledge.retriever import delete_vectors_by_doc_id

    if delete_vectors_by_doc_id(doc_id):
        return {"status": "success", "message": f"Usunięto wektory doc_id={doc_id}. Zaimportuj plik/URL ponownie.", "embedding_version": embedding_version}
    return {"status": "error", "message": "Nie udało się usunąć lub brak doc_id w indeksie"}


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
