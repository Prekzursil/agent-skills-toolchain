"""Compare per-workflow estimates to measured runs.

MAPE and bias use MEASURED rows only. A workflow with no run is NOT-CHECKED
and is never treated as error 0. Cost uses tokens_cumulative, never last-turn.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from statistics import mean

from corpus import hermetic_workflows, live_workflow_files, production_inputs
from estimator import estimate_workflow
from ledger import (
    ACCOUNTING_SOURCE_ABSENT_ESTIMATOR,
    ACCOUNTING_SOURCE_MEASURED,
    ACCOUNTING_SOURCE_NO_RUN,
    CUMULATIVE_FIELD,
    LAST_TURN_FIELD,
    RATE_SOURCE,
    USD_PER_TOKEN,
    cost_usd,
)
from runner import run_workflow

BIAS_EPS = 0.05
OOM_RATIO = 10.0


def signed_pct(estimate: float, actual: float) -> float | None:
    if actual == 0:
        return None
    return (estimate - actual) / abs(actual)


def mape_pct(pairs: list[tuple[float, float]]) -> float | None:
    vals = []
    for est, act in pairs:
        sp = signed_pct(est, act)
        if sp is None:
            continue
        vals.append(abs(sp))
    if not vals:
        return None
    return mean(vals) * 100.0


def bias_direction(pairs: list[tuple[float, float]]) -> str:
    vals = []
    for est, act in pairs:
        sp = signed_pct(est, act)
        if sp is None:
            continue
        vals.append(sp)
    if not vals:
        return "NOT-CHECKED"
    m = mean(vals)
    if m < -BIAS_EPS:
        return "LOW"
    if m > BIAS_EPS:
        return "HIGH"
    return "UNBIASED"


def mean_signed(pairs: list[tuple[float, float]]) -> float | None:
    vals = [signed_pct(e, a) for e, a in pairs if signed_pct(e, a) is not None]
    if not vals:
        return None
    return mean(vals)


def _error_block(est: dict, obs: dict) -> dict:
    cost_sp = signed_pct(est["cost_usd"], obs["cost_usd"])
    tok_sp = signed_pct(est["tokens_cumulative"], obs["tokens_cumulative"])
    time_sp = signed_pct(est["wall_clock_s"], obs["wall_clock_s"])
    cost_ratio = (
        obs["cost_usd"] / est["cost_usd"] if est["cost_usd"] else None
    )
    tok_ratio = (
        obs["tokens_cumulative"] / est["tokens_cumulative"]
        if est["tokens_cumulative"]
        else None
    )
    oom_cost = bool(
        est["cost_usd"] > 0 and obs["cost_usd"] > OOM_RATIO * est["cost_usd"]
    )
    return {
        "cost_signed_pct": cost_sp,
        "cost_abs_pct": None if cost_sp is None else abs(cost_sp) * 100.0,
        "tokens_signed_pct": tok_sp,
        "tokens_abs_pct": None if tok_sp is None else abs(tok_sp) * 100.0,
        "time_signed_pct": time_sp,
        "time_abs_pct": None if time_sp is None else abs(time_sp) * 100.0,
        "actual_over_estimate_cost": cost_ratio,
        "actual_over_estimate_tokens": tok_ratio,
        "order_of_magnitude_cost": oom_cost,
        "observed_writes_subset_of_estimate": set(obs.get("writes") or []).issubset(
            set(est.get("blast_radius") or [])
        ),
    }


def measure_hermetic(work_root: Path | None = None) -> dict:
    own_tmp = None
    if work_root is None:
        own_tmp = tempfile.TemporaryDirectory(prefix="cnf0081-")
        work_root = Path(own_tmp.name)
    try:
        rows = []
        for wf in hermetic_workflows():
            est = estimate_workflow(wf)
            obs = run_workflow(wf, work_root=work_root / wf["id"])
            if obs is None:
                rows.append(
                    {
                        "id": wf["id"],
                        "status": "NOT-CHECKED",
                        "accounting_source": ACCOUNTING_SOURCE_NO_RUN,
                        "source_class": "hermetic-eval",
                        "source_path": wf["_source_path"],
                        "estimate": est,
                        "observed": None,
                        "error": None,
                        "reason": "no measured run (skip_run); not assumed accurate",
                    }
                )
                continue
            err = _error_block(est, obs)
            rows.append(
                {
                    "id": wf["id"],
                    "status": "MEASURED",
                    "accounting_source": ACCOUNTING_SOURCE_MEASURED,
                    "source_class": "hermetic-eval",
                    "source_path": wf["_source_path"],
                    "estimate": est,
                    "observed": obs,
                    "error": err,
                }
            )
        return {"rows": rows}
    finally:
        if own_tmp is not None:
            own_tmp.cleanup()


def extra_turn_control() -> dict:
    wf = next(w for w in hermetic_workflows() if w["id"] == "wf.turns.cumulative")
    with tempfile.TemporaryDirectory(prefix="cnf0081-ctl-") as tmp:
        root = Path(tmp)
        base = run_workflow(wf, work_root=root / "base")
        planted = run_workflow(
            wf, work_root=root / "planted", extra_turn_tokens=77
        )
    assert base is not None and planted is not None
    delta = planted["tokens_cumulative"] - base["tokens_cumulative"]
    last_ne_cum = planted["tokens_cumulative"] != planted["tokens_last_turn"]
    tracer_saw_write = "out/extra-turn.control" in planted["writes"]
    ok = (
        delta == 77
        and planted["tokens_last_turn"] == 77
        and last_ne_cum
        and tracer_saw_write
        and base["tokens_cumulative"] != base["tokens_last_turn"]
    )
    return {
        "ok": ok,
        "base_cumulative": base["tokens_cumulative"],
        "base_last_turn": base["tokens_last_turn"],
        "planted_cumulative": planted["tokens_cumulative"],
        "planted_last_turn": planted["tokens_last_turn"],
        "delta_cumulative": delta,
        "extra_write_seen": tracer_saw_write,
        "cumulative_ne_last_turn": last_ne_cum,
    }


def _pairs(rows: list[dict], key_est: str, key_obs: str) -> list[tuple[float, float]]:
    out = []
    for row in rows:
        if row.get("status") != "MEASURED":
            continue
        est = (row.get("estimate") or {}).get(key_est)
        obs = (row.get("observed") or {}).get(key_obs)
        if est is None or obs is None:
            continue
        out.append((float(est), float(obs)))
    return out


def folded_mape_if_not_checked_were_zero(rows: list[dict]) -> float | None:
    """Illegal aggregation: treat NOT-CHECKED as 0% error. Control bait."""
    pairs = _pairs(rows, "cost_usd", "cost_usd")
    for row in rows:
        if row.get("status") == "NOT-CHECKED" and row.get("estimate"):
            pairs.append((1.0, 1.0))
    return mape_pct(pairs)


def aggregates_from_rows(rows: list[dict]) -> dict:
    measured = [r for r in rows if r.get("status") == "MEASURED"]
    not_checked = [r for r in rows if r.get("status") == "NOT-CHECKED"]
    cost_pairs = _pairs(rows, "cost_usd", "cost_usd")
    token_pairs = _pairs(rows, "tokens_cumulative", "tokens_cumulative")
    time_pairs = _pairs(rows, "wall_clock_s", "wall_clock_s")
    oom = [
        r["id"]
        for r in measured
        if (r.get("error") or {}).get("order_of_magnitude_cost")
    ]
    honest_mape = mape_pct(cost_pairs)
    folded = folded_mape_if_not_checked_were_zero(rows)
    direction = bias_direction(cost_pairs)
    return {
        "bias_direction": direction,
        "bias_magnitude": honest_mape,
        "bias_direction_is_not_magnitude": True,
        "mean_signed_percentage_error_cost": mean_signed(cost_pairs),
        "mape_cost_pct": honest_mape,
        "mape_tokens_pct": mape_pct(token_pairs),
        "mape_time_pct": mape_pct(time_pairs),
        "estimator_biased_low": direction == "LOW",
        "n_measured": len(measured),
        "n_not_checked": len(not_checked),
        "order_of_magnitude_overruns": oom,
        "any_order_of_magnitude_overrun": bool(oom),
        "mape_if_not_checked_folded_into_pass": folded,
        "not_checked_fold_changes_mape": (
            honest_mape is not None
            and folded is not None
            and not math.isclose(honest_mape, folded, rel_tol=1e-12, abs_tol=1e-12)
        ),
    }


def live_not_checked_rows() -> list[dict]:
    rows = [
        {
            "id": "production:tools/agentspec/agentspec/budget.py",
            "status": "NOT-CHECKED",
            "accounting_source": ACCOUNTING_SOURCE_ABSENT_ESTIMATOR,
            "source_class": "production-estimator",
            "source_path": "tools/agentspec/agentspec/budget.py",
            "live_workflow_id": None,
            "estimate": None,
            "observed": None,
            "error": None,
            "reason": (
                "production estimator tools/agentspec/agentspec/budget.py "
                "is absent on this worktree; no measured run"
            ),
        }
    ]
    for rec in live_workflow_files():
        wid = rec["workflow_id"]
        path = rec["path"]
        rows.append(
            {
                "id": f"live:{path}",
                "status": "NOT-CHECKED",
                "accounting_source": ACCOUNTING_SOURCE_ABSENT_ESTIMATOR,
                "source_class": "live-tree",
                "source_path": path,
                "live_workflow_id": wid,
                "estimate": None,
                "observed": None,
                "error": None,
                "reason": (
                    "production estimator tools/agentspec/agentspec/budget.py "
                    "is absent on this worktree; no measured run"
                ),
            }
        )
    return rows


def conflation_check(rows: list[dict]) -> dict:
    target = next(
        (r for r in rows if r.get("id") == "wf.turns.cumulative"), None
    )
    if not target or target.get("status") != "MEASURED":
        return {"ok": False, "reason": "multi-turn workflow not measured"}
    obs = target["observed"]
    cum = obs["tokens_cumulative"]
    last = obs["tokens_last_turn"]
    cost_ok = math.isclose(
        obs["cost_usd"], cost_usd(cum), rel_tol=1e-12, abs_tol=1e-15
    )
    last_cost = cost_usd(last)
    distinct = cum != last
    used_last = math.isclose(obs["cost_usd"], last_cost, rel_tol=1e-12, abs_tol=1e-15)
    return {
        "ok": distinct and cost_ok and not used_last,
        "workflow_id": target["id"],
        "tokens_cumulative": cum,
        "tokens_last_turn": last,
        "cost_from_cumulative": cost_usd(cum),
        "cost_from_last_turn": last_cost,
        "observed_cost_matches_cumulative": cost_ok,
        "observed_cost_matches_last_turn": used_last,
        "fields_distinct": distinct,
        "usd_per_token": USD_PER_TOKEN,
        "rate_source": RATE_SOURCE,
        "cumulative_field": CUMULATIVE_FIELD,
        "last_turn_field": LAST_TURN_FIELD,
    }


def report_body(doc: dict) -> dict:
    """Domain payload. receipt_core additionalProperties=false puts rows under report."""
    if isinstance(doc.get("rows"), list):
        return doc
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("rows"), list):
        return rep
    return doc


def measure_all() -> dict:
    herm = measure_hermetic()
    live = live_not_checked_rows()
    rows = herm["rows"] + live
    agg = aggregates_from_rows(rows)
    extra = extra_turn_control()
    confl = conflation_check(rows)
    prod = production_inputs()
    every_named = all(
        isinstance(r.get("accounting_source"), str)
        and len(r["accounting_source"]) >= 8
        for r in rows
    )
    every_status = all(r.get("status") in {"MEASURED", "NOT-CHECKED"} for r in rows)
    return {
        "rows": rows,
        "aggregates": agg,
        "extra_turn_control": extra,
        "conflation": confl,
        "production": prod,
        "every_workflow_measured_or_not_checked": every_status,
        "every_accounting_source_named": every_named,
        "rate_source": RATE_SOURCE,
        "usd_per_token": USD_PER_TOKEN,
    }
