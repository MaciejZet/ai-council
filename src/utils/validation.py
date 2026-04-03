"""
Input Validation and Security
==============================
Validates user inputs, prevents injection attacks, enforces limits
"""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator
from fastapi import HTTPException


# Configuration limits
MAX_QUERY_LENGTH = 10000
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB
MAX_HISTORY_ITEMS = 50
ALLOWED_FILE_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}

# Suspicious patterns that might indicate injection attacks
SUSPICIOUS_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"disregard\s+all\s+prior",
    r"forget\s+everything",
    r"system\s*:\s*you\s+are",
    r"<\s*script",
    r"javascript\s*:",
]


class QueryRequest(BaseModel):
    """Validated query request"""
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    provider: str = Field(default="openai", pattern="^(openai|grok|gemini|deepseek|perplexity|openrouter)$")
    model: str = Field(default="gpt-4o", min_length=1, max_length=100)
    use_knowledge_base: bool = Field(default=True)
    chat_mode: bool = Field(default=False)
    attachment_text: str = Field(default="", max_length=MAX_ATTACHMENT_SIZE)
    history: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=MAX_HISTORY_ITEMS)
    # Routing: auto = subset of agents by intent; full = all four core agents
    routing_mode: str = Field(default="auto", pattern="^(auto|full)$")
    # Server-side session persistence (data/sessions)
    persist_session: bool = Field(default=False)
    session_id: Optional[str] = Field(default=None, max_length=128)
    # Quality & KB
    behavior_preset: str = Field(
        default="default",
        pattern="^(default|short|with_sources|kb_only)$",
    )
    enable_critic: bool = Field(default=False)
    enable_weighted_voting: bool = Field(default=False)
    hybrid_search: bool = Field(default=False)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Check for suspicious patterns"""
        v_lower = v.lower()
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, v_lower, re.IGNORECASE):
                raise ValueError(f"Query contains suspicious pattern: {pattern}")
        return v.strip()

    @field_validator("history")
    @classmethod
    def validate_history(cls, v: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Validate history structure (chat UI or role-based)."""
        if v is None:
            return v

        for item in v:
            if not isinstance(item, dict):
                raise ValueError("History items must be dictionaries")
            if "query" in item or "synthesis" in item:
                continue
            if "role" in item and "content" in item:
                if item["role"] not in ["user", "assistant", "system"]:
                    raise ValueError("Invalid role in history")
                continue
            raise ValueError("History items need query/synthesis or role/content fields")

        return v


class CustomAgentRequest(BaseModel):
    """Validated custom agent creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    emoji: str = Field(..., min_length=1, max_length=10)
    role: str = Field(..., min_length=1, max_length=200)
    persona: str = Field(..., min_length=10, max_length=2000)
    system_prompt: str = Field(..., min_length=10, max_length=5000)
    tools: List[str] = Field(default_factory=list, max_length=20)
    context_limit: int = Field(default=8000, ge=1000, le=128000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is alphanumeric with spaces/dashes"""
        if not re.match(r"^[a-zA-Z0-9\s\-_]+$", v):
            raise ValueError("Name must contain only letters, numbers, spaces, dashes, and underscores")
        return v.strip()


class FileUploadValidator:
    """Validates file uploads"""

    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        """Check if file extension is allowed"""
        from pathlib import Path
        ext = Path(filename).suffix.lower()
        return ext in ALLOWED_FILE_EXTENSIONS

    @staticmethod
    def validate_file_size(file_size: int) -> bool:
        """Check if file size is within limits"""
        return file_size <= MAX_ATTACHMENT_SIZE

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove dangerous characters from filename"""
        # Remove path traversal attempts
        filename = filename.replace("..", "").replace("/", "").replace("\\", "")
        # Keep only safe characters
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        return filename


def validate_api_keys() -> Dict[str, bool]:
    """
    Validate that required API keys are present

    Returns:
        Dictionary with provider names and their availability status
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    keys = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "grok": bool(os.getenv("GROK_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "pinecone": bool(os.getenv("PINECONE_API_KEY")),
    }

    return keys


def validate_request(request_data: Dict[str, Any], model_class: BaseModel) -> BaseModel:
    """
    Validate request data against a Pydantic model

    Args:
        request_data: Raw request data
        model_class: Pydantic model class to validate against

    Returns:
        Validated model instance

    Raises:
        HTTPException: If validation fails
    """
    try:
        return model_class(**request_data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
