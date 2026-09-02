"""Charter field -> evaluator binding census and launch gate (IMP-0357).

A council charter is only launchable when every success criterion is BOUND to
a runtime evaluator, SATISFIABLE within that metric's domain and NOT VACUOUS
(able to fail).  The census lists every defect instead of dropping it, and the
launch gate refuses at launch -- never deferring an unsatisfiable-by-construction
criterion to stop time.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

CHARTER_FIELDS = (
    "objective",
    "risk_class",
    "desired_output",
    "consensus_intent",
    "required_outputs",
    "success_criteria",
)

# Bookkeeping keys a charter may carry without an evaluator.
META_FIELDS = ("id", "title", "version", "schema_version")

KNOWN_METRICS = {
    "unique_ideas": "quota.unique_ideas",
    "completeness_score": "outcomes.completeness",
    "calibration": "calibration.report",
}

# Closed value domain of each runtime metric: (low, high).
METRIC_DOMAINS: dict[str, tuple[float, float]] = {
    "unique_ideas": (0.0, math.inf),
    "completeness_score": (0.0, 1.0),
    "calibration": (0.0, 1.0),
}

OPS = (">=", "<=", "==", "!=", ">", "<")
_CRITERION_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*(>=|<=|==|!=|>|<)\s*([-+]?\d+(?:\.\d+)?)\s*$")


@dataclass
class LaunchDecision:
    """Outcome of ``attempt_launch``; ``stage`` is where the decision was made."""

    accepted: bool
    stage: str
    reasons: list[str] = field(default_factory=list)
    census: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"accepted": self.accepted, "stage": self.stage, "reasons": list(self.reasons)}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_criteria(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalise ``success_criteria`` (list of dicts or an ``AND`` string).

    Returns ``(criteria, parse_errors)``; every criterion carries ``metric``,
    ``op``, ``threshold``, ``id`` and ``path`` (its location in the charter).
    """
    criteria: list[dict[str, Any]] = []
    errors: list[str] = []
    if raw is None:
        return criteria, errors
    if isinstance(raw, str):
        clauses = [c for c in re.split(r"\s+AND\s+|\s*&&\s*|\s*;\s*", raw.strip()) if c.strip()]
        for i, clause in enumerate(clauses):
            m = _CRITERION_RE.match(clause)
            if not m:
                errors.append(f"success_criteria[{i}]: cannot parse criterion text {clause!r}")
                continue
            metric, op, thr = m.group(1), m.group(2), float(m.group(3))
            criteria.append(
                {
                    "id": f"c-{i}-{metric}",
                    "metric": metric,
                    "op": op,
                    "threshold": thr,
                    "path": f"success_criteria[{i}]",
                }
            )
        return criteria, errors
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        errors.append(f"success_criteria: unsupported type {type(raw).__name__}")
        return criteria, errors
    for i, row in enumerate(raw):
        path = f"success_criteria[{i}]"
        if isinstance(row, str):
            m = _CRITERION_RE.match(row)
            if not m:
                errors.append(f"{path}: cannot parse criterion text {row!r}")
                continue
            criteria.append(
                {
                    "id": f"c-{i}-{m.group(1)}",
                    "metric": m.group(1),
                    "op": m.group(2),
                    "threshold": float(m.group(3)),
                    "path": path,
                }
            )
            continue
        if not isinstance(row, dict):
            errors.append(f"{path}: criterion must be an object or text, got {type(row).__name__}")
            continue
        criteria.append(
            {
                "id": row.get("id") or f"c-{i}",
                "metric": str(row.get("metric") or ""),
                "op": str(row.get("op") or ""),
                "threshold": row.get("threshold"),
                "path": path,
            }
        )
    return criteria, errors


def _satisfying_bounds(op: str, thr: float) -> tuple[float, bool, float, bool] | None:
    """(low, low_strict, high, high_strict) of the values satisfying ``op thr``."""
    if op == ">=":
        return (thr, False, math.inf, False)
    if op == ">":
        return (thr, True, math.inf, False)
    if op == "<=":
        return (-math.inf, False, thr, False)
    if op == "<":
        return (-math.inf, False, thr, True)
    if op == "==":
        return (thr, False, thr, False)
    return None  # "!=" is handled separately


def _intersect(
    a: tuple[float, bool, float, bool], b: tuple[float, bool, float, bool]
) -> tuple[float, bool, float, bool]:
    lo = max(a[0], b[0])
    lo_strict = (a[1] if a[0] == lo else False) or (b[1] if b[0] == lo else False)
    hi = min(a[2], b[2])
    hi_strict = (a[3] if a[2] == hi else False) or (b[3] if b[2] == hi else False)
    return (lo, lo_strict, hi, hi_strict)


def _is_empty(bounds: tuple[float, bool, float, bool]) -> bool:
    lo, lo_s, hi, hi_s = bounds
    if lo > hi:
        return True
    return lo == hi and (lo_s or hi_s)


def _covers_domain(bounds: tuple[float, bool, float, bool], domain: tuple[float, float]) -> bool:
    lo, lo_s, hi, hi_s = bounds
    d_lo, d_hi = domain
    low_ok = lo < d_lo or (lo == d_lo and not lo_s)
    high_ok = hi > d_hi or (hi == d_hi and not hi_s)
    return low_ok and high_ok


def _fmt(v: float) -> str:
    if v == math.inf:
        return "inf"
    if v == -math.inf:
        return "-inf"
    return str(int(v)) if float(v).is_integer() else str(v)


def evaluate_criterion(op: str, value: float, thr: float) -> bool:
    if op == ">=":
        return value >= thr
    if op == ">":
        return value > thr
    if op == "<=":
        return value <= thr
    if op == "<":
        return value < thr
    if op == "==":
        return value == thr
    if op == "!=":
        return value != thr
    raise ValueError(f"unknown op {op!r}")


def binding_census(charter: dict[str, Any]) -> dict[str, Any]:
    """Bind every charter field and criterion to a runtime evaluator.

    Output lists: ``bound`` (criterion -> evaluator), ``unbound`` (no
    evaluator / unknown field / empty or unparsable criteria), ``unsatisfiable``
    (impossible within the metric domain or contradictory with a sibling) and
    ``vacuous`` (true for every value in the domain, so it can never fail).
    """
    bindings = []
    unbound: list[dict[str, Any]] = []
    for name in CHARTER_FIELDS:
        present = name in charter
        bindings.append({"field": name, "present": present, "evaluator": f"charter.{name}", "path": name})
        if not present:
            unbound.append(
                {
                    "path": name,
                    "field": name,
                    "metric_id": None,
                    "criterion_id": None,
                    "reason": f"charter field {name!r} missing: nothing to bind",
                }
            )
    for key in charter:
        if key not in CHARTER_FIELDS and key not in META_FIELDS:
            unbound.append(
                {
                    "path": key,
                    "field": key,
                    "metric_id": None,
                    "criterion_id": None,
                    "reason": f"unknown charter field {key!r} has no evaluator (fail-closed)",
                }
            )

    criteria, parse_errors = parse_criteria(charter.get("success_criteria"))
    for err in parse_errors:
        unbound.append(
            {
                "path": err.split(":", 1)[0],
                "field": "success_criteria",
                "metric_id": None,
                "criterion_id": None,
                "reason": err,
            }
        )
    if not criteria and not parse_errors:
        unbound.append(
            {
                "path": "success_criteria",
                "field": "success_criteria",
                "metric_id": None,
                "criterion_id": None,
                "reason": "no success criteria: an unevaluable aspiration cannot be bound to any evaluator",
            }
        )

    bound: list[dict[str, Any]] = []
    unsatisfiable: list[dict[str, Any]] = []
    vacuous: list[dict[str, Any]] = []
    per_metric: dict[str, list[dict[str, Any]]] = {}
    for crit in criteria:
        metric = crit["metric"]
        rec = {
            "metric_id": metric,
            "criterion_id": crit["id"],
            "op": crit["op"],
            "threshold": crit["threshold"],
            "field": "success_criteria",
            "path": crit["path"],
        }
        if metric not in KNOWN_METRICS:
            rec["reason"] = f"no evaluator bound for metric {metric}"
            unbound.append(rec)
            continue
        thr = _number(crit["threshold"])
        if crit["op"] not in OPS or thr is None:
            rec["reason"] = (
                f"criterion {crit['id']} on {metric}: op {crit['op']!r} / threshold "
                f"{crit['threshold']!r} not evaluable"
            )
            unbound.append(rec)
            continue
        rec["evaluator"] = KNOWN_METRICS[metric]
        rec["threshold"] = thr
        domain = METRIC_DOMAINS.get(metric, (-math.inf, math.inf))
        dom_txt = f"[{_fmt(domain[0])}, {_fmt(domain[1])}]"
        bounds = _satisfying_bounds(crit["op"], thr)
        if bounds is None:  # "!="
            if thr < domain[0] or thr > domain[1]:
                rec["reason"] = f"{metric} != {_fmt(thr)} holds for every value in domain {dom_txt} (vacuous)"
                vacuous.append(rec)
                continue
            if domain[0] == domain[1] == thr:
                rec["reason"] = f"{metric} != {_fmt(thr)} excludes the whole domain {dom_txt} (unsatisfiable-by-construction)"
                unsatisfiable.append(rec)
                continue
        else:
            within = _intersect(bounds, (domain[0], False, domain[1], False))
            if _is_empty(within):
                rec["reason"] = (
                    f"threshold {_fmt(thr)} outside domain {dom_txt} for {metric}: "
                    f"{metric} {crit['op']} {_fmt(thr)} is unsatisfiable-by-construction"
                )
                unsatisfiable.append(rec)
                continue
            if _covers_domain(bounds, domain):
                rec["reason"] = (
                    f"{metric} {crit['op']} {_fmt(thr)} holds for every value in domain {dom_txt} "
                    "(vacuous: cannot fail)"
                )
                vacuous.append(rec)
                continue
            per_metric.setdefault(metric, []).append({"rec": rec, "bounds": bounds})
        bound.append(rec)

    # Criteria on the same metric must leave a non-empty feasible interval.
    for metric, rows in per_metric.items():
        if len(rows) < 2:
            continue
        domain = METRIC_DOMAINS.get(metric, (-math.inf, math.inf))
        feasible: tuple[float, bool, float, bool] = (domain[0], False, domain[1], False)
        for row in rows:
            feasible = _intersect(feasible, row["bounds"])
        if _is_empty(feasible):
            ids = ", ".join(str(r["rec"]["criterion_id"]) for r in rows)
            for row in rows:
                rec = dict(row["rec"])
                rec["reason"] = (
                    f"criteria on {metric} contradict ({ids}): no value satisfies all of them "
                    "(unsatisfiable-by-construction)"
                )
                unsatisfiable.append(rec)
                if row["rec"] in bound:
                    bound.remove(row["rec"])

    all_bound = bool(bound) and not unbound and not unsatisfiable
    return {
        "bindings": bindings,
        "bound": bound,
        "unbound": unbound,
        "unsatisfiable": unsatisfiable,
        "vacuous": vacuous,
        "all_bound": all_bound,
        "field_count": len(CHARTER_FIELDS),
        "criterion_count": len(criteria),
        "runtime_metrics": sorted(KNOWN_METRICS),
        "gating_failures": list(unbound) + list(unsatisfiable) + list(vacuous),
    }


def attempt_launch(charter: dict[str, Any]) -> LaunchDecision:
    """Launch gate: refuse at launch on ANY unbound, unsatisfiable or vacuous
    criterion (or a charter with nothing measurable to bind)."""
    census = binding_census(charter)
    reasons = [row["reason"] for row in census["gating_failures"]]
    if not census["bound"] and not reasons:
        reasons.append("no bound success criteria: nothing measurable to launch against")
    if reasons:
        return LaunchDecision(accepted=False, stage="launch", reasons=reasons, census=census)
    return LaunchDecision(accepted=True, stage="launch", reasons=[], census=census)


def evaluate_at_stop(charter: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Evaluate bound criteria against a metric snapshot at council stop.

    A charter the launch gate refuses is never evaluated here: the answer
    carries ``stage='launch'`` and ``evaluated=False`` with the launch reasons.
    """
    decision = attempt_launch(charter)
    if not decision.accepted:
        return {
            "evaluated": False,
            "stage": "launch",
            "reasons": list(decision.reasons),
            "all_satisfied": None,
            "results": [],
        }
    results = []
    all_ok = True
    for rec in decision.census["bound"]:
        metric = rec["metric_id"]
        value = _number(snapshot.get(metric))
        if value is None:
            ok = False
            note = f"metric {metric} absent from snapshot"
        else:
            ok = evaluate_criterion(rec["op"], value, float(rec["threshold"]))
            note = f"{metric}={_fmt(value)} {rec['op']} {_fmt(float(rec['threshold']))} -> {ok}"
        all_ok = all_ok and ok
        results.append(
            {
                "criterion_id": rec["criterion_id"],
                "metric_id": metric,
                "evaluator": rec["evaluator"],
                "value": value,
                "satisfied": ok,
                "note": note,
            }
        )
    return {
        "evaluated": True,
        "stage": "stop",
        "reasons": [],
        "all_satisfied": all_ok,
        "results": results,
    }
