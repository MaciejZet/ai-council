"""
Quick Start Integration Example
================================
Shows how to integrate the new utilities into existing code
"""

import asyncio
from datetime import datetime

# Import new utilities
from src.utils.logger import setup_logger, log_api_call, log_agent_response
from src.utils.validation import QueryRequest, validate_api_keys
from src.utils.cache import get_cache
from src.utils.error_handler import retry_with_backoff, timeout, ErrorHandler
from src.utils.health import get_health_checker

# Setup logger
logger = setup_logger("ai_council.example")


# Example 1: Using structured logging
def example_logging():
    """Example of using the new logging system"""
    logger.info("Starting deliberation process")
    logger.debug("Loading agents", extra={"extra_data": {"agent_count": 5}})

    try:
        # Some operation
        result = process_query()
        logger.info("Deliberation completed successfully")
    except Exception as e:
        logger.error(f"Deliberation failed: {e}", exc_info=True)


# Example 2: Using validation
async def example_validation(raw_request: dict):
    """Example of input validation"""
    try:
        # Validate request
        validated = QueryRequest(**raw_request)
        logger.info(f"Valid request: {validated.query[:50]}...")
        return validated
    except Exception as e:
        logger.warning(f"Invalid request: {e}")
        return ErrorHandler.handle_validation_error(e)


# Example 3: Using caching
async def example_caching(query: str, provider: str, model: str):
    """Example of response caching"""
    cache = get_cache()
    await cache.connect()

    # Try to get from cache
    cached = await cache.get(query, provider, model, use_knowledge_base=True)
    if cached:
        logger.info("Cache hit!")
        return cached

    # Process query
    logger.info("Cache miss, processing query...")
    result = await process_query_expensive(query, provider, model)

    # Cache the result
    await cache.set(query, provider, model, True, result, ttl=3600)

    return result


# Example 4: Using retry logic
@retry_with_backoff(max_retries=3, initial_delay=1.0)
@timeout(30.0)
async def example_retry_and_timeout():
    """Example of retry logic with timeout"""
    # This will retry up to 3 times with exponential backoff
    # and timeout after 30 seconds
    response = await call_external_api()
    return response


# Example 5: Using health checks
async def example_health_monitoring():
    """Example of health monitoring"""
    checker = get_health_checker()

    # Record a request
    checker.record_request(tokens_used=1500, cost=0.03)

    # Get metrics
    metrics = checker.get_metrics()
    logger.info(f"System metrics: {metrics}")

    # Check health
    health = await checker.check_health()
    logger.info(f"System health: {health['status']}")


# Example 6: Complete integration
async def example_complete_integration(request_data: dict):
    """Complete example showing all utilities together"""

    # 1. Validate input
    try:
        validated_request = QueryRequest(**request_data)
    except Exception as e:
        return ErrorHandler.handle_validation_error(e)

    # 2. Check cache
    cache = get_cache()
    cached_response = await cache.get(
        validated_request.query,
        validated_request.provider,
        validated_request.model,
        validated_request.use_knowledge_base
    )

    if cached_response:
        logger.info("Returning cached response")
        return cached_response

    # 3. Process with retry logic
    try:
        start_time = datetime.now()

        @retry_with_backoff(max_retries=3)
        @timeout(60.0)
        async def process_with_protection():
            return await process_deliberation(validated_request)

        result = await process_with_protection()

        duration = (datetime.now() - start_time).total_seconds()

        # 4. Log API call
        log_api_call(
            logger,
            provider=validated_request.provider,
            model=validated_request.model,
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            cost=result.get("total_cost", 0.0),
            duration=duration,
            success=True
        )

        # 5. Cache result
        await cache.set(
            validated_request.query,
            validated_request.provider,
            validated_request.model,
            validated_request.use_knowledge_base,
            result
        )

        # 6. Record metrics
        health_checker = get_health_checker()
        health_checker.record_request(
            tokens_used=result.get("total_tokens", 0),
            cost=result.get("total_cost", 0.0)
        )

        return result

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)

        # Record error
        health_checker = get_health_checker()
        health_checker.record_request(error=True)

        return ErrorHandler.handle_api_error(
            e,
            validated_request.provider,
            validated_request.model
        )


# Placeholder functions (replace with actual implementations)
async def process_query():
    pass

async def process_query_expensive(query, provider, model):
    pass

async def call_external_api():
    pass

async def process_deliberation(request):
    pass


if __name__ == "__main__":
    # Example usage
    logger.info("AI Council - Enhanced with production utilities")

    # Check API keys on startup
    api_keys = validate_api_keys()
    logger.info(f"Available providers: {[k for k, v in api_keys.items() if v]}")

    # Run example
    asyncio.run(example_health_monitoring())
