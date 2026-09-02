"""Paired A/B eval runner with an under-powered refusal (IMP-0197)."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

DEFAULT_MIN_N = 20
INSUFFICIENT_EVIDENCE = "INSUFFICIENT-EVIDENCE"
VERDICTS = ("A_BETTER", "B_BETTER", "TIE")


def _score(wf: Mapping[str, Any], case: Mapping[str, Any]) -> float:
    payload = case.get("payload") if isinstance(case.get("payload"), dict) else {}
    text = str(payload.get("text") or case.get("text") or "")
    offset = float((wf.get("params") or {}).get("offset") or 0.0)
    return float(len(text)) + offset


def run_paired_ab(wf_a: Mapping[str, Any], wf_b: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], min_n: int | None = None) -> dict[str, Any]:
    if min_n is None:
        min_n = DEFAULT_MIN_N
    rows = []
    for case in cases:
        sa = _score(wf_a, case)
        sb = _score(wf_b, case)
        rows.append(
            {
                "case_id": case.get("id"),
                "score_a": sa,
                "score_b": sb,
                "delta": sa - sb,
            }
        )
    n = len(rows)
    out: dict[str, Any] = {
        "n": n,
        "min_n": int(min_n),
        "paired_deltas": rows,
        "workflow_a": wf_a.get("id"),
        "workflow_b": wf_b.get("id"),
    }
    if n < int(min_n):
        out["status"] = INSUFFICIENT_EVIDENCE
        out["verdict_refused"] = True
        return out
    wins_a = sum(1 for r in rows if r["delta"] > 0)
    wins_b = sum(1 for r in rows if r["delta"] < 0)
    if wins_a > wins_b:
        verdict = "A_BETTER"
    elif wins_b > wins_a:
        verdict = "B_BETTER"
    else:
        verdict = "TIE"
    mean_delta = sum(r["delta"] for r in rows) / n if n else 0.0
    out["status"] = "POWERED"
    out["verdict"] = verdict
    out["verdict_refused"] = False
    out["wins_a"] = wins_a
    out["wins_b"] = wins_b
    out["effect_size"] = {"raw_mean_delta": mean_delta, "n": n}
    return out
