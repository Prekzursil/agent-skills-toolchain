#!/usr/bin/env python3
"""Independent latency/overhead harness for CNF-0180.

Measures labelled component stand-ins with an explicit non-empty input gate.
Does not import the project's own verifier (hooks/harness-bench is absent).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Work is bytes * rounds. Ratios 1:4:16:64 keep ranking separable from noise.
CASES: list[dict] = [
    {"id": "hook-dispatch", "bytes": 4096, "rounds": 8},
    {"id": "ledger-write", "bytes": 8192, "rounds": 16},
    {"id": "capability-router", "bytes": 16384, "rounds": 32},
    {"id": "rule-injection", "bytes": 32768, "rounds": 64},
]
CASE_BY_ID = {c["id"]: c for c in CASES}
N_REPS = 11
SLOWDOWN = 1.20
SLOWDOWN_DETECT_FLOOR = 1.10


class EmptyInputError(ValueError):
    def __init__(self, case_id: str, input_size: int) -> None:
        super().__init__(
            f"EMPTY-INPUT: case={case_id} input_size={input_size} "
            "(a zero-size case must fail the run, not emit a latency)"
        )
        self.case_id = case_id
        self.input_size = input_size


def machine_state() -> dict:
    load = os.getloadavg() if hasattr(os, "getloadavg") else (None, None, None)
    mem: dict[str, int] = {}
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:", "MemFree:")):
                parts = line.split()
                mem[parts[0].rstrip(":")] = int(parts[1])
    return {
        "loadavg_1_5_15": [load[0], load[1], load[2]],
        "mem_kb": mem,
        "cpu_count": os.cpu_count(),
        "pid": os.getpid(),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "cwd": str(Path.cwd()),
        "ts_ns": time.time_ns(),
    }


def payload_for(case: dict) -> bytes:
    n = int(case.get("bytes") or 0)
    cid = str(case.get("id") or "unnamed")
    if n <= 0:
        raise EmptyInputError(cid, n)
    rounds = int(case.get("rounds") or 0)
    if rounds <= 0:
        raise EmptyInputError(cid, rounds)
    seed = f"CNF-0180|{cid}|{n}".encode("utf-8")
    block = hashlib.sha256(seed).digest()
    return (block * ((n + 31) // 32))[:n]


def run_case(case: dict, *, slowdown: float = 1.0, clock=time.perf_counter) -> dict:
    blob = payload_for(case)
    rounds = int(case["rounds"])
    if slowdown != 1.0:
        rounds = max(1, int(round(rounds * slowdown)))
    t0 = clock()
    h = hashlib.sha256()
    for _ in range(rounds):
        h.update(blob)
    digest = h.hexdigest()
    elapsed_ms = (clock() - t0) * 1000.0
    return {
        "case_id": case["id"],
        "input_size_bytes": len(blob),
        "rounds": rounds,
        "slowdown": slowdown,
        "elapsed_ms": elapsed_ms,
        "digest8": digest[:8],
        "clock": getattr(clock, "__name__", str(clock)),
    }


def summarize(samples: list[float]) -> dict:
    if not samples:
        raise EmptyInputError("summarize", 0)
    ordered = sorted(samples)
    n = len(ordered)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0
    q1 = ordered[n // 4]
    q3 = ordered[(3 * n) // 4]
    return {
        "n": n,
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
        "median_ms": median,
        "mean_ms": statistics.mean(ordered),
        "stdev_ms": statistics.pstdev(ordered) if n > 1 else 0.0,
        "iqr_ms": q3 - q1,
        "q1_ms": q1,
        "q3_ms": q3,
        "raw_ms": samples,
    }


def warm_samples(case: dict, n: int = N_REPS, *, slowdown: float = 1.0, prime: int = 3) -> dict:
    for _ in range(prime):
        run_case(case, slowdown=slowdown)
    rows = [run_case(case, slowdown=slowdown) for _ in range(n)]
    return {
        "case_id": case["id"],
        "input_size_bytes": rows[0]["input_size_bytes"],
        "thermal": "warm",
        "slowdown": slowdown,
        "distribution": summarize([r["elapsed_ms"] for r in rows]),
        "runs": rows,
    }


def empty_input_control() -> dict:
    """Zero-size case must fail and must not emit a latency number."""
    mutant = {"id": "empty-mutant", "bytes": 0, "rounds": 8}
    emitted_number = False
    failed = False
    message = ""
    try:
        row = run_case(mutant)
        emitted_number = "elapsed_ms" in row
    except EmptyInputError as exc:
        failed = True
        message = str(exc)
        emitted_number = False
    ok = failed and (not emitted_number) and "EMPTY-INPUT" in message
    return {
        "control": "empty-input",
        "zero_size_failed_the_run": failed,
        "latency_number_emitted": emitted_number,
        "pass": ok,
        "message": message,
    }


def rank_ids(medians: dict[str, float]) -> list[str]:
    return [k for k, _ in sorted(medians.items(), key=lambda kv: (kv[1], kv[0]))]


def dump(doc: dict) -> None:
    json.dump(doc, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", metavar="CASE_ID")
    p.add_argument("--slowdown", type=float, default=1.0)
    p.add_argument("--clock", choices=("perf_counter", "monotonic"), default="perf_counter")
    p.add_argument("--empty", action="store_true")
    args = p.parse_args()
    clock = time.monotonic if args.clock == "monotonic" else time.perf_counter
    if args.empty:
        try:
            run_case({"id": "empty-mutant", "bytes": 0, "rounds": 8}, clock=clock)
        except EmptyInputError as exc:
            dump(
                {
                    "ok": False,
                    "empty_input": True,
                    "input_size_bytes": exc.input_size,
                    "elapsed_ms": None,
                    "error": str(exc),
                }
            )
            return 2
        dump({"ok": True, "empty_input": True, "elapsed_ms": 0, "error": "did-not-fail"})
        return 0
    if args.once:
        case = CASE_BY_ID.get(args.once)
        if case is None:
            dump({"ok": False, "error": f"unknown-case:{args.once}"})
            return 2
        try:
            row = run_case(case, slowdown=args.slowdown, clock=clock)
        except EmptyInputError as exc:
            dump(
                {
                    "ok": False,
                    "empty_input": True,
                    "input_size_bytes": exc.input_size,
                    "elapsed_ms": None,
                    "error": str(exc),
                }
            )
            return 2
        row["ok"] = True
        row["machine_state"] = machine_state()
        dump(row)
        return 0
    dump({"ok": False, "error": "usage"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
