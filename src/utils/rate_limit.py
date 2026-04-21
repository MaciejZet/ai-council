"""
Rate Limiting
=============
Prevent abuse and control API costs
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import HTTPException, Request
from src.utils.logger import setup_logger

logger = setup_logger("ai_council.rate_limit")


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(
        self,
        requests_per_minute: int = 20,
        requests_per_hour: int = 100,
        burst_size: int = 5
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size

        # Track requests per client
        self.minute_buckets: Dict[str, list] = defaultdict(list)
        self.hour_buckets: Dict[str, list] = defaultdict(list)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request"""
        # Use IP address as identifier
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _clean_old_requests(self, bucket: list, window_seconds: int):
        """Remove requests older than the time window"""
        cutoff = time.time() - window_seconds
        return [ts for ts in bucket if ts > cutoff]

    async def check_rate_limit(self, request: Request):
        """
        Check if request is within rate limits

        Raises:
            HTTPException: If rate limit exceeded
        """
        client_id = self._get_client_id(request)
        current_time = time.time()

        # Clean old requests
        self.minute_buckets[client_id] = self._clean_old_requests(
            self.minute_buckets[client_id], 60
        )
        self.hour_buckets[client_id] = self._clean_old_requests(
            self.hour_buckets[client_id], 3600
        )

        # Check minute limit
        if len(self.minute_buckets[client_id]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded (minute) for client: {client_id}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
            )

        # Check hour limit
        if len(self.hour_buckets[client_id]) >= self.requests_per_hour:
            logger.warning(f"Rate limit exceeded (hour) for client: {client_id}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.requests_per_hour} requests per hour"
            )

        # Check burst limit
        recent_requests = [
            ts for ts in self.minute_buckets[client_id]
            if ts > current_time - 10  # Last 10 seconds
        ]
        if len(recent_requests) >= self.burst_size:
            logger.warning(f"Burst limit exceeded for client: {client_id}")
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests in short time. Please slow down."
            )

        # Add current request
        self.minute_buckets[client_id].append(current_time)
        self.hour_buckets[client_id].append(current_time)

        logger.debug(f"Rate limit check passed for client: {client_id}")

    def get_stats(self, request: Request) -> Dict[str, int]:
        """Get rate limit stats for a client"""
        client_id = self._get_client_id(request)

        return {
            "requests_last_minute": len(self.minute_buckets[client_id]),
            "requests_last_hour": len(self.hour_buckets[client_id]),
            "minute_limit": self.requests_per_minute,
            "hour_limit": self.requests_per_hour,
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
