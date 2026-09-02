"""Paired A/B eval runner with matched cases and paired statistics (IMP-0197).

Two workflows are scored on the SAME case set; the analysis is the per-case
delta (``score_a - score_b``), never the difference of group means. The runner
archives every paired delta, reports the effect size (raw mean delta and
Cohen's dz) and refuses to issue a verdict when fewer than ``min_n`` complete
pairs exist -- an under-powered run returns ``INSUFFICIENT-EVIDENCE`` with the
deltas still archived, and carries no ``verdict`` key at all.

Scorers are hermetic functions of the case payload, looked up by the
workflow's ``scorer`` name; ``payload_len`` scores the byte length of the
canonical JSON payload plus the workflow's ``offset`` parameter.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Mapping, Sequence

DEFAULT_MIN_N = 20
INSUFFICIENT_EVIDENCE = "INSUFFICIENT-EVIDENCE"
POWERED = "POWERED"
A_BETTER = "A_BETTER"
B_BETTER = "B_BETTER"
TIE = "TIE"
ZERO_EFFECT = "ZERO_EFFECT"
VERDICTS = (A_BETTER, B_BETTER, TIE, ZERO_EFFECT)
RUNNER_ID = "agentspec.evals.paired_ab"
UNIT_ID = "IMP-0197"
GROUP_MEANS_NOTE = "Paired analysis uses per-case delta; do not verdict from group means."

Scorer = Callable[[Mapping[str, Any], Mapping[str, Any]], float]


def _payload(case: Mapping[str, Any]) -> Any:
    if isinstance(case.get("payload"), dict):
        return case["payload"]
    if "text" in case:
        return {"text": case.get("text")}
    return {}


def _offset(wf: Mapping[str, Any]) -> float:
    params = wf.get("params") if isinstance(wf.get("params"), dict) else {}
    return float(params.get("offset") or 0.0)


def score_payload_len(wf: Mapping[str, Any], case: Mapping[str, Any]) -> float:
    """Length of the canonical (compact, sorted) JSON payload, plus ``params.offset``."""
    blob = json.dumps(_payload(case), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return float(len(blob)) + _offset(wf)


def score_text_len(wf: Mapping[str, Any], case: Mapping[str, Any]) -> float:
    """Character length of ``payload.text`` (or ``case.text``), plus ``params.offset``."""
    payload = _payload(case)
    text = payload.get("text") if isinstance(payload, dict) else None
    return float(len(str(text or ""))) + _offset(wf)


SCORERS: dict[str, Scorer] = {
    "payload_len": score_payload_len,
    "text_len": score_text_len,
}
DEFAULT_SCORER = "payload_len"


def resolve_scorer(wf: Mapping[str, Any]) -> Scorer:
    name = str(wf.get("scorer") or DEFAULT_SCORER)
    try:
        return SCORERS[name]
    except KeyError as exc:
        raise ValueError(f"workflow {wf.get('id')!r} names unknown scorer {name!r}") from exc


def _finite(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def cohens_dz(deltas: Sequence[float]) -> dict[str, Any]:
    """Paired effect size: mean delta over the sample SD of the deltas.

    ``value`` is ``None`` (with a ``reason``) when dz is undefined: fewer than
    two pairs, or a zero-variance nonzero mean. All-zero deltas are a real zero
    effect and report ``0.0``.
    """
    n = len(deltas)
    mean = _mean(deltas)
    if n < 2:
        return {"kind": "cohens_dz", "n": n, "mean_delta": mean, "sd_delta": None, "value": None, "reason": "n<2"}
    var = sum((d - mean) ** 2 for d in deltas) / (n - 1)
    sd = math.sqrt(var)
    if all(abs(d) <= 1e-12 for d in deltas):
        return {"kind": "cohens_dz", "n": n, "mean_delta": 0.0, "sd_delta": 0.0, "value": 0.0, "reason": "zero-delta"}
    if sd <= 1e-12:
        return {
            "kind": "cohens_dz",
            "n": n,
            "mean_delta": mean,
            "sd_delta": 0.0,
            "value": None,
            "reason": "zero-variance-nonzero-mean",
        }
    return {"kind": "cohens_dz", "n": n, "mean_delta": mean, "sd_delta": sd, "value": mean / sd, "reason": "ok"}


def decide_verdict(deltas: Sequence[float]) -> str:
    wins_a = sum(1 for d in deltas if d > 0)
    wins_b = sum(1 for d in deltas if d < 0)
    if wins_a == 0 and wins_b == 0:
        return ZERO_EFFECT
    mean = _mean(deltas)
    if wins_a > wins_b and mean > 0:
        return A_BETTER
    if wins_b > wins_a and mean < 0:
        return B_BETTER
    return TIE


def run_paired_ab(
    wf_a: Mapping[str, Any],
    wf_b: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    min_n: int | None = None,
    corpus_id: str | None = None,
) -> dict[str, Any]:
    """Score both workflows on the same cases and analyse the paired deltas."""
    if min_n is None:
        min_n = DEFAULT_MIN_N
    min_n = int(min_n)
    score_a = resolve_scorer(wf_a)
    score_b = resolve_scorer(wf_b)

    rows: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for idx, case in enumerate(cases):
        case_id = case.get("id", f"case-{idx}")
        try:
            sa = _finite(score_a(wf_a, case))
        except Exception as exc:  # a scorer crash is an incomplete pair, not a verdict input
            sa, err_a = None, repr(exc)
        else:
            err_a = None
        try:
            sb = _finite(score_b(wf_b, case))
        except Exception as exc:
            sb, err_b = None, repr(exc)
        else:
            err_b = None
        if sa is None or sb is None:
            incomplete.append(
                {
                    "case_id": case_id,
                    "missing": [arm for arm, s in (("a", sa), ("b", sb)) if s is None],
                    "errors": {k: v for k, v in (("a", err_a), ("b", err_b)) if v},
                }
            )
            continue
        rows.append({"case_id": case_id, "score_a": sa, "score_b": sb, "delta": sa - sb})

    deltas = [r["delta"] for r in rows]
    n = len(rows)
    wins_a = sum(1 for d in deltas if d > 0)
    wins_b = sum(1 for d in deltas if d < 0)
    mean_a = _mean([r["score_a"] for r in rows])
    mean_b = _mean([r["score_b"] for r in rows])
    out: dict[str, Any] = {
        "runner": RUNNER_ID,
        "unit": UNIT_ID,
        "corpus_id": corpus_id,
        "workflow_a_id": wf_a.get("id"),
        "workflow_b_id": wf_b.get("id"),
        "workflow_a": wf_a.get("id"),
        "workflow_b": wf_b.get("id"),
        "n_input": len(cases),
        "n": n,
        "min_n": min_n,
        "same_case_set": True,
        "incomplete": incomplete,
        "paired_deltas": rows,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "effect_size": {
            "raw_mean_delta": _mean(deltas),
            "n": n,
            "cohens_dz": cohens_dz(deltas),
        },
        "diagnostic_unpaired_group_means": {
            "mean_a": mean_a,
            "mean_b": mean_b,
            "mean_a_minus_mean_b": mean_a - mean_b,
            "not_the_analysis": True,
            "note": GROUP_MEANS_NOTE,
        },
    }
    if n < min_n:
        out["status"] = INSUFFICIENT_EVIDENCE
        out["verdict_refused"] = True
        out["refusal_reason"] = f"n={n} complete pairs < min_n={min_n}; no verdict is issued"
        return out
    out["status"] = POWERED
    out["verdict_refused"] = False
    out["refusal_reason"] = None
    out["verdict"] = decide_verdict(deltas)
    return out
