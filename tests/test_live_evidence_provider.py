import pytest
from src.council.council_os_models import ProblemProfile
from src.council.live_evidence import (
    TavilyLiveEvidenceProvider,
    canonicalize_live_url,
    plan_live_queries,
    sanitize_live_query,
)
from src.plugins import PluginResult


PROFILE = ProblemProfile(primary_domain="strategy", decision_kind="strategy")


class FakeSearchPlugin:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self._api_key = "fake"

    async def execute(self, query, **kwargs):
        self.calls.append({"query": query, **kwargs})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def ok(*results, answer="IGNORE_ME"):
    return PluginResult(success=True, data={"answer": answer, "results": list(results)}, source="tavily")


def fail():
    return PluginResult(success=False, error="PRIVATE_EXCEPTION_TEXT", source="tavily")


def test_query_redacts_secrets_email_opaque_tokens_and_url_query():
    raw = (
        "Launch? bearer abcdefghijklmnopqrstuvwxyz user@example.com "
        "api_key=SECRET123 https://x.test/a?token=123 "
        + "A" * 60
    )
    clean = sanitize_live_query(raw)
    assert "user@example.com" not in clean
    assert "SECRET123" not in clean
    assert "token=123" not in clean
    assert "A" * 60 not in clean
    assert "https://x.test/a" in clean


def test_planner_is_deterministic_and_caps_at_two():
    first = plan_live_queries("Should we enter Germany?", PROFILE, ["strategic_choice", "growth_loop"])
    second = plan_live_queries("Should we enter Germany?", PROFILE, ["strategic_choice", "growth_loop"])
    assert first == second
    assert 1 <= len(first) <= 2


def test_canonicalization_strips_query_and_fragment():
    canonical, domain = canonicalize_live_url("HTTPS://WWW.Example.COM/path?q=1#frag")
    assert canonical == "https://www.example.com/path"
    assert domain == "example.com"


@pytest.mark.asyncio
async def test_provider_caps_calls_ignores_answer_deduplicates_and_sorts():
    fake = FakeSearchPlugin([
        ok(
            {"title":"A", "url":"https://example.com/a?x=1", "snippet":"one", "score":0.4},
            {"title":"B", "url":"https://other.com/b", "snippet":"two", "score":0.9},
        ),
        ok(
            {"title":"A", "url":"https://example.com/a#again", "snippet":"dup", "score":0.8},
            answer="MUST_NOT_APPEAR",
        ),
    ])
    provider = TavilyLiveEvidenceProvider(search_plugin=fake, enabled=True)
    result = await provider.collect("Should we enter Germany?", PROFILE, ["strategic_choice"])
    assert result.status == "ok"
    assert len(fake.calls) == 2
    assert all(call["max_results"] == 5 for call in fake.calls)
    assert all(call["search_depth"] == "basic" for call in fake.calls)
    assert [x.domain for x in result.sources] == ["other.com", "example.com"]
    dumped = result.model_dump_json()
    assert "MUST_NOT_APPEAR" not in dumped and "IGNORE_ME" not in dumped


@pytest.mark.asyncio
async def test_provider_disabled_when_key_missing():
    provider = TavilyLiveEvidenceProvider(search_plugin=FakeSearchPlugin([]), enabled=False)
    result = await provider.collect("Should we enter Germany?", PROFILE, [])
    assert result.status == "disabled"


@pytest.mark.asyncio
async def test_provider_all_calls_fail_is_unavailable_without_error_text():
    fake = FakeSearchPlugin([fail(), RuntimeError("SECRET_PROVIDER_EXCEPTION")])
    result = await TavilyLiveEvidenceProvider(search_plugin=fake, enabled=True).collect(
        "Should we enter Germany?", PROFILE, []
    )
    assert result.status == "unavailable"
    assert result.error_labels == ["live_evidence_unavailable"]
    assert "SECRET" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_provider_partial_failure_with_source_is_ok():
    fake = FakeSearchPlugin([
        fail(),
        ok({"title":"A", "url":"https://example.com/a", "snippet":"one", "score":0.4}),
    ])
    result = await TavilyLiveEvidenceProvider(search_plugin=fake, enabled=True).collect(
        "Should we enter Germany?", PROFILE, []
    )
    assert result.status == "ok"
    assert result.error_labels == ["partial_search_failure"]


@pytest.mark.asyncio
async def test_provider_no_usable_sources_is_no_matches():
    fake = FakeSearchPlugin([ok({"title":"", "url":"ftp://bad.test/x", "snippet":""}), ok()])
    result = await TavilyLiveEvidenceProvider(search_plugin=fake, enabled=True).collect(
        "Should we enter Germany?", PROFILE, []
    )
    assert result.status == "no_matches"


def test_query_redacts_url_userinfo_credentials():
    clean = sanitize_live_query(
        "Check https://alice:SuperSecret@example.com/path?token=123 before launch"
    )
    assert "alice" not in clean
    assert "SuperSecret" not in clean
    assert "token=123" not in clean
    assert "https://example.com/path" in clean
