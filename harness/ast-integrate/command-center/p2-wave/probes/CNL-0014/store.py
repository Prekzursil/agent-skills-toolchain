"""Minimum per-participant calibration store. Never invents a score."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "store.schema.json"
SCHEMA_ID = "council-calibration-store/v1"
DEFAULT_MIN_N = 1

_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def empty_store(min_resolved_n: int = DEFAULT_MIN_N) -> dict[str, Any]:
    if min_resolved_n < 1:
        raise ValueError("min_resolved_n must be >= 1")
    return {
        "schema_id": SCHEMA_ID,
        "min_resolved_n": int(min_resolved_n),
        "records": [],
    }


def scoreable_outcomes(outcomes: list[dict]) -> list[dict]:
    return [o for o in outcomes if o.get("resolution") == "SCOREABLE"]


def brier_of(outcomes: list[dict]) -> float | None:
    scored = scoreable_outcomes(outcomes)
    if not scored:
        return None
    total = 0.0
    for o in scored:
        y = 1.0 if o["resolved_correct"] is True else 0.0
        p = float(o["stated_confidence"])
        total += (p - y) ** 2
    return total / len(scored)


def derive(outcomes: list[dict], min_resolved_n: int) -> tuple[int, bool, float | None, str]:
    n = len(scoreable_outcomes(outcomes))
    if n < min_resolved_n:
        return n, False, None, "UNRANKABLE"
    score = brier_of(outcomes)
    return n, True, score, "RANK_ELIGIBLE"


def _key(participant_id: str, task_class: str) -> tuple[str, str]:
    return participant_id, task_class


def find_record(store: dict, participant_id: str, task_class: str) -> dict | None:
    for rec in store["records"]:
        if rec["participant_id"] == participant_id and rec["task_class"] == task_class:
            return rec
    return None


def resolved_n(store: dict, participant_id: str, task_class: str) -> int:
    rec = find_record(store, participant_id, task_class)
    if rec is None:
        return 0
    return len(scoreable_outcomes(rec["outcomes"]))


def observe_candidate(store: dict, participant_id: str, task_class: str) -> dict:
    """Cold-start insert: identity row, no invented score."""
    existing = find_record(store, participant_id, task_class)
    if existing is not None:
        return existing
    n, scoreable, brier, rank_class = derive([], store["min_resolved_n"])
    rec = {
        "participant_id": participant_id,
        "task_class": task_class,
        "resolved_n": n,
        "outcomes": [],
        "scoreable": scoreable,
        "brier": brier,
        "rank_class": rank_class,
    }
    store["records"].append(rec)
    return rec


def append_outcome(store: dict, participant_id: str, task_class: str, outcome: dict) -> dict:
    rec = observe_candidate(store, participant_id, task_class)
    resolution = outcome["resolution"]
    if resolution == "SCOREABLE":
        if outcome.get("resolved_correct") not in (True, False):
            raise ValueError("SCOREABLE outcome requires boolean resolved_correct")
        if not outcome.get("resolution_source"):
            raise ValueError("SCOREABLE outcome requires resolution_source")
    elif resolution == "UNSCOREABLE":
        if outcome.get("resolved_correct") is not None:
            raise ValueError("UNSCOREABLE outcome must not carry resolved_correct")
    else:
        raise ValueError(f"unknown resolution {resolution!r}")
    rec["outcomes"].append(copy.deepcopy(outcome))
    n, scoreable, brier, rank_class = derive(rec["outcomes"], store["min_resolved_n"])
    rec["resolved_n"] = n
    rec["scoreable"] = scoreable
    rec["brier"] = brier
    rec["rank_class"] = rank_class
    return rec


def validate_store(store: dict) -> list[str]:
    """Schema plus invariants jsonschema cannot see (min_n vs resolved_n)."""
    errors: list[str] = []
    try:
        jsonschema.Draft7Validator(_SCHEMA).validate(store)
    except jsonschema.ValidationError as exc:
        errors.append(f"schema:{exc.message}")
        return errors
    min_n = store["min_resolved_n"]
    seen: set[tuple[str, str]] = set()
    for rec in store["records"]:
        k = _key(rec["participant_id"], rec["task_class"])
        if k in seen:
            errors.append(f"duplicate-record:{k[0]}/{k[1]}")
        seen.add(k)
        n = len(scoreable_outcomes(rec["outcomes"]))
        if rec["resolved_n"] != n:
            errors.append(
                f"resolved_n-mismatch:{rec['participant_id']} stored={rec['resolved_n']} counted={n}"
            )
        want_n, want_s, want_b, want_c = derive(rec["outcomes"], min_n)
        if rec["scoreable"] != want_s or rec["rank_class"] != want_c:
            errors.append(f"derived-mismatch:{rec['participant_id']}")
        if rec["brier"] is None and want_b is not None:
            errors.append(f"missing-brier:{rec['participant_id']}")
        if rec["brier"] is not None and want_b is None:
            errors.append(f"INVENTED_SCORE:{rec['participant_id']}")
        if rec["brier"] is not None and want_b is not None:
            if abs(float(rec["brier"]) - float(want_b)) > 1e-12:
                errors.append(f"brier-mismatch:{rec['participant_id']}")
        if n == 0 and rec["brier"] is not None:
            errors.append(f"INVENTED_SCORE_ZERO_HISTORY:{rec['participant_id']}")
        if n < min_n and rec["rank_class"] == "RANK_ELIGIBLE":
            errors.append(f"ZERO_HISTORY_MARKED_ELIGIBLE:{rec['participant_id']}")
        if want_n != n:
            errors.append(f"count-drift:{rec['participant_id']}")
    return errors


def planted_invented_average_store(base: dict, participant_id: str, task_class: str) -> dict:
    """Known-broken store: writes 0.5 as if it were a measured Brier."""
    bad = copy.deepcopy(base)
    rec = observe_candidate(bad, participant_id, task_class)
    rec["brier"] = 0.5
    rec["scoreable"] = True
    rec["rank_class"] = "RANK_ELIGIBLE"
    rec["resolved_n"] = 0
    return bad
