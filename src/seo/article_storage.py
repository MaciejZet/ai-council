"""
Article Storage (Pinecone)
==========================
Przechowywanie artykułów w Pinecone dla deduplication
Używa osobnego indexu 'seo-articles'
"""

import os
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Article:
    """Pełny artykuł z treścią"""
    id: str
    title: str
    content: str
    content_html: str = ""
    topic: str = ""
    target_url: str = ""
    keywords: List[str] = field(default_factory=list)
    word_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ArticleMeta:
    """Metadane artykułu (bez pełnej treści)"""
    id: str
    title: str
    topic: str
    target_url: str
    word_count: int
    created_at: str
    similarity_score: float = 0.0


class ArticleStorage:
    """
    Przechowuje artykuły w Pinecone dla deduplication
    
    Features:
    - Store article with embedding
    - Check similarity before generation
    - List all articles
    - Update existing articles
    """
    
    def __init__(self):
        self.index_name = os.getenv("PINECONE_SEO_INDEX_NAME", "seo-articles")
        self._index = None
    
    def _get_index(self):
        """Lazy-load Pinecone index"""
        if self._index is None:
            from pinecone import Pinecone
            
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            
            # Sprawdź czy index istnieje
            existing_indexes = [idx.name for idx in pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                # Utwórz index jeśli nie istnieje
                # Dimension 1536 dla text-embedding-3-small
                pc.create_index(
                    name=self.index_name,
                    dimension=1536,
                    metric="cosine",
                    spec={
                        "serverless": {
                            "cloud": "aws",
                            "region": "us-east-1"
                        }
                    }
                )
            
            self._index = pc.Index(self.index_name)
        
        return self._index
    
    def _get_embedding(self, text: str) -> List[float]:
        """Generuje embedding dla tekstu"""
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Używamy pierwszych 8000 znaków (limit tokenów)
        truncated = text[:8000]
        
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=truncated
        )
        
        return response.data[0].embedding
    
    def _generate_id(self, title: str, topic: str) -> str:
        """Generuje unikalny ID dla artykułu"""
        content = f"{title}:{topic}:{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    async def store(self, article: Article) -> str:
        """
        Zapisuje artykuł w Pinecone
        
        Args:
            article: Artykuł do zapisania
            
        Returns:
            ID zapisanego artykułu
        """
        index = self._get_index()
        
        # Generuj ID jeśli brak
        if not article.id:
            article.id = self._generate_id(article.title, article.topic)
        
        # Ustaw daty
        now = datetime.now().isoformat()
        if not article.created_at:
            article.created_at = now
        article.updated_at = now
        
        # Ustaw word count
        if not article.word_count:
            article.word_count = len(article.content.split())
        
        # Generuj embedding z tytułu + początku treści
        embed_text = f"{article.title}\n\n{article.topic}\n\n{article.content[:2000]}"
        embedding = self._get_embedding(embed_text)
        
        # Przygotuj metadata (Pinecone ma limit na rozmiar)
        metadata = {
            "title": article.title,
            "topic": article.topic,
            "target_url": article.target_url,
            "keywords": ",".join(article.keywords[:10]),  # Max 10 keywords
            "word_count": article.word_count,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
            "content_preview": article.content[:500]  # Preview only
        }
        
        # Upsert do Pinecone
        index.upsert(
            vectors=[{
                "id": article.id,
                "values": embedding,
                "metadata": metadata
            }]
        )
        
        # Zapisz pełną treść lokalnie (Pinecone ma limit metadata)
        self._save_content_locally(article)
        
        return article.id
    
    def _save_content_locally(self, article: Article):
        """Zapisuje pełną treść artykułu lokalnie"""
        import json
        
        articles_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "articles"
        )
        os.makedirs(articles_dir, exist_ok=True)
        
        filepath = os.path.join(articles_dir, f"{article.id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(article.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _load_content_locally(self, article_id: str) -> Optional[Article]:
        """Wczytuje pełną treść artykułu z pliku lokalnego"""
        import json
        
        filepath = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "articles",
            f"{article_id}.json"
        )
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Article.from_dict(data)
        except (json.JSONDecodeError, IOError):
            return None
    
    async def find_similar(
        self, 
        topic: str, 
        threshold: float = 0.85
    ) -> List[ArticleMeta]:
        """
        Znajduje podobne artykuły
        
        Args:
            topic: Temat do sprawdzenia
            threshold: Próg podobieństwa (0-1)
            
        Returns:
            Lista podobnych artykułów
        """
        index = self._get_index()
        
        # Generuj embedding dla tematu
        embedding = self._get_embedding(topic)
        
        # Szukaj podobnych
        results = index.query(
            vector=embedding,
            top_k=5,
            include_metadata=True
        )
        
        similar = []
        for match in results.matches:
            if match.score >= threshold:
                meta = match.metadata
                similar.append(ArticleMeta(
                    id=match.id,
                    title=meta.get("title", ""),
                    topic=meta.get("topic", ""),
                    target_url=meta.get("target_url", ""),
                    word_count=meta.get("word_count", 0),
                    created_at=meta.get("created_at", ""),
                    similarity_score=match.score
                ))
        
        return similar
    
    async def list_all(self, limit: int = 50) -> List[ArticleMeta]:
        """
        Lista wszystkich artykułów
        
        Args:
            limit: Maksymalna liczba wyników
            
        Returns:
            Lista metadanych artykułów
        """
        index = self._get_index()
        
        # Pinecone nie ma list all, używamy dummy query
        # Generuj losowy embedding i szukaj top_k
        import random
        dummy_embedding = [random.random() for _ in range(1536)]
        
        results = index.query(
            vector=dummy_embedding,
            top_k=limit,
            include_metadata=True
        )
        
        articles = []
        for match in results.matches:
            meta = match.metadata
            articles.append(ArticleMeta(
                id=match.id,
                title=meta.get("title", ""),
                topic=meta.get("topic", ""),
                target_url=meta.get("target_url", ""),
                word_count=meta.get("word_count", 0),
                created_at=meta.get("created_at", ""),
                similarity_score=0
            ))
        
        # Sortuj po dacie
        articles.sort(key=lambda x: x.created_at, reverse=True)
        
        return articles
    
    async def get(self, article_id: str) -> Optional[Article]:
        """
        Pobiera pełny artykuł
        
        Args:
            article_id: ID artykułu
            
        Returns:
            Artykuł lub None
        """
        # Najpierw sprawdź lokalny plik
        article = self._load_content_locally(article_id)
        if article:
            return article
        
        # Fallback - pobierz z Pinecone (tylko metadata)
        index = self._get_index()
        
        try:
            result = index.fetch(ids=[article_id])
            if article_id in result.vectors:
                meta = result.vectors[article_id].metadata
                return Article(
                    id=article_id,
                    title=meta.get("title", ""),
                    content=meta.get("content_preview", ""),
                    topic=meta.get("topic", ""),
                    target_url=meta.get("target_url", ""),
                    keywords=meta.get("keywords", "").split(","),
                    word_count=meta.get("word_count", 0),
                    created_at=meta.get("created_at", ""),
                    updated_at=meta.get("updated_at", "")
                )
        except Exception:
            pass
        
        return None
    
    async def update(self, article_id: str, content: str) -> bool:
        """
        Aktualizuje treść artykułu
        
        Args:
            article_id: ID artykułu
            content: Nowa treść
            
        Returns:
            True jeśli sukces
        """
        article = await self.get(article_id)
        if not article:
            return False
        
        article.content = content
        article.word_count = len(content.split())
        article.updated_at = datetime.now().isoformat()
        
        await self.store(article)
        return True
    
    async def delete(self, article_id: str) -> bool:
        """Usuwa artykuł"""
        index = self._get_index()
        
        try:
            index.delete(ids=[article_id])
            
            # Usuń też lokalny plik
            filepath = os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "articles",
                f"{article_id}.json"
            )
            if os.path.exists(filepath):
                os.remove(filepath)
            
            return True
        except Exception:
            return False


if __name__ == "__main__":
    import asyncio
    
    async def test():
        storage = ArticleStorage()
        
        # Test store
        article = Article(
            id="",
            title="Jak wybrać hosting WordPress",
            content="Lorem ipsum dolor sit amet...",
            topic="hosting wordpress",
            target_url="https://example.com",
            keywords=["hosting", "wordpress", "porównanie"]
        )
        
        article_id = await storage.store(article)
        print(f"Zapisano artykuł: {article_id}")
        
        # Test find similar
        similar = await storage.find_similar("wybór hostingu dla WordPress")
        print(f"Znaleziono {len(similar)} podobnych artykułów")
        
        # Test list
        all_articles = await storage.list_all()
        print(f"Wszystkich artykułów: {len(all_articles)}")
    
    asyncio.run(test())
