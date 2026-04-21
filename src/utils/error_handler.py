"""
Error Handling with Retry Logic
================================
Robust error handling with exponential backoff and circuit breaker
"""

import asyncio
import time
from typing import Callable, TypeVar, Optional, Any
from functools import wraps
from enum import Enum

from src.utils.logger import setup_logger

logger = setup_logger("ai_council.error_handler")

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern implementation"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state for {func.__name__}")
            else:
                raise Exception(f"Circuit breaker OPEN for {func.__name__}")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker CLOSED - service recovered")

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"Circuit breaker OPEN - {self.failure_count} failures")


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    await asyncio.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)

            raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def timeout(seconds: float):
    """
    Decorator to add timeout to async functions

    Args:
        seconds: Timeout in seconds
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(f"Function {func.__name__} timed out after {seconds}s")
                raise TimeoutError(f"{func.__name__} exceeded timeout of {seconds}s")

        return wrapper

    return decorator


class ErrorHandler:
    """Centralized error handling"""

    @staticmethod
    def handle_api_error(e: Exception, provider: str, model: str) -> dict:
        """
        Handle API errors and return structured error response

        Args:
            e: Exception that occurred
            provider: LLM provider name
            model: Model name

        Returns:
            Structured error response
        """
        error_type = type(e).__name__
        error_message = str(e)

        logger.error(f"API error ({provider}/{model}): {error_type} - {error_message}")

        # Map common errors to user-friendly messages
        em_lower = error_message.lower()
        if "rate_limit" in em_lower or "rate limit" in em_lower or "429" in error_message:
            user_message = "Rate limit exceeded. Please try again in a moment."
        elif "authentication" in error_message.lower() or "401" in error_message:
            user_message = "Authentication failed. Please check your API key."
        elif "timeout" in error_message.lower():
            user_message = "Request timed out. Please try again."
        elif "connection" in error_message.lower():
            user_message = "Connection error. Please check your internet connection."
        else:
            user_message = "An error occurred while processing your request."

        return {
            "error": True,
            "error_type": error_type,
            "error_message": error_message,
            "user_message": user_message,
            "provider": provider,
            "model": model,
        }

    @staticmethod
    def handle_validation_error(e: Exception) -> dict:
        """Handle validation errors"""
        logger.warning(f"Validation error: {e}")

        return {
            "error": True,
            "error_type": "ValidationError",
            "error_message": str(e),
            "user_message": "Invalid input. Please check your request and try again.",
        }

    @staticmethod
    def handle_knowledge_base_error(e: Exception) -> dict:
        """Handle knowledge base errors"""
        logger.error(f"Knowledge base error: {e}")

        return {
            "error": True,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "user_message": "Error accessing knowledge base. Proceeding without context.",
        }
