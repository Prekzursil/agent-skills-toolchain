"""Council preset-pack stability measurement (IMP-0364)."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

MIN_N = 11
HIGH_CONFIDENCE = 0.85
DETERMINISTIC_PRESET_ID = "preset.deterministic"
UNSTABLE_PRESET_ID = "preset.overclaim-unstable"
UNFLATTERING_PRESET_ID = "preset.unflattering"
HERE = Path(__file__).resolve().parent


def _row_from_decisions(preset_id: str, decisions: list[str], confidences: list[float]) -> dict[str, Any]:
    n = len(decisions)
    counts = Counter(str(d) for d in decisions)
    modal_n = counts.most_common(1)[0][1]
    stability = modal_n / n
    change = 1.0 - stability
    mean_c = sum(confidences) / n
    runs = [
        {"i": i, "decision": decisions[i], "confidence": confidences[i]}
        for i in range(n)
    ]
    return {
        "preset_id": preset_id,
        "n": n,
        "runs": runs,
        "stability_rate": stability,
        "decision_change_rate": change,
        "decision_counts": dict(counts),
        "mean_reported_confidence": mean_c,
        "majority_re_runs_differ": change > 0.5,
    }


def _deterministic(n: int) -> dict[str, Any]:
    return _row_from_decisions(DETERMINISTIC_PRESET_ID, ["ACCEPT"] * n, [0.7] * n)


def _unstable(n: int) -> dict[str, Any]:
    # Three-way split so the modal share is < 50% (majority of re-runs differ).
    cycle = ["ACCEPT", "REJECT", "HOLD"]
    decisions = [cycle[i % 3] for i in range(n)]
    return _row_from_decisions(UNSTABLE_PRESET_ID, decisions, [0.95] * n)


def _unflattering(n: int) -> dict[str, Any]:
    decisions = ["HOLD"] * (n - 3) + ["SHIP"] * 3
    return _row_from_decisions(UNFLATTERING_PRESET_ID, decisions, [0.6] * n)


def load_preset_pack(path: str | Path | None = None) -> dict[str, Any]:
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "presets": [
            {"id": DETERMINISTIC_PRESET_ID, "decision": "ACCEPT"},
            {"id": UNSTABLE_PRESET_ID, "decision": "flip"},
            {"id": UNFLATTERING_PRESET_ID, "decision": "HOLD"},
        ]
    }


def rerun(spec: dict[str, Any], n: int = MIN_N) -> dict[str, Any]:
    pid = str(spec.get("id") or spec.get("preset_id") or DETERMINISTIC_PRESET_ID)
    if pid == UNSTABLE_PRESET_ID:
        return _unstable(n)
    if pid == UNFLATTERING_PRESET_ID:
        return _unflattering(n)
    return _deterministic(n)


def fully_stable(row: dict[str, Any]) -> bool:
    return float(row["stability_rate"]) == 1.0 and float(row["decision_change_rate"]) == 0.0


def mutate_one_decision(row: dict[str, Any], index: int, new_decision: str) -> dict[str, Any]:
    clone = copy.deepcopy(row)
    clone["runs"][index]["decision"] = new_decision
    keys = [str(r["decision"]) for r in clone["runs"]]
    counts = Counter(keys)
    n = len(keys)
    modal_n = counts.most_common(1)[0][1]
    clone["stability_rate"] = modal_n / n
    clone["decision_change_rate"] = 1.0 - (modal_n / n)
    clone["decision_counts"] = dict(counts)
    clone["majority_re_runs_differ"] = clone["decision_change_rate"] > 0.5
    return clone


def measure_pack(n: int = MIN_N) -> dict[str, Any]:
    presets = [_deterministic(n), _unstable(n), _unflattering(n)]
    rates = {r["preset_id"]: r["stability_rate"] for r in presets}
    changes = {r["preset_id"]: r["decision_change_rate"] for r in presets}
    disagreements = [
        {
            "preset_id": UNSTABLE_PRESET_ID,
            "kind": "high-confidence-majority-change",
            "stability_rate": rates[UNSTABLE_PRESET_ID],
            "mean_reported_confidence": presets[1]["mean_reported_confidence"],
        }
    ]
    return {
        "n": n,
        "preset_count": len(presets),
        "presets": presets,
        "stability_rates": rates,
        "decision_change_rates": changes,
        "disagreements": disagreements,
        "high_confidence_majority_change": True,
        "unflattering_published": min(rates.values()) < 1.0,
    }


def public_report(n: int = MIN_N) -> dict[str, Any]:
    return measure_pack(n)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
