"""Verdict freshness: input-hash and age invalidation for stored registry verdicts.

A stored verdict (quality score, vulnerability verdict, ...) is stamped with a
per-input hash set and the time it was computed.  Two *independent* signals can
turn it STALE:

* the **hash signal** fires when any hashed input differs from the stored hash
  set (it compares hashes only and never consults the clock);
* the **age signal** fires when the record is older than its freshness window
  (it covers inputs the registry cannot hash, such as an advisory database).

A record is VALID only when neither signal fires.  STALE is never rendered as
the stored result on any surface (record, API, summary): every surface goes
through :func:`surface_result` / :func:`enumerate_surfaces`.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

VALID = "VALID"
STALE = "STALE"
HASH_STALE = "hash-stale"
AGE_STALE = "age-stale"
SCHEMA_VERSION = 1

# Stored results that are *not* a passing verdict even when fresh.
FAILING_RESULTS = frozenset({"FAIL", "FAILED", "VULNERABLE", "RED", "ERROR", "BLOCKED"})


class Clock:
    """Injectable clock so freshness windows can be tested deterministically."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        self._now = self._now + delta
        return self._now

    def timestamp(self) -> float:
        return self._now.timestamp()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def hash_inputs(inputs: Mapping[str, Any]) -> dict[str, str]:
    """Return ``{input_name: sha256(canonical JSON of value)}`` for every input."""
    if not isinstance(inputs, Mapping):
        raise TypeError(f"inputs must be a mapping, got {type(inputs).__name__}")
    return {
        str(key): hashlib.sha256(_canonical(inputs[key])).hexdigest()
        for key in sorted(inputs, key=str)
    }


def stamp_verdict(
    *,
    kind: str,
    subject: str,
    result: str,
    inputs: Mapping[str, Any],
    computed_at: float,
    freshness_window_s: float,
    unhashable_inputs: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a stored verdict record carrying its input hashes and freshness window."""
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("kind must be a non-empty string")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject must be a non-empty string")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("result must be a non-empty string")
    if isinstance(computed_at, bool) or not isinstance(computed_at, (int, float)):
        raise TypeError("computed_at must be a POSIX timestamp (number)")
    window = float(freshness_window_s)
    if window <= 0:
        raise ValueError("freshness_window_s must be positive")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "subject": subject,
        "result": result,
        "input_hashes": hash_inputs(inputs),
        "computed_at": float(computed_at),
        "freshness_window_s": window,
        "unhashable_inputs": sorted(str(name) for name in unhashable_inputs),
    }


def changed_inputs(record: Mapping[str, Any], current_inputs: Mapping[str, Any]) -> list[str]:
    """Names of inputs whose hash differs from (or is missing in) the stored set."""
    stored = dict(record["input_hashes"])
    current = hash_inputs(current_inputs)
    changed = set(stored) ^ set(current)
    changed.update(name for name in stored if name in current and stored[name] != current[name])
    return sorted(changed)


def hash_invalidated(record: Mapping[str, Any], current_inputs: Mapping[str, Any]) -> bool:
    """Hash signal: True when the current input hash set differs from the stored one."""
    return hash_inputs(current_inputs) != dict(record["input_hashes"])


def record_age_s(record: Mapping[str, Any], now: float) -> float:
    return float(now) - float(record["computed_at"])


def age_invalidated(record: Mapping[str, Any], now: float) -> bool:
    """Age signal: True when the record is older than its freshness window."""
    return record_age_s(record, now) > float(record["freshness_window_s"])


def evaluate_freshness(
    record: Mapping[str, Any], current_inputs: Mapping[str, Any], now: float
) -> dict[str, Any]:
    """Combine both signals; ``reasons`` lists which ones fired (empty when VALID)."""
    hash_signal = STALE if hash_invalidated(record, current_inputs) else VALID
    age_signal = STALE if age_invalidated(record, now) else VALID
    reasons: list[str] = []
    if hash_signal == STALE:
        reasons.append(HASH_STALE)
    if age_signal == STALE:
        reasons.append(AGE_STALE)
    return {
        "subject": record["subject"],
        "kind": record["kind"],
        "freshness": STALE if reasons else VALID,
        "hash_signal": hash_signal,
        "age_signal": age_signal,
        "reasons": reasons,
        "changed_inputs": changed_inputs(record, current_inputs) if hash_signal == STALE else [],
        "age_s": record_age_s(record, now),
        "freshness_window_s": float(record["freshness_window_s"]),
    }


def surface_result(record: Mapping[str, Any], current_inputs: Mapping[str, Any], now: float) -> str:
    """The only result any surface may show: the stored result when VALID, else STALE."""
    evaluation = evaluate_freshness(record, current_inputs, now)
    return STALE if evaluation["freshness"] == STALE else str(record["result"])


def age_sweep(records: Sequence[Mapping[str, Any]], now: float) -> list[dict[str, Any]]:
    """Return one row per record whose age signal fires at ``now`` (hashes untouched)."""
    rows: list[dict[str, Any]] = []
    for record in records:
        if age_invalidated(record, now):
            rows.append(
                {
                    "subject": record["subject"],
                    "kind": record["kind"],
                    "reason": AGE_STALE,
                    "age_s": record_age_s(record, now),
                    "freshness_window_s": float(record["freshness_window_s"]),
                    "computed_at": float(record["computed_at"]),
                }
            )
    return rows


def _row(record: Mapping[str, Any], current_inputs: Mapping[str, Any], now: float) -> dict[str, Any]:
    evaluation = evaluate_freshness(record, current_inputs, now)
    stored = str(record["result"])
    return {
        "subject": record["subject"],
        "kind": record["kind"],
        "stored_result": stored,
        "result_shown": STALE if evaluation["freshness"] == STALE else stored,
        "freshness": evaluation["freshness"],
        "reasons": evaluation["reasons"],
        "hash_signal": evaluation["hash_signal"],
        "age_signal": evaluation["age_signal"],
    }


def summary_view(
    records: Sequence[Mapping[str, Any]],
    inputs_by_subject: Mapping[str, Mapping[str, Any]],
    now: float,
) -> dict[str, Any]:
    """Cohort summary: STALE records are counted as stale, never as pass."""
    rows: list[dict[str, Any]] = []
    for record in records:
        subject = record["subject"]
        if subject not in inputs_by_subject:
            raise KeyError(f"no current inputs supplied for {subject}")
        rows.append(_row(record, inputs_by_subject[subject], now))
    fresh = [row for row in rows if row["freshness"] == VALID]
    return {
        "total": len(rows),
        "pass": sum(1 for row in fresh if row["stored_result"].upper() not in FAILING_RESULTS),
        "fail": sum(1 for row in fresh if row["stored_result"].upper() in FAILING_RESULTS),
        "stale": sum(1 for row in rows if row["freshness"] == STALE),
        "rows": rows,
    }


def enumerate_surfaces(
    record: Mapping[str, Any], current_inputs: Mapping[str, Any], now: float
) -> dict[str, Any]:
    """Render one record on every surface (record view, API, summary) from one evaluation."""
    row = _row(record, current_inputs, now)
    summary = summary_view([record], {record["subject"]: current_inputs}, now)
    return {
        "surface_result": row["result_shown"],
        "record": row,
        "api": {
            "subject": row["subject"],
            "kind": row["kind"],
            "verdict": row["result_shown"],
            "freshness": row["freshness"],
            "reasons": row["reasons"],
        },
        "summary": {
            "total": summary["total"],
            "pass": summary["pass"],
            "fail": summary["fail"],
            "stale": summary["stale"],
        },
    }


__all__ = [
    "AGE_STALE",
    "Clock",
    "FAILING_RESULTS",
    "HASH_STALE",
    "SCHEMA_VERSION",
    "STALE",
    "VALID",
    "age_invalidated",
    "age_sweep",
    "changed_inputs",
    "enumerate_surfaces",
    "evaluate_freshness",
    "hash_inputs",
    "hash_invalidated",
    "record_age_s",
    "stamp_verdict",
    "summary_view",
    "surface_result",
]
