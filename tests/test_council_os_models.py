import pytest

import src.council.council_os_models as models


def test_extract_json_object_accepts_fenced_json():
    payload = models.extract_json_object('```json\n{"verdict":"TEST"}\n```')
    assert payload == {"verdict": "TEST"}


def test_extract_json_object_rejects_non_object_json():
    with pytest.raises(ValueError):
        models.extract_json_object("[1, 2, 3]")


def test_council_verdict_rejects_unknown_vote():
    with pytest.raises(ValueError):
        models.CouncilVerdict(
            verdict="MAYBE",
            recommendation="x",
            confidence=0.5,
            consensus="",
            key_disagreement="",
            minority_report="",
            assumptions=[],
            evidence_gaps=[],
            what_would_change_decision=[],
            next_experiment=None,
        )


def test_decision_vote_values_are_stable():
    assert {vote.value for vote in models.DecisionVote} == {"GO", "NO-GO", "TEST", "DEFER"}


def test_defer_verdict_is_explicit_about_parse_failure():
    verdict = models.defer_verdict("chairman_parse_error")
    assert verdict.verdict == models.DecisionVote.DEFER
    assert "chairman_parse_error" in verdict.evidence_gaps
