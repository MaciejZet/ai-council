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
        + (0.2 if risk_ok else 0.0)
        + (0.1 if reason_ok else 0.0)
    )
    return score, {
        "critic_ok": critic_ok,
        "weighted_ok": weighted_ok,
        "risk_ok": risk_ok,
        "reason_ok": reason_ok,
        "risk_score": decision.risk_score,
        "reason": decision.reason,
    }


def evaluate_dataset(dataset: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    scores: list[float] = []
    for case in dataset:
        score, details = _score_case(case)
        scores.append(score)
        results.append(
            {
                "id": case["id"],
                "score": round(score, 4),
                **details,
            }
        )
    return mean(scores) if scores else 0.0, results


def main() -> int:
    dataset = _load_json(DATASET_PATH)
    baseline = _load_json(BASELINE_PATH)
    current_score, results = evaluate_dataset(dataset)
    baseline_score = float(baseline.get("score", 0.0))
    tolerance = float(baseline.get("tolerance", 0.0))
    threshold = baseline_score - tolerance

    print(
        json.dumps(
            {
                "current_score": round(current_score, 4),
                "baseline_score": baseline_score,
                "tolerance": tolerance,
                "threshold": round(threshold, 4),
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if current_score >= threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
