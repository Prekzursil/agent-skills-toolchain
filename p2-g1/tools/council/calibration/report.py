"""Calibration Brier reports (IMP-0329)."""
from __future__ import annotations

from typing import Any

HAND_COMPUTED_ALICE_N = 12
HAND_COMPUTED_ALICE_BRIER = 0.19
INSUFFICIENT_MARKER = "INSUFFICIENT-DATA"


def hand_computed_predictions() -> list[dict[str, Any]]:
    # Alice n=12 at p=0.8: (p-y)^2 is 0.04 when correct, 0.64 when wrong.
    # squares = 0.04*5 + 0.64 + 0.04*4 + 0.64*2  -> mean 0.19
    alice: list[dict[str, Any]] = []
    for i in range(5):
        alice.append(
            {
                "participant_id": "alice",
                "stated_confidence": 0.8,
                "resolved_correct": True,
                "resolution": "SCOREABLE",
            }
        )
    alice.append(
        {
            "participant_id": "alice",
            "stated_confidence": 0.8,
            "resolved_correct": False,
            "resolution": "SCOREABLE",
        }
    )
    for i in range(4):
        alice.append(
            {
                "participant_id": "alice",
                "stated_confidence": 0.8,
                "resolved_correct": True,
                "resolution": "SCOREABLE",
            }
        )
    for i in range(2):
        alice.append(
            {
                "participant_id": "alice",
                "stated_confidence": 0.8,
                "resolved_correct": False,
                "resolution": "SCOREABLE",
            }
        )
    alice.append(
        {
            "participant_id": "alice",
            "stated_confidence": 0.9,
            "resolved_correct": None,
            "resolution": "UNSCOREABLE",
        }
    )
    bob = [
        {
            "participant_id": "bob",
            "stated_confidence": 0.8,
            "resolved_correct": True,
            "resolution": "SCOREABLE",
        }
        for _ in range(9)
    ]
    cara = [
        {
            "participant_id": "cara",
            "stated_confidence": 0.5,
            "resolved_correct": None,
            "resolution": "UNSCOREABLE",
        }
    ]
    return alice + bob + cara


def _brier(pairs: list[tuple[float, float]]) -> float:
    n = len(pairs)
    return sum((p - y) ** 2 for p, y in pairs) / n


def format_estimate(n: int, brier: float | None) -> str:
    if n < 10 or brier is None:
        return f"{INSUFFICIENT_MARKER}: n={n} not yet meaningful"
    return f"brier={brier:.4f} n={n}"


def is_honest_insufficient(row: dict[str, Any]) -> bool:
    return int(row.get("resolved_n") or 0) < 10 and row.get("brier") is None


def detect_bare_confident_score(row: dict[str, Any]) -> bool:
    n = int(row.get("resolved_n") or 0)
    if n >= 10:
        return False
    if row.get("brier") is None:
        return False
    text = str(row.get("estimate_sentence") or "")
    return INSUFFICIENT_MARKER not in text


def planted_bare_score_record(honest: dict[str, Any]) -> dict[str, Any]:
    planted = dict(honest)
    planted["brier"] = 0.12
    planted["estimate_sentence"] = "brier=0.1200 n=9"
    planted["insufficient_data_marker"] = None
    return planted


def _participant(pid: str, preds: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [p for p in preds if p["participant_id"] == pid]
    scoreable = [p for p in rows if p["resolution"] == "SCOREABLE"]
    pairs = [
        (float(p["stated_confidence"]), 1.0 if p["resolved_correct"] is True else 0.0)
        for p in scoreable
    ]
    n = len(pairs)
    brier = _brier(pairs) if n >= 10 else None
    sentence = format_estimate(n, brier)
    return {
        "participant_id": pid,
        "resolved_n": n,
        "unscoreable_n": sum(1 for p in rows if p["resolution"] != "SCOREABLE"),
        "brier": brier,
        "estimate_status": "MEANINGFUL" if n >= 10 else "INSUFFICIENT",
        "estimate_sentence": sentence,
        "insufficient_data_marker": INSUFFICIENT_MARKER if n < 10 else None,
        "rank_class": "UNRANKABLE" if n < 10 else "RANKABLE",
    }


def generate_report(preds: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    preds = preds or hand_computed_predictions()
    ids = []
    for p in preds:
        if p["participant_id"] not in ids:
            ids.append(p["participant_id"])
    participants = [_participant(pid, preds) for pid in ids]
    store = {
        "records": [
            {
                "participant_id": p["participant_id"],
                "brier": p["brier"],
                "resolved_n": p["resolved_n"],
                "rank_class": p["rank_class"],
            }
            for p in participants
        ]
    }
    return {
        "participants": participants,
        "calibration_store": store,
        "n_participants": len(participants),
    }


def write_calibration_store(path: Any, report: dict[str, Any] | None = None) -> dict[str, Any]:
    import json
    from pathlib import Path

    report = report or generate_report()
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = report.get("calibration_store") if "calibration_store" in report else report
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest
