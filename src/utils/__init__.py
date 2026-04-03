"""Update utils __init__ to export all new utilities"""

from .logger import setup_logger, log_api_call, log_agent_response
from .validation import (
    QueryRequest,
    CustomAgentRequest,
    FileUploadValidator,
    validate_api_keys,
    validate_request,
    MAX_QUERY_LENGTH,
    MAX_ATTACHMENT_SIZE,
)
from .rate_limit import RateLimiter, get_rate_limiter
from .cache import ResponseCache, get_cache
from .error_handler import (
    retry_with_backoff,
    timeout,
    ErrorHandler,
    CircuitBreaker,
    CircuitState,
)
from .health import HealthChecker, get_health_checker
from .api_keys import APIKeyManager, get_api_keys_header

__all__ = [
    # Logging
    "setup_logger",
    "log_api_call",
    "log_agent_response",
    # Validation
    "QueryRequest",
    "CustomAgentRequest",
    "FileUploadValidator",
    "validate_api_keys",
    "validate_request",
    "MAX_QUERY_LENGTH",
    "MAX_ATTACHMENT_SIZE",
    # Rate Limiting
    "RateLimiter",
    "get_rate_limiter",
    # Caching
    "ResponseCache",
    "get_cache",
    # Error Handling
    "retry_with_backoff",
    "timeout",
    "ErrorHandler",
    "CircuitBreaker",
    "CircuitState",
    # Health & Monitoring
    "HealthChecker",
    "get_health_checker",
    # API Keys
    "APIKeyManager",
    "get_api_keys_header",
]
