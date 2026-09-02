"""Harness overhead measurement (TST-0305).

Runs a case through the same four-stage pipeline the bench uses
(``setup`` -> ``dispatch`` -> ``collect`` -> ``ledger_write``) with the oracle
call timed separately, so the instrumentation cost can be attributed per stage
and compared with the payload it wraps.

* no-op campaign: 100 runs whose oracle does nothing -> harness overhead
  distribution and per-stage attribution.
* real campaign: a calibrated payload (``max(4 ms, 6 * no-op p50)``) -> the
  smallest real case the overhead is expressed against.
* tiny campaign: a near-zero payload -> the state in which the harness must
  admit that it dominates its own measurement.

The ceiling alarm fires when the harness share of total wall time exceeds
``CEILING``. ``inverted_ceiling_alarm`` is the polarity-flipped detector
control and must disagree with production on both states.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import Any, Callable

NOOP_N = 100
REAL_N = 20
TINY_N = 5
WARMUP_N = 3
STAGES = ("setup", "dispatch", "collect", "ledger_write")
CEILING = 0.5
MIN_REAL_PAYLOAD_MS = 4.0
REAL_PAYLOAD_MULTIPLIER = 6.0


def compact(report: dict[str, Any]) -> dict[str, Any]:
    return {
        k: report[k]
        for k in (
            "ok",
            "overhead_ms",
            "fraction_of_p50_real",
            "dominating_stage",
            "alarm",
            "both_states",
            "payload_s",
        )
        if k in report
    }


def harness_share(oracle_ms: float, harness_ms: float) -> float:
    total = float(oracle_ms) + float(harness_ms)
    if total <= 0:
        return 1.0
    return float(harness_ms) / total


def ceiling_alarm(oracle_ms: float, harness_ms: float, ceiling: float = CEILING) -> bool:
    """Production polarity: warn when the harness is more than ``ceiling`` of the wall."""
    return harness_share(oracle_ms, harness_ms) > ceiling


def inverted_ceiling_alarm(oracle_ms: float, harness_ms: float, ceiling: float = CEILING) -> bool:
    """Detector control with the comparison flipped; must fail both states."""
    return harness_share(oracle_ms, harness_ms) <= ceiling


def _busy_wait(seconds: float) -> None:
    if seconds <= 0:
        return
    end = time.perf_counter() + seconds
    acc = 0
    while time.perf_counter() < end:
        acc += 1


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "p50_ms": 0.0, "p90_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "mean_ms": 0.0}
    return {
        "n": len(values),
        "p50_ms": round(statistics.median(values), 6),
        "p90_ms": round(_quantile(values, 0.9), 6),
        "min_ms": round(min(values), 6),
        "max_ms": round(max(values), 6),
        "mean_ms": round(statistics.fmean(values), 6),
        "stdev_ms": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
    }


class Pipeline:
    """The four harness stages around one oracle call, each timed on its own."""

    def __init__(self, scratch_dir: Path, ledger_path: Path) -> None:
        self.scratch_dir = Path(scratch_dir)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def run_case(self, campaign: str, idx: int, oracle: Callable[[], Any]) -> dict[str, Any]:
        stage_ms: dict[str, float] = {}

        t0 = time.perf_counter()
        case_dir = self.scratch_dir / campaign / f"case-{idx:04d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.json"
        input_path.write_text(json.dumps({"campaign": campaign, "idx": idx}), encoding="utf-8")
        stage_ms["setup"] = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        case = json.loads(input_path.read_text(encoding="utf-8"))
        case["dispatched"] = True
        stage_ms["dispatch"] = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        result = oracle()
        oracle_ms = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        record = {
            "campaign": campaign,
            "idx": idx,
            "case": case,
            "result": None if result is None else str(result)[:64],
            "oracle_ms": round(oracle_ms, 6),
        }
        (case_dir / "result.json").write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        stage_ms["collect"] = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        stage_ms["ledger_write"] = (time.perf_counter() - t0) * 1000.0

        harness_ms = sum(stage_ms.values())
        return {
            "stages_ms": stage_ms,
            "oracle_ms": oracle_ms,
            "harness_ms": harness_ms,
            "total_ms": harness_ms + oracle_ms,
        }


def _campaign(pipeline: Pipeline, name: str, n: int, oracle: Callable[[], Any], warmup: int) -> dict[str, Any]:
    for i in range(warmup):
        pipeline.run_case(f"{name}-warmup", i, oracle)
    runs = [pipeline.run_case(name, i, oracle) for i in range(n)]
    totals = [r["total_ms"] for r in runs]
    harness = [r["harness_ms"] for r in runs]
    oracle_ms = [r["oracle_ms"] for r in runs]
    stages = {s: _summary([r["stages_ms"][s] for r in runs]) for s in STAGES}
    total = _summary(totals)
    p50_harness = statistics.median(harness)
    p50_oracle = statistics.median(oracle_ms)
    return {
        "n": n,
        "stages": stages,
        "total": total,
        "harness": _summary(harness),
        "oracle": _summary(oracle_ms),
        "p50_ms": total["p50_ms"],
        "p50_harness_ms": round(p50_harness, 6),
        "p50_oracle_ms": round(p50_oracle, 6),
        "p50_total_ms": total["p50_ms"],
        "harness_share_p50": round(harness_share(p50_oracle, p50_harness), 6),
        "ceiling_p50": ceiling_alarm(p50_oracle, p50_harness),
        "totals_ms": [round(t, 6) for t in totals],
    }


def _dominating_stage(stages: dict[str, dict[str, Any]], p50_total: float) -> dict[str, Any]:
    name = max(STAGES, key=lambda s: stages[s]["p50_ms"])
    p50 = stages[name]["p50_ms"]
    return {
        "stage": name,
        "p50_ms": p50,
        "share_of_p50_total": round(p50 / p50_total, 6) if p50_total > 0 else 0.0,
        "ranking": sorted(STAGES, key=lambda s: -stages[s]["p50_ms"]),
    }


def measure_overhead(
    ledger: Path | None = None,
    scratch_dir: Path | None = None,
    noop_n: int = NOOP_N,
    real_n: int = REAL_N,
    tiny_n: int = TINY_N,
    warmup: int = WARMUP_N,
) -> dict[str, Any]:
    scratch = Path(scratch_dir) if scratch_dir else Path(os.environ.get("TMPDIR", "/tmp")) / "tst0305-scratch"
    ledger_path = Path(ledger) if ledger else scratch / "_campaign_ledger.jsonl"
    pipeline = Pipeline(scratch, ledger_path)

    def noop() -> None:
        return None

    def tiny() -> int:
        return sum(range(50))

    noop_rep = _campaign(pipeline, "noop", noop_n, noop, warmup)
    overhead_ms = noop_rep["total"]["p50_ms"]

    # Calibrate the smallest real case against the measured harness cost so
    # the fraction is a property of this machine, not a constant.
    payload_ms = max(MIN_REAL_PAYLOAD_MS, REAL_PAYLOAD_MULTIPLIER * max(overhead_ms, 1e-6))
    payload_s = payload_ms / 1000.0

    def real() -> float:
        _busy_wait(payload_s)
        return payload_s

    real_rep = _campaign(pipeline, "real", real_n, real, warmup)
    tiny_rep = _campaign(pipeline, "tiny", tiny_n, tiny, warmup)

    p50_real = real_rep["total"]["p50_ms"] or 1e-9
    fraction = overhead_ms / p50_real
    fast_fired = tiny_rep["ceiling_p50"]
    slow_fired = real_rep["ceiling_p50"]
    inv_fast = inverted_ceiling_alarm(tiny_rep["p50_oracle_ms"], tiny_rep["p50_harness_ms"])
    inv_slow = inverted_ceiling_alarm(real_rep["p50_oracle_ms"], real_rep["p50_harness_ms"])
    both_states = fast_fired is True and slow_fired is False
    ceiling = {
        "ceiling": CEILING,
        "rule": "alarm when harness_ms / (oracle_ms + harness_ms) > ceiling at p50",
        "fast_p50_fired": fast_fired,
        "slow_p50_fired": slow_fired,
        "fast_share_p50": tiny_rep["harness_share_p50"],
        "slow_share_p50": real_rep["harness_share_p50"],
        "inverted_fast_fired": inv_fast,
        "inverted_slow_fired": inv_slow,
        "inverted_both_states": inv_fast is True and inv_slow is False,
    }
    dominating = _dominating_stage(noop_rep["stages"], overhead_ms)
    alarm = ceiling_alarm(real_rep["p50_oracle_ms"], real_rep["p50_harness_ms"])
    ok = (
        noop_rep["n"] == noop_n
        and overhead_ms > 0
        and 0 < fraction < 1
        and both_states
        and not ceiling["inverted_both_states"]
    )
    report = {
        "ok": ok,
        "stages_order": list(STAGES),
        "warmup": warmup,
        "noop": noop_rep,
        "noop_totals_ms": noop_rep["totals_ms"],
        "real": real_rep,
        "real_totals_ms": real_rep["totals_ms"],
        "tiny": tiny_rep,
        "tiny_totals_ms": tiny_rep["totals_ms"],
        "overhead_ms": overhead_ms,
        "fraction_of_p50_real": round(fraction, 6),
        "dominating_stage": dominating,
        "ceiling": ceiling,
        "both_states": both_states,
        "alarm": alarm,
        "payload_s": round(payload_s, 6),
        "payload_rule": f"max({MIN_REAL_PAYLOAD_MS} ms, {REAL_PAYLOAD_MULTIPLIER} * noop p50)",
        "ledger": str(ledger_path),
        "scratch_dir": str(scratch),
    }
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "kind": "campaign-summary",
                    "overhead_ms": overhead_ms,
                    "fraction_of_p50_real": report["fraction_of_p50_real"],
                    "dominating_stage": dominating["stage"],
                    "both_states": both_states,
                    "payload_s": report["payload_s"],
                },
                sort_keys=True,
            )
            + "\n"
        )
    return report
