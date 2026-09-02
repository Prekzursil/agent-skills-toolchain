"""TST-0305 paths, sentinels, and campaign entry.

Loads tools/bench/overhead.py by file path so a sibling rewrite of
tools/bench/__init__.py cannot break these probes.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _load_overhead():
    path = REPO / "tools" / "bench" / "overhead.py"
    spec = importlib.util.spec_from_file_location("tst0305_bench_overhead", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


overhead = _load_overhead()
NOOP_N = overhead.NOOP_N
REAL_N = overhead.REAL_N
STAGES = overhead.STAGES
TINY_N = overhead.TINY_N
WARMUP_N = overhead.WARMUP_N
compact = overhead.compact
inverted_ceiling_alarm = overhead.inverted_ceiling_alarm
measure_overhead = overhead.measure_overhead

OUT_REL = "command-center/receipts/TST-0305.json"
RESULTS_REL = "command-center/bench/results/TST-0305.jsonl"
LEDGER = HERE / "_campaign_ledger.jsonl"
SCRATCH = HERE / "_scratch"
CATALOG_SENTINEL = "SUCCESS:TST-0305"
QUESTION = (
    "Question: how much of the measured latency is the thing being measured, "
    "and how much is the instrumentation around it? Measure the harness "
    "overhead directly (run a no-op case through the full pipeline), express "
    "it as a fraction of the smallest real case, and set a ceiling above "
    "which the platform must warn that its own overhead dominates."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0305/probe1_noop_distribution.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0305/probe2_ceiling_alarm.py"
)


def run_campaign() -> dict:
    return measure_overhead(
        ledger=LEDGER,
        scratch_dir=SCRATCH,
        noop_n=NOOP_N,
        real_n=REAL_N,
        tiny_n=TINY_N,
        warmup=WARMUP_N,
    )


def append_results_summary(report: dict) -> None:
    dest = REPO / RESULTS_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "compact": compact(report),
        "dominating_stage": report.get("dominating_stage"),
        "fraction_of_p50_real": report.get("fraction_of_p50_real"),
        "overhead_ms": report.get("overhead_ms"),
        "unit_id": "TST-0305",
    }
    line = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    with dest.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.flush()


def load_artifact() -> dict:
    path = REPO / OUT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(OUT_REL)
    return json.loads(path.read_text(encoding="utf-8"))
