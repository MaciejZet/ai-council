"""
Response Caching System
========================
Redis-based caching for identical queries to reduce API costs
"""

import hashlib
import json
from typing import Optional, Dict, Any
from datetime import timedelta
import asyncio

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from src.utils.logger import setup_logger

logger = setup_logger("ai_council.cache")


class ResponseCache:
    """Cache for AI responses to reduce redundant API calls"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 3600,  # 1 hour
        enabled: bool = True
    ):
        self.enabled = enabled and REDIS_AVAILABLE
        self.default_ttl = default_ttl
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None

        if not REDIS_AVAILABLE and enabled:
            logger.warning("Redis not available. Install with: pip install redis")
            self.enabled = False

    async def connect(self):
        """Connect to Redis"""
        if not self.enabled:
            return

        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.enabled = False
            self.client = None

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()

    def _generate_cache_key(
        self,
        query: str,
        provider: str,
        model: str,
        use_knowledge_base: bool,
        attachment_text: str = ""
    ) -> str:
        """Generate a unique cache key for the query"""
        key_data = {
            "query": query.strip().lower(),
            "provider": provider,
            "model": model,
            "use_kb": use_knowledge_base,
            "attachment": attachment_text[:100] if attachment_text else "",
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()
        return f"ai_council:response:{key_hash}"

    async def get(
        self,
        query: str,
        provider: str,
        model: str,
        use_knowledge_base: bool,
        attachment_text: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response if available

        Returns:
            Cached response data or None if not found
        """
        if not self.enabled or not self.client:
            return None

        try:
            cache_key = self._generate_cache_key(
                query, provider, model, use_knowledge_base, attachment_text
            )
            cached_data = await self.client.get(cache_key)

            if cached_data:
                logger.info(f"Cache HIT for query: {query[:50]}...")
                return json.loads(cached_data)
            else:
                logger.debug(f"Cache MISS for query: {query[:50]}...")
                return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        query: str,
        provider: str,
        model: str,
        use_knowledge_base: bool,
        response_data: Dict[str, Any],
        attachment_text: str = "",
        ttl: Optional[int] = None
    ):
        """
        Cache a response

        Args:
            query: User query
            provider: LLM provider
            model: Model name
            use_knowledge_base: Whether KB was used
            response_data: Response to cache
            attachment_text: Attachment content
            ttl: Time to live in seconds (default: 1 hour)
        """
        if not self.enabled or not self.client:
            return

        try:
            cache_key = self._generate_cache_key(
                query, provider, model, use_knowledge_base, attachment_text
            )
            ttl = ttl or self.default_ttl

            await self.client.setex(
                cache_key,
                ttl,
                json.dumps(response_data)
            )

            logger.info(f"Cached response for query: {query[:50]}... (TTL: {ttl}s)")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def invalidate(self, pattern: str = "ai_council:response:*"):
        """
        Invalidate cache entries matching pattern

        Args:
            pattern: Redis key pattern to match
        """
        if not self.enabled or not self.client:
            return

        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self.client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries")

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled or not self.client:
            return {"enabled": False}

        try:
            info = await self.client.info("stats")
            keys_count = await self.client.dbsize()

            return {
                "enabled": True,
                "total_keys": keys_count,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) /
                    (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                ) * 100,
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}


# Global cache instance
_cache_instance: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    """Get or create the global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ResponseCache()
    return _cache_instance
