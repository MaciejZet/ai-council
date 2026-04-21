from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from src.council.quality_decision import evaluate_quality_mode


ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "quality_eval_dataset.json"
BASELINE_PATH = ROOT / "quality_eval_baseline.json"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _score_case(case: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    decision = evaluate_quality_mode(
        quality_mode=case["quality_mode"],
        query=case["query"],
        full_query=case["query"],
        use_knowledge_base=bool(case["use_knowledge_base"]),
        behavior_preset=case["behavior_preset"],
        chat_mode=bool(case["chat_mode"]),
        has_attachment=bool(case["has_attachment"]),
        manual_critic=bool(case["manual_critic"]),
        manual_weighted_voting=bool(case["manual_weighted_voting"]),
    )

    critic_ok = decision.applied_critic == bool(case["expected_critic"])
    weighted_ok = decision.applied_weighted_voting == bool(case["expected_weighted"])
    risk_ok = float(case["min_risk"]) <= decision.risk_score <= float(case["max_risk"])
    reason_ok = bool(decision.reason)

    score = (
        (0.35 if critic_ok else 0.0)
        + (0.35 if weighted_ok else 0.0)
        + (0.20 if risk_ok else 0.0)
        + (0.10 if reason_ok else 0.0)
    )
    detail = {
        "id": case["id"],
        "category": case["category"],
        "score": round(score, 4),
        "risk_score": decision.risk_score,
        "critic": decision.applied_critic,
        "weighted": decision.applied_weighted_voting,
        "reason": decision.reason,
        "checks": {
            "critic_ok": critic_ok,
            "weighted_ok": weighted_ok,
            "risk_ok": risk_ok,
            "reason_ok": reason_ok,
        },
    }
    return score, detail


def main() -> int:
    dataset = _load_json(DATASET_PATH)
    baseline = _load_json(BASELINE_PATH)
    baseline_score = float(baseline.get("baseline_score", 0.0))
    tolerance = float(baseline.get("regression_tolerance", 0.05))
    fail_threshold = baseline_score * (1.0 - tolerance)

    details: list[dict[str, Any]] = []
    scores: list[float] = []
    for case in dataset:
        score, detail = _score_case(case)
        scores.append(score)
        details.append(detail)

    current_score = mean(scores) if scores else 0.0
    print("== Quality Gate ==")
    print(f"Dataset cases: {len(dataset)}")
    print(f"Current score: {current_score:.4f}")
    print(f"Baseline score: {baseline_score:.4f}")
    print(f"Fail threshold: {fail_threshold:.4f}")
    print("")
    print("Per-case results:")
    for d in details:
        print(
            f"- {d['id']} [{d['category']}]: score={d['score']:.4f}, "
            f"risk={d['risk_score']:.3f}, critic={d['critic']}, weighted={d['weighted']}"
        )

    if current_score < fail_threshold:
        print("")
        print(
            "FAIL: quality regression exceeded tolerance "
            f"({current_score:.4f} < {fail_threshold:.4f})."
        )
        return 1

    if current_score < baseline_score:
        print("")
        print(
            "WARNING: quality score below baseline but within tolerance "
            f"({current_score:.4f} < {baseline_score:.4f})."
        )

    print("")
    print("PASS: quality gate satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
