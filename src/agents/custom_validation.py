"""
Validation for custom agent configs: tools, context limits, name uniqueness.
"""

import re
from typing import List, Tuple

# Logical tools (not only plugin ids — knowledge_base is virtual)
ALLOWED_CUSTOM_TOOLS = frozenset(
    {
        "knowledge_base",
        "web_search",
        "tavily",
        "duckduckgo",
        "url_analyzer",
        "wikipedia",
        "weather",
        "stocks",
        "calculator",
        "datetime",
        "hash",
        "converter",
        "random",
        "text",
    }
)

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_]+$")


def validate_agent_name(name: str) -> Tuple[bool, str]:
    stripped = name.strip()
    if len(stripped) < 1 or len(stripped) > 100:
        return False, "Name length must be 1–100 characters"
    if not _NAME_PATTERN.match(stripped):
        return False, "Name must contain only letters, numbers, spaces, dashes, and underscores"
    return True, ""


def validate_context_limit(limit: int) -> Tuple[bool, str]:
    if limit < 500:
        return False, "context_limit must be at least 500"
    if limit > 200_000:
        return False, "context_limit cannot exceed 200000"
    return True, ""


def validate_tools(tools: List[str]) -> Tuple[bool, str]:
    if len(tools) > 20:
        return False, "At most 20 tools allowed"
    unknown = [t for t in tools if t not in ALLOWED_CUSTOM_TOOLS]
    if unknown:
        return False, f"Unknown tools: {', '.join(unknown)}. Allowed: {', '.join(sorted(ALLOWED_CUSTOM_TOOLS))}"
    return True, ""


def validate_custom_agent_payload(
    name: str,
    tools: List[str],
    context_limit: int,
    existing_names_lower: List[str],
    exclude_name_lower: str | None = None,
) -> Tuple[bool, str]:
    ok, msg = validate_agent_name(name)
    if not ok:
        return False, msg
    ok, msg = validate_tools(tools)
    if not ok:
        return False, msg
    ok, msg = validate_context_limit(context_limit)
    if not ok:
        return False, msg
    n = name.strip().lower()
    for other in existing_names_lower:
        if exclude_name_lower and other == exclude_name_lower:
            continue
        if other == n:
            return False, "An agent with this name already exists"
    return True, ""
