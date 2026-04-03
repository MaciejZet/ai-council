"""
Structured Logging System
==========================
Centralized logging with proper levels, formatting, and context
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for better parsing and analysis"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Setup a logger with both file and console handlers

    Args:
        name: Logger name (usually __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with colored output (UTF-8 encoding for Windows)
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)

        # Set UTF-8 encoding for Windows
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except:
                pass

        logger.addHandler(console_handler)

    # File handler with JSON formatting (UTF-8 encoding)
    if log_to_file:
        log_file = LOGS_DIR / f"{name.replace('.', '_')}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

    return logger


def log_api_call(
    logger: logging.Logger,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost: float,
    duration: float,
    success: bool = True,
    error: Optional[str] = None
):
    """Log API call metrics"""
    extra_data = {
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": cost,
        "duration_seconds": duration,
        "success": success,
    }

    if error:
        extra_data["error"] = error
        logger.error(f"API call failed: {provider}/{model}", extra={"extra_data": extra_data})
    else:
        logger.info(f"API call: {provider}/{model}", extra={"extra_data": extra_data})


def log_agent_response(
    logger: logging.Logger,
    agent_name: str,
    query: str,
    response_length: int,
    duration: float,
    tokens_used: int
):
    """Log agent response metrics"""
    extra_data = {
        "agent": agent_name,
        "query_preview": query[:100] + "..." if len(query) > 100 else query,
        "response_length": response_length,
        "duration_seconds": duration,
        "tokens_used": tokens_used,
    }
    logger.info(f"Agent response: {agent_name}", extra={"extra_data": extra_data})


# Create default loggers
main_logger = setup_logger("ai_council")
api_logger = setup_logger("ai_council.api")
agent_logger = setup_logger("ai_council.agents")
knowledge_logger = setup_logger("ai_council.knowledge")
