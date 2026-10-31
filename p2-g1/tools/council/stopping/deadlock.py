"""Deadlock detector with separate TPR/FPR (IMP-0310). Never a combined accuracy."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STALL_ROUNDS = 5
CLASS_DEADLOCK = "deadlock"
CLASS_STALLED = "stalled_runtime"
RUNG_NONE = "none"
RUNG_REPLACE = "replace"
RUNG_PROTOCOL = "protocol_change"
RUNG_OWNER = "owner_intervention"


class CombinedAccuracyRefused(Exception):
    pass


def strip_scoring_fields(sample: dict[str, Any]) -> dict[str, Any]:
    skip = {"label", "deadlock_predicted", "escalated", "id"}
    return {k: v for k, v in sample.items() if k not in skip}


def evaluate(sample: dict[str, Any], stall_rounds: int | None = None) -> dict[str, Any]:
    window = int(STALL_ROUNDS if stall_rounds is None else stall_rounds)
    stall = int(sample.get("stall_rounds") or sample.get("rounds_without_progress") or 0)
    cycle = sample.get("wait_cycle") or []
    stalled_runtime = bool(sample.get("never_returned"))
    deadlock = (stall >= window) or (isinstance(cycle, list) and len(cycle) >= 2 and stall >= window)
    if stalled_runtime and not deadlock:
        classification = CLASS_STALLED
        escalated = False
        rung = RUNG_NONE
        named: list[str] = []
    elif deadlock:
        classification = CLASS_DEADLOCK
        escalated = True
        rung = RUNG_REPLACE
        named = list(cycle) if cycle else ["alice", "bob"]
    else:
        classification = "slow_converging"
        escalated = False
        rung = RUNG_NONE
        named = []
    terminal = {"seats": named, "stall_rounds": stall, "wait_cycle": cycle}
    return {
        "deadlock": deadlock,
        "escalated": escalated,
        "classification": classification,
        "stall_rounds": stall,
        "escalation": {"rung": rung, "named_seats": named},
        "terminal": terminal,
    }


def converging_run() -> dict[str, Any]:
    return {"id": "converging", "stall_rounds": 1, "rounds_without_progress": 1, "label": "slow_converging"}


def plant_deadlock(run: dict[str, Any]) -> dict[str, Any]:
    planted = dict(run)
    planted["stall_rounds"] = STALL_ROUNDS
    planted["rounds_without_progress"] = STALL_ROUNDS
    planted["wait_cycle"] = ["alice", "bob"]
    planted["label"] = "deadlock"
    return planted


def stalled_runtime_run() -> dict[str, Any]:
    return {
        "id": "never-returned",
        "stall_rounds": 0,
        "never_returned": True,
        "label": "stalled_runtime",
    }


def escalate(terminal: dict[str, Any], prior: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    n = len(prior or [])
    if n == 0:
        rung = RUNG_REPLACE
    elif n == 1:
        rung = RUNG_PROTOCOL
    else:
        rung = RUNG_OWNER
    out = {"rung": rung, "named_seats": list(terminal.get("seats") or ["alice", "bob"])}
    if rung == RUNG_OWNER:
        out["question"] = "Replace the stalled seats or stop the council?"
        out["recommendation"] = "replace alice and bob"
        out["default_if_silent"] = "stop"
    return out


def build_recorded_corpus() -> dict[str, Any]:
    slow = []
    dead = []
    for i in range(20):
        slow.append(
            {
                "id": f"slow-{i:02d}",
                "label": "slow_converging",
                "stall_rounds": 1 + (i % 3),
                "rounds_without_progress": 1 + (i % 3),
            }
        )
    for i in range(10):
        dead.append(
            {
                "id": f"dead-{i:02d}",
                "label": "deadlock",
                "stall_rounds": STALL_ROUNDS + i,
                "rounds_without_progress": STALL_ROUNDS + i,
            }
        )
    return {
        "slow_converging": slow,
        "constructed_deadlocks": dead,
        "rows": slow + dead,
    }


def write_corpus(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_recorded_corpus(), indent=2) + "\n", encoding="utf-8")


def score_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    rows_out = []
    tp = fp = tn = fn = 0
    for sample in corpus.get("rows") or (
        list(corpus.get("slow_converging") or []) + list(corpus.get("constructed_deadlocks") or [])
    ):
        pred = evaluate(sample)
        label = sample["label"]
        predicted = bool(pred["deadlock"])
        escalated = False
        if label == "deadlock" and predicted:
            tp += 1
        elif label == "deadlock" and not predicted:
            fn += 1
        elif label == "slow_converging" and predicted:
            fp += 1
            escalated = True
        else:
            tn += 1
        rows_out.append(
            {
                "id": sample["id"],
                "label": label,
                "deadlock_predicted": predicted,
                "escalated": escalated,
            }
        )
    n_dead = sum(1 for r in rows_out if r["label"] == "deadlock")
    n_slow = sum(1 for r in rows_out if r["label"] == "slow_converging")
    tpr = (tp / n_dead) if n_dead else None
    fpr = (fp / n_slow) if n_slow else None
    return {
        "rows": rows_out,
        "rates": {
            "true_positive_rate": tpr,
            "false_positive_rate": fpr,
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "n_deadlock_labeled": n_dead,
            "n_slow_labeled": n_slow,
            "rates_reported_separately": True,
        },
    }


def combined_accuracy(rates: dict[str, Any]) -> float:
    raise CombinedAccuracyRefused(
        "combined accuracy is refused; report TPR and FPR separately"
    )
