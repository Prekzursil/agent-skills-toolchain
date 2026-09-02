"""Pin-then-score runner. Refuses mutated or re-pinned registries."""
from __future__ import annotations

import copy
from typing import Any

from predicate import decide, digest_predicate

UNPINNED = "UNPINNED"
PIN_MISMATCH = "PIN_MISMATCH"
REPIN_AFTER_MEASUREMENT = "REPIN_AFTER_MEASUREMENT"
SCORED = "SCORED"


def pin_registry(predicate: dict[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(predicate)
    sha = digest_predicate(body)
    return {
        "predicate": body,
        "pin": {
            "alg": "sha256",
            "canonical": "json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True)",
            "sha256": sha,
            "seq": 0,
            "frozen": True,
            "recorded_before_first_measurement": True,
        },
        "runs": [],
        "next_seq": 1,
    }


def score_registry(
    registry: dict[str, Any],
    fusion: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    pin = (registry.get("pin") or {}) if isinstance(registry, dict) else {}
    pin_sha = pin.get("sha256")
    pred = registry.get("predicate") if isinstance(registry, dict) else None
    if not isinstance(pred, dict) or not pin_sha:
        return {
            "status": "REFUSED",
            "reason": UNPINNED,
            "decision": None,
        }
    live = digest_predicate(pred)
    if live != pin_sha:
        return {
            "status": "REFUSED",
            "reason": PIN_MISMATCH,
            "decision": None,
            "live_sha256": live,
            "pin_sha256": pin_sha,
        }
    runs = list(registry.get("runs") or [])
    if pin.get("frozen") is True and runs:
        recorded = None
        for row in runs:
            if isinstance(row, dict) and row.get("cited_pin_sha256"):
                recorded = row.get("cited_pin_sha256")
                break
        if recorded and recorded != pin_sha:
            return {
                "status": "REFUSED",
                "reason": REPIN_AFTER_MEASUREMENT,
                "decision": None,
                "first_run_pin_sha256": recorded,
                "current_pin_sha256": pin_sha,
            }
    verdict = decide(fusion, sources, pred)
    seq = int(registry.get("next_seq") or (len(runs) + 1))
    rec = {
        "status": SCORED,
        "reason": None,
        "seq": seq,
        "cited_pin_sha256": pin_sha,
        "arm_id": fusion.get("arm_id"),
        "decision": verdict["decision"],
        "per_source": verdict["per_source"],
        "n_sources": verdict["n_sources"],
        "fusion_stage_count": fusion.get("stage_count"),
        "stage_count_excluded": True,
    }
    registry.setdefault("runs", []).append(copy.deepcopy(rec))
    registry["next_seq"] = seq + 1
    return rec
