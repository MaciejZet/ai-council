import json

import pytest

import src.council.modes as modes_module
from src.council.council_os_models import CouncilOSResult, ProblemProfile, defer_verdict


class FakeCouncilOS:
    def __init__(self, llm):
        self.llm = llm

    async def deliberate(self, query):
        return CouncilOSResult(
            profile=ProblemProfile(
                primary_domain="strategy",
                secondary_domains=["marketing"],
                decision_kind="strategy",
                reversibility="reversible",
                risk_level="medium",
            ),
            routed_experts=["strategy", "marketing", "sales", "operator"],
            memos=[],
            rebuttals=[],
            red_team=None,
            evidence=None,
            verdict=defer_verdict("synthetic_mode_test"),
            knowledge_status_by_expert={},
            errors=[],
        )


def _event_names(events):
    names = []
    for event in events:
        payload = json.loads(event.removeprefix("data: ").strip())
        names.append(payload["event"])
    return names


def test_council_os_mode_is_registered():
    mode = modes_module.get_mode("council_os")
    assert mode is not None
    assert mode.name == "council_os"


@pytest.mark.asyncio
async def test_council_os_mode_stream_emits_sanitized_structured_result(monkeypatch):
    monkeypatch.setattr(modes_module, "CouncilOS", FakeCouncilOS, raising=False)
    mode = modes_module.get_mode("council_os")
    assert mode is not None

    events = [event async for event in mode.run_stream("synthetic question", llm=object())]
    event_names = _event_names(events)
    combined = "".join(events)

    assert event_names == ["mode_start", "council_os_result", "complete"]
    assert '"verdict": "DEFER"' in combined
    assert "PRIVATE_SYNTHETIC_CHUNK" not in combined
    assert "source_inventory" not in combined
