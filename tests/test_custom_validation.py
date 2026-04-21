"""Unit tests for custom agent validation helpers."""

from src.agents.custom_validation import (
    validate_agent_name,
    validate_context_limit,
    validate_custom_agent_payload,
    validate_tools,
)


def test_validate_tools_rejects_unknown() -> None:
    ok, msg = validate_tools(["not_a_registered_tool"])
    assert ok is False
    assert "Unknown tools" in msg


def test_validate_tools_accepts_wikipedia() -> None:
    ok, msg = validate_tools(["wikipedia", "knowledge_base"])
    assert ok is True
    assert msg == ""


def test_validate_context_limit_too_low() -> None:
    ok, msg = validate_context_limit(400)
    assert ok is False
    assert "500" in msg


def test_validate_context_limit_too_high() -> None:
    ok, msg = validate_context_limit(300_000)
    assert ok is False


def test_validate_agent_name_invalid_chars() -> None:
    ok, msg = validate_agent_name("bad<name>")
    assert ok is False


def test_duplicate_name_blocked() -> None:
    ok, err = validate_custom_agent_payload(
        "MyAgent",
        ["wikipedia"],
        8000,
        existing_names_lower=["myagent", "other"],
        exclude_name_lower=None,
    )
    assert ok is False
    assert "already exists" in err


def test_duplicate_allowed_when_updating_same() -> None:
    ok, err = validate_custom_agent_payload(
        "MyAgent",
        ["wikipedia"],
        8000,
        existing_names_lower=["myagent", "other"],
        exclude_name_lower="myagent",
    )
    assert ok is True


def test_new_unique_name_ok() -> None:
    ok, err = validate_custom_agent_payload(
        "Unique Name",
        [],
        5000,
        existing_names_lower=["someone_else"],
        exclude_name_lower=None,
    )
    assert ok is True
