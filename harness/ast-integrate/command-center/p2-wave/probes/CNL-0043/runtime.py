#!/usr/bin/env python3
"""Executable resolution, scoring, and turn-schedule semantics for P33–P37.

Designed here because 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent and the
inherited catalogue status (R-A09 evidence) is DISCOVERY. As-written fields on
the fixture are null; these definitions are the runtime this unit authors.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FORECASTS = HERE / "fixtures" / "forecasts.json"
PROTOCOLS = HERE / "fixtures" / "protocols.json"

KNOWN_HALT_OPS = frozenset(
    {
        "all",
        "any",
        "forall",
        "resolved",
        "has_submission",
        "lte",
        "gte",
        "completed",
        "scored",
        "signposts_resolved",
        "pairs_resolved_or_queued",
        "true",
    }
)

SCORING_IDS = frozenset(
    {"brier", "brier+ece", "crps", "bradley-terry-logloss", "none-on-narrative"}
)


def load_protocols() -> list[dict]:
    return json.loads(PROTOCOLS.read_text(encoding="utf-8"))["records"]


def load_forecasts() -> dict:
    return json.loads(FORECASTS.read_text(encoding="utf-8"))


def protocol_by_id(pid: str, records: list[dict] | None = None) -> dict:
    recs = records if records is not None else load_protocols()
    for r in recs:
        if r.get("id") == pid:
            return r
    raise KeyError(pid)


def halt_executable(expr: Any) -> tuple[bool, str | None]:
    if expr is None:
        return False, "halt_when_missing"
    if isinstance(expr, str):
        return False, "halt_when_is_prose"
    if not isinstance(expr, dict):
        return False, "halt_when_not_object"
    op = expr.get("op")
    if op not in KNOWN_HALT_OPS:
        return False, f"unknown_halt_op:{op}"
    if op in {"all", "any"}:
        args = expr.get("args")
        if not isinstance(args, list) or not args:
            return False, "halt_compound_empty"
        for a in args:
            ok, why = halt_executable(a)
            if not ok:
                return False, why
        return True, None
    if op == "forall":
        pred = expr.get("pred")
        ok, why = halt_executable(pred)
        if not ok:
            return False, why
        if not expr.get("collection"):
            return False, "forall_collection_missing"
        return True, None
    return True, None


def schedule_verdict(proto: dict) -> dict:
    designed = proto.get("designed_turn_schedule") or {}
    turns = designed.get("turns") or []
    asw = proto.get("as_written") or {}
    missing_as_written: list[str] = []
    if not asw.get("resolution_criterion"):
        missing_as_written.append("resolution_criterion")
    if not asw.get("scoring_rule"):
        missing_as_written.append("scoring_rule")
    if not asw.get("turn_schedule"):
        missing_as_written.append("turn_schedule")
    if not turns:
        return {
            "id": proto.get("id"),
            "verdict": "NOT-EXECUTABLE",
            "missing_element": "designed_turn_schedule.turns",
            "as_written_missing": missing_as_written,
            "turn_count": 0,
        }
    for t in turns:
        for k in ("id", "role", "action", "reads", "writes"):
            if k not in t:
                return {
                    "id": proto.get("id"),
                    "verdict": "NOT-EXECUTABLE",
                    "missing_element": f"turn.{t.get('id', '?')}.{k}",
                    "as_written_missing": missing_as_written,
                    "turn_count": len(turns),
                }
        halt = t.get("halt_when")
        if halt is not None:
            ok, why = halt_executable(halt)
            if not ok:
                return {
                    "id": proto.get("id"),
                    "verdict": "NOT-EXECUTABLE",
                    "missing_element": f"turn.{t.get('id')}.halt_when:{why}",
                    "as_written_missing": missing_as_written,
                    "turn_count": len(turns),
                }
    last = turns[-1]
    if last.get("halt_when") is None:
        return {
            "id": proto.get("id"),
            "verdict": "NOT-EXECUTABLE",
            "missing_element": f"turn.{last.get('id')}.halt_when",
            "as_written_missing": missing_as_written,
            "turn_count": len(turns),
        }
    scoring = (proto.get("designed_scoring") or {}).get("id")
    if scoring not in SCORING_IDS:
        return {
            "id": proto.get("id"),
            "verdict": "NOT-EXECUTABLE",
            "missing_element": "designed_scoring.id",
            "as_written_missing": missing_as_written,
            "turn_count": len(turns),
        }
    if not (proto.get("designed_resolution") or {}).get("criterion"):
        return {
            "id": proto.get("id"),
            "verdict": "NOT-EXECUTABLE",
            "missing_element": "designed_resolution.criterion",
            "as_written_missing": missing_as_written,
            "turn_count": len(turns),
        }
    return {
        "id": proto.get("id"),
        "verdict": "EXECUTABLE",
        "missing_element": None,
        "as_written_missing": missing_as_written,
        "turn_count": len(turns),
        "scoring_id": scoring,
    }


def family_schedule_table(family: str = "FORECASTING") -> dict:
    recs = [r for r in load_protocols() if r.get("family") == family]
    rows = [schedule_verdict(r) for r in recs]
    return {
        "family": family,
        "n": len(rows),
        "rows": rows,
        "executable": [r["id"] for r in rows if r["verdict"] == "EXECUTABLE"],
        "not_executable": [r["id"] for r in rows if r["verdict"] != "EXECUTABLE"],
    }


def _nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    if isinstance(v, (list, dict)) and not v:
        return False
    return True


def forecast_issues(forecast: dict, proto: dict | None = None) -> list[str]:
    """Return missing-element tokens. Empty list means RESOLVABLE under designed semantics."""
    issues: list[str] = []
    kind = forecast.get("proposition_kind")
    if kind in {None, "narrative", "undefined"}:
        issues.append("proposition_kind:not-a-resolvable-forecast")
    pid = forecast.get("protocol_id")
    if proto is None and pid:
        try:
            proto = protocol_by_id(str(pid))
        except KeyError:
            issues.append("protocol_id:unknown")
            proto = {}
    scoring = ((proto or {}).get("designed_scoring") or {}).get("id")
    kind = forecast.get("proposition_kind")
    if kind == "narrative":
        return issues or ["proposition_kind:narrative-is-not-a-forecast"]
    if scoring == "none-on-narrative" and kind == "narrative":
        issues.append("scenario-narrative-unresolvable")
    if kind in {"binary", "multinomial", "signpost"}:
        space = forecast.get("outcome_space")
        if not isinstance(space, list) or len(space) < 2:
            issues.append("outcome_space")
        pv = forecast.get("probability_vector")
        if not isinstance(pv, dict) or not pv:
            issues.append("probability_vector")
        if not _nonempty(forecast.get("resolution_source")):
            issues.append("resolution_source")
        if not _nonempty(forecast.get("resolution_time")):
            issues.append("resolution_time")
    elif kind == "scalar":
        if not _nonempty(forecast.get("actual_accessor")):
            issues.append("actual_accessor")
        bins = forecast.get("bins")
        edges = forecast.get("bin_edges")
        if not isinstance(bins, dict) or not bins:
            issues.append("bins")
        if not isinstance(edges, list) or len(edges) < 2:
            issues.append("bin_edges")
        status = forecast.get("item_status")
        if status not in {"completed", "resolved"}:
            issues.append("item_status:not-completed")
        if forecast.get("actual") is None and status in {"completed", "resolved"}:
            issues.append("actual")
    elif kind == "pairwise-outcome":
        pair = forecast.get("pair")
        if not (isinstance(pair, list) and len(pair) == 2):
            issues.append("pair")
        has_obs = _nonempty(forecast.get("observed_choice"))
        has_gt = _nonempty(forecast.get("ground_truth_winner")) or isinstance(
            forecast.get("ground_truth_ranking"), list
        )
        if not has_obs and not has_gt:
            issues.append("observed_choice_or_ground_truth")
        pv = forecast.get("probability_vector")
        if not isinstance(pv, dict) or not pv:
            issues.append("probability_vector")
    elif kind not in {None, "narrative", "undefined"}:
        issues.append(f"proposition_kind:unsupported:{kind}")
    return issues


def classify_forecasts(blob: dict | None = None) -> dict:
    data = blob if blob is not None else load_forecasts()
    recs = load_protocols()
    by_id = {r["id"]: r for r in recs if "id" in r}
    rows = []
    for f in data.get("forecasts") or []:
        proto = by_id.get(str(f.get("protocol_id")))
        issues = forecast_issues(f, proto)
        rows.append(
            {
                "id": f.get("id"),
                "protocol_id": f.get("protocol_id"),
                "planted": bool(f.get("planted_bad")),
                "resolvable": not issues,
                "issues": issues,
            }
        )
    unres = [r["id"] for r in rows if not r["resolvable"]]
    res = [r["id"] for r in rows if r["resolvable"]]
    return {
        "n": len(rows),
        "rows": rows,
        "resolvable_ids": res,
        "unresolvable_ids": unres,
        "unresolvable_count": len(unres),
        "resolvable_count": len(res),
    }


def brier(prob: dict, outcome: str, space: list[str]) -> float:
    s = 0.0
    for k in space:
        p = float(prob.get(k, 0.0))
        y = 1.0 if k == outcome else 0.0
        s += (p - y) ** 2
    return s


def ece(items: list[dict], n_bins: int = 5) -> float:
    """Expected calibration error over [0,1] confidence = max probability."""
    if not items:
        return 0.0
    bins: list[list[dict]] = [[] for _ in range(n_bins)]
    for it in items:
        conf = max(float(x) for x in it["probability_vector"].values())
        idx = min(n_bins - 1, int(conf * n_bins))
        bins[idx].append(it)
    acc_gap = 0.0
    n = len(items)
    for b in bins:
        if not b:
            continue
        confs = []
        hits = []
        for it in b:
            pv = it["probability_vector"]
            conf = max(float(x) for x in pv.values())
            pred = max(pv, key=lambda k, m=pv: m[k])
            confs.append(conf)
            hits.append(1.0 if pred == it["resolved_outcome"] else 0.0)
        acc_gap += (len(b) / n) * abs(sum(hits) / len(b) - sum(confs) / len(b))
    return acc_gap


def crps_histogram(bin_edges: list[float], bins: dict, actual: float) -> float:
    """CRPS for a histogram on [edges[0], edges[-1]] with mass `bins` keyed by labels."""
    labels = list(bins.keys())
    if len(labels) != len(bin_edges) - 1:
        raise ValueError("bins/edges length mismatch")
    masses = [float(bins[lab]) for lab in labels]
    total = sum(masses)
    if total <= 0:
        raise ValueError("empty mass")
    masses = [m / total for m in masses]
    acc = 0.0
    cdf = 0.0
    for i, mass in enumerate(masses):
        lo, hi = float(bin_edges[i]), float(bin_edges[i + 1])
        width = hi - lo
        if width <= 0:
            raise ValueError("non-increasing edges")
        # Integrate (F(x) - 1_{x>=actual})^2 over [lo, hi].
        # F is constant cdf before this bin, then jumps by mass (piecewise constant).
        # Use piecewise-linear CDF inside the bin (uniform within bin).
        def integ(f0: float, f1: float, a: float, b: float, t: float) -> float:
            # F(x) = f0 + (f1-f0)*(x-a)/(b-a) on [a,b]; indicator 1_{x>=t}
            if b <= a:
                return 0.0
            slope = (f1 - f0) / (b - a)

            def antideriv(x: float, target: float) -> float:
                # int (f0 + slope*(u-a) - target)^2 du
                c = f0 - target - slope * a
                return (c**2) * x + c * slope * x * x + (slope**2) * (x**3) / 3.0

            if t <= a:
                # indicator 1 everywhere
                return antideriv(b, 1.0) - antideriv(a, 1.0)
            if t >= b:
                return antideriv(b, 0.0) - antideriv(a, 0.0)
            return (antideriv(t, 0.0) - antideriv(a, 0.0)) + (
                antideriv(b, 1.0) - antideriv(t, 1.0)
            )

        acc += integ(cdf, cdf + mass, lo, hi, actual)
        cdf += mass
    return acc


def bt_logloss(prob: dict, winner: str) -> float:
    p = float(prob.get(winner, 0.0))
    p = min(1.0 - 1e-12, max(1e-12, p))
    return -math.log(p)


def score_forecast(forecast: dict, proto: dict | None = None) -> dict:
    issues = forecast_issues(forecast, proto)
    if issues:
        return {"id": forecast.get("id"), "scored": False, "issues": issues}
    kind = forecast.get("proposition_kind")
    pid = forecast.get("protocol_id")
    proto = proto or protocol_by_id(str(pid))
    sid = (proto.get("designed_scoring") or {}).get("id")
    if kind in {"binary", "multinomial", "signpost"}:
        val = brier(
            forecast["probability_vector"],
            str(forecast["resolved_outcome"]),
            list(forecast["outcome_space"]),
        )
        return {
            "id": forecast.get("id"),
            "scored": True,
            "rule": sid,
            "brier": val,
        }
    if kind == "scalar":
        val = crps_histogram(
            [float(x) for x in forecast["bin_edges"]],
            forecast["bins"],
            float(forecast["actual"]),
        )
        return {
            "id": forecast.get("id"),
            "scored": True,
            "rule": sid,
            "crps": val,
        }
    if kind == "pairwise-outcome":
        winner = forecast.get("ground_truth_winner") or forecast.get(
            "observed_choice"
        )
        val = bt_logloss(forecast["probability_vector"], str(winner))
        return {
            "id": forecast.get("id"),
            "scored": True,
            "rule": sid,
            "logloss": val,
        }
    return {"id": forecast.get("id"), "scored": False, "issues": ["unscored-kind"]}


def both_states() -> dict:
    """FIRES on planted-bad forecasts; SILENT on known-good. Recorded verbatim."""
    data = load_forecasts()
    good = {"forecasts": [f for f in data["forecasts"] if not f.get("planted_bad")]}
    bad = {"forecasts": [f for f in data["forecasts"] if f.get("planted_bad")]}
    g = classify_forecasts(good)
    b = classify_forecasts(bad)
    silent_on_good = g["unresolvable_count"] == 0
    fires_on_bad = b["unresolvable_count"] > 0
    return {
        "silent_on_good": silent_on_good,
        "fires_on_bad": fires_on_bad,
        "good": {
            "n": g["n"],
            "unresolvable_ids": g["unresolvable_ids"],
            "resolvable_ids": g["resolvable_ids"],
        },
        "bad": {
            "n": b["n"],
            "unresolvable_ids": b["unresolvable_ids"],
            "issues_by_id": {r["id"]: r["issues"] for r in b["rows"]},
        },
        "pass": silent_on_good and fires_on_bad,
        "negative_control": (
            "On the planted-bad fixture the resolvability check FIRES: it returns "
            f"unresolvable_ids={b['unresolvable_ids']} with issues "
            f"{ {r['id']: r['issues'] for r in b['rows']} }. "
            "That is the state the check is meant to reject (missing source/time/"
            "completion/ground-truth, or a scenario narrative treated as a forecast)."
        ),
    }


def family_count_both_states(family: str = "FORECASTING") -> dict:
    recs = load_protocols()
    good_n = sum(1 for r in recs if r.get("family") == family)
    mutant = [dict(r) for r in recs]
    flipped = None
    for r in mutant:
        if r.get("family") == family:
            r["family"] = "PLANTED-MISASSIGN"
            flipped = r.get("id")
            break
    bad_n = sum(1 for r in mutant if r.get("family") == family)
    return {
        "silent_on_good": good_n == 5,
        "fires_on_bad": bad_n != 5,
        "good_n": good_n,
        "bad_n": bad_n,
        "flipped_id": flipped,
        "pass": good_n == 5 and bad_n != 5,
        "negative_control": (
            f"On a planted family-misassignment of {flipped} the census FIRES: "
            f"FORECASTING count becomes {bad_n} (want 5). The check is meant to "
            "reject a member falling through a family mis-assignment."
        ),
    }
