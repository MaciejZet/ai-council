"""
Health Check and Monitoring
============================
System health checks and metrics collection
"""

from typing import Dict, Any, Optional
from datetime import UTC, datetime
import asyncio
import os
from dotenv import load_dotenv

from src.utils.logger import setup_logger
from src.utils.validation import validate_api_keys

logger = setup_logger("ai_council.health")

load_dotenv()


class HealthChecker:
    """System health monitoring"""

    def __init__(self):
        self.start_time = datetime.now(UTC)
        self.request_count = 0
        self.error_count = 0
        self.total_tokens_used = 0
        self.total_cost = 0.0

    async def check_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check

        Returns:
            Health status dictionary
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": (datetime.now(UTC) - self.start_time).total_seconds(),
            "checks": {}
        }

        # Check API keys
        api_keys = validate_api_keys()
        health_status["checks"]["api_keys"] = {
            "status": "ok" if any(api_keys.values()) else "error",
            "available_providers": [k for k, v in api_keys.items() if v],
            "details": api_keys
        }

        # Check Pinecone
        pinecone_status = await self._check_pinecone()
        health_status["checks"]["pinecone"] = pinecone_status

        # Check Redis cache (if available)
        redis_status = await self._check_redis()
        health_status["checks"]["redis"] = redis_status

        # System metrics
        health_status["metrics"] = {
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": (
                self.error_count / self.request_count * 100
                if self.request_count > 0 else 0
            ),
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost, 4),
        }

        # Determine overall status
        if health_status["checks"]["api_keys"]["status"] == "error":
            health_status["status"] = "degraded"

        if health_status["checks"]["pinecone"]["status"] == "error":
            health_status["status"] = "degraded"

        return health_status

    async def _check_pinecone(self) -> Dict[str, Any]:
        """Check Pinecone connection"""
        try:
            api_key = os.getenv("PINECONE_API_KEY")
            index_name = os.getenv("PINECONE_INDEX_NAME")

            if not api_key or not index_name:
                return {
                    "status": "warning",
                    "message": "Pinecone not configured"
                }

            # Try to import and connect
            from pinecone import Pinecone
            pc = Pinecone(api_key=api_key)

            # Check if index exists
            indexes = pc.list_indexes()
            index_exists = any(idx.name == index_name for idx in indexes)

            if index_exists:
                index = pc.Index(index_name)
                stats = index.describe_index_stats()

                return {
                    "status": "ok",
                    "message": "Pinecone connected",
                    "index_name": index_name,
                    "total_vectors": stats.total_vector_count if hasattr(stats, 'total_vector_count') else 0
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Index '{index_name}' not found"
                }

        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connection"""
        try:
            from src.utils.cache import get_cache
            cache = get_cache()

            if not cache.enabled:
                return {
                    "status": "disabled",
                    "message": "Redis caching not enabled"
                }

            if not cache.client:
                await cache.connect()

            if cache.client:
                await cache.client.ping()
                stats = await cache.get_stats()

                return {
                    "status": "ok",
                    "message": "Redis connected",
                    "stats": stats
                }
            else:
                return {
                    "status": "warning",
                    "message": "Redis not available"
                }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "warning",
                "message": "Redis not available"
            }

    def record_request(self, tokens_used: int = 0, cost: float = 0.0, error: bool = False):
        """Record request metrics"""
        self.request_count += 1
        self.total_tokens_used += tokens_used
        self.total_cost += cost

        if error:
            self.error_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        uptime = (datetime.now(UTC) - self.start_time).total_seconds()

        return {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": (
                self.error_count / self.request_count * 100
                if self.request_count > 0 else 0
            ),
            "requests_per_minute": (
                self.request_count / (uptime / 60)
                if uptime > 0 else 0
            ),
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost, 4),
            "avg_tokens_per_request": (
                self.total_tokens_used / self.request_count
                if self.request_count > 0 else 0
            ),
            "avg_cost_per_request": (
                self.total_cost / self.request_count
                if self.request_count > 0 else 0
            ),
        }


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get or create the global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
