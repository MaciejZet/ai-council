"""Regression tests for provider validation and API key decoding."""

import base64
import json

import pytest
from fastapi import HTTPException

from src.utils.api_keys import APIKeyManager
from src.utils.validation import QueryRequest


def test_query_request_accepts_custom_provider() -> None:
    """`custom` provider is exposed by API and must pass input validation."""
    req = QueryRequest(query="Test query", provider="custom", model="local-model")
    assert req.provider == "custom"


def test_decode_api_keys_rejects_non_object_payload() -> None:
    """Encoded API keys must decode to a JSON object, not list/primitive."""
    encoded = base64.b64encode(json.dumps(["openai"]).encode("utf-8")).decode("utf-8")

    with pytest.raises(HTTPException) as exc:
        APIKeyManager.decode_api_keys(encoded)

    assert exc.value.status_code == 400
