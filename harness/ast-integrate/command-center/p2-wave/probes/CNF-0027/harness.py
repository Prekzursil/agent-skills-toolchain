"""Phase-0-relevant live measurements for CNF-0027.

The recorded snapshot (command-center/BASELINE-SNAPSHOT.json) and the original
hooks/harness-bench harness are absent on this sparse worktree. This module
re-measures the Phase 0 operations that DO exist here (catalog parse, freeze
digest, python -m invocation) with interleaved repetitions, plus a null arm
that isolates harness noise.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from stats import classify_delta, sample_indices, summarize

N_POOL = 13
N_KEEP = 11
SEED = 27
UNIT = "ms"

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SCHEMA_REL = "command-center/schema/architecture-review.schema.json"
RECEIPT_SCHEMA_REL = "platform/schema/receipt.schema.json"
RECEIPT_EXAMPLE_REL = "platform/schema/examples/receipt.valid.example.json"
SNAPSHOT_CANDIDATES = (
    "command-center/BASELINE-SNAPSHOT.json",
    "command-center/BASELINE-SNAPSHOT.md",
    "hooks/harness-bench/baseline.json",
    "hooks/harness-bench/gate.py",
    "hooks/harness-bench/test_bench.py",
    "command-center/phase3/A2/MIGRATION.json",
)


def _read_loadavg() -> tuple[float, float, float]:
    parts = Path("/proc/loadavg").read_text(encoding="utf-8").split()
    return float(parts[0]), float(parts[1]), float(parts[2])


def _mem_available_kb() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1])
    raise RuntimeError("MemAvailable missing from /proc/meminfo")


def quiescence_at_start() -> dict:
    l1, l5, l15 = _read_loadavg()
    nproc = os.cpu_count() or 1
    return {
        "loadavg_1m_at_start": l1,
        "loadavg_5m_at_start": l5,
        "loadavg_15m_at_start": l15,
        "nproc": nproc,
        "mem_available_kb_at_start": _mem_available_kb(),
        "captured_at_ns": time.time_ns(),
    }


def sibling_inflight(repo: Path) -> dict:
    hb = repo.parents[0] / "supervisor-heartbeat.json"
    if not hb.is_file():
        hb = Path("/opt/p2/supervisor-heartbeat.json")
    if not hb.is_file():
        return {"present": False, "in_flight_n": None, "path": None}
    try:
        doc = json.loads(hb.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"present": True, "in_flight_n": None, "path": str(hb), "parse": "FAILED"}
    inflight = doc.get("in_flight") or []
    n = int(doc.get("in_flight_n") or len(inflight))
    others = [u for u in inflight if u != "CNF-0027"]
    return {
        "present": True,
        "path": str(hb),
        "in_flight_n": n,
        "other_units": others[:12],
        "other_n": len(others),
    }


def mtime_fingerprint(root: Path, exclude_prefixes: tuple[str, ...]) -> dict:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(p) for p in exclude_prefixes):
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append(
            (rel, int(st.st_mtime_ns), int(st.st_ctime_ns), int(st.st_size))
        )
    blob = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    return {
        "file_count": len(rows),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def _ms(fn) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000.0


def make_ops(repo: Path) -> dict:
    catalog = repo / CATALOG_REL
    schema_small = repo / SCHEMA_REL
    receipt_schema_path = repo / RECEIPT_SCHEMA_REL
    receipt_example_path = repo / RECEIPT_EXAMPLE_REL
    catalog_bytes = catalog.read_bytes()
    receipt_schema = json.loads(receipt_schema_path.read_text(encoding="utf-8"))
    receipt_example = json.loads(receipt_example_path.read_text(encoding="utf-8"))
    receipt_validator = __import__("jsonschema").Draft7Validator(receipt_schema)

    def catalog_json_parse() -> None:
        json.loads(catalog_bytes)

    def catalog_sha256() -> None:
        hashlib.sha256(catalog_bytes).hexdigest()

    def python_m_json_tool() -> None:
        subprocess.run(
            ["python3", "-m", "json.tool", str(schema_small)],
            cwd=str(repo),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    def null_arm_sha256() -> None:
        hashlib.sha256(b"CNF-0027-null-arm").hexdigest()

    def schema_validate_receipt_example() -> None:
        # MIGRATION.json is absent on this sparse tree; the shipped receipt
        # example + physical receipt.schema.json is the live jsonschema arm.
        receipt_validator.validate(receipt_example)

    return {
        "catalog-json-parse": {
            "title": "json.loads of WORK-UNIT-CATALOG.json (Phase 0 ledger)",
            "fn": catalog_json_parse,
            "input_bytes": len(catalog_bytes),
        },
        "catalog-sha256": {
            "title": "sha256 of WORK-UNIT-CATALOG.json (freeze/snapshot integrity op)",
            "fn": catalog_sha256,
            "input_bytes": len(catalog_bytes),
        },
        "python-m-json-tool": {
            "title": "python -m json.tool on a schema (Phase 0 used python -m)",
            "fn": python_m_json_tool,
            "input_bytes": schema_small.stat().st_size,
        },
        "null-arm-sha256": {
            "title": "null arm: hashlib of a constant (harness noise floor)",
            "fn": null_arm_sha256,
            "input_bytes": 17,
        },
        "schema-validate-receipt-example": {
            "title": (
                "jsonschema Draft7 validate of platform/schema/examples/"
                "receipt.valid.example.json (MIGRATION.json absent)"
            ),
            "fn": schema_validate_receipt_example,
            "input_bytes": receipt_example_path.stat().st_size,
        },
    }


def recorded_sources(repo: Path) -> list[dict]:
    rows = []
    for rel in SNAPSHOT_CANDIDATES:
        p = repo / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return rows


def measure(repo: Path) -> dict:
    ops = make_ops(repo)
    order = list(ops.keys())
    qui = quiescence_at_start()
    sib = sibling_inflight(repo)
    exclude = (
        "confirmation/CNF-0027-baseline-variance.json",
        "p2-wave/probes/CNF-0027/",
    )
    before = mtime_fingerprint(repo / "command-center", exclude)
    pools: dict[str, list[float]] = {k: [] for k in order}
    interleave = []
    for rep in range(N_POOL):
        for bid in order:
            ms = _ms(ops[bid]["fn"])
            pools[bid].append(ms)
            interleave.append({"rep": rep, "benchmark_id": bid, "ms": ms})
    after = mtime_fingerprint(repo / "command-center", exclude)
    qui_end = {
        "loadavg_1m_at_end": _read_loadavg()[0],
        "mem_available_kb_at_end": _mem_available_kb(),
    }

    mtime_changed = before["sha256"] != after["sha256"]
    siblings_live = bool(sib.get("other_n"))
    overloaded = qui["loadavg_1m_at_start"] > float(qui["nproc"])
    freeze_label = (
        "SAMPLE" if (mtime_changed or siblings_live or overloaded) else "FREEZE"
    )
    freeze_reasons = []
    if mtime_changed:
        freeze_reasons.append("command-center mtime fingerprint changed during the window")
    if siblings_live:
        freeze_reasons.append(
            f"supervisor in_flight other_n={sib.get('other_n')} (sibling agents live)"
        )
    if overloaded:
        freeze_reasons.append(
            f"loadavg_1m={qui['loadavg_1m_at_start']} > nproc={qui['nproc']}"
        )
    if not freeze_reasons:
        freeze_reasons.append("no sibling mutation or overload observed")

    benchmarks = []
    for bid in order:
        idxs = sample_indices(N_POOL, N_KEEP, SEED, bid)
        pool = pools[bid]
        kept = [pool[i] for i in idxs]
        stats = summarize(kept)
        benchmarks.append(
            {
                "id": bid,
                "title": ops[bid]["title"],
                "unit": UNIT,
                "n_pool": N_POOL,
                "n": N_KEEP,
                "sample_indices": idxs,
                "sampling_frame_seed": SEED,
                "raw_pool": pool,
                "raw_repetitions": kept,
                "median": stats["median"],
                "q1": stats["q1"],
                "q3": stats["q3"],
                "iqr": stats["iqr"],
                "noise_floor": stats["noise_floor"],
                "min": stats["min"],
                "max": stats["max"],
                "input_bytes": ops[bid]["input_bytes"],
            }
        )

    by_id = {b["id"]: b for b in benchmarks}
    catalog_floor = by_id["catalog-json-parse"]["noise_floor"]
    null_floor = by_id["null-arm-sha256"]["noise_floor"]
    claims = [
        {
            "id": "phase0-snapshot-absent",
            "claim": (
                "Any later improvement claimed against the recorded Phase 0 "
                "baseline numbers in BASELINE-SNAPSHOT.json"
            ),
            "claimed_delta": None,
            "claimed_delta_unit": UNIT,
            "noise_floor": catalog_floor,
            "noise_floor_benchmark": "catalog-json-parse",
            "verdict": "NOT-CHECKED",
            "reason": (
                "BASELINE-SNAPSHOT.json is absent on this worktree; there is no "
                "recorded numeric baseline to compare a later claim against."
            ),
            "source": "catalog inputs for CNF-0027",
        },
        {
            "id": "control-sub-noise-catalog-parse",
            "claim": (
                "Planted control: a 1e-9 ms improvement on catalog-json-parse"
            ),
            "claimed_delta": 1e-9,
            "claimed_delta_unit": UNIT,
            "noise_floor": catalog_floor,
            "noise_floor_benchmark": "catalog-json-parse",
            "verdict": classify_delta(1e-9, catalog_floor),
            "reason": "abs(delta) compared to IQR noise floor of catalog-json-parse",
            "source": "negative-control (planted; not an implementer claim)",
        },
        {
            "id": "control-sub-noise-null-arm",
            "claim": "Planted control: a 0 ms (exact) delta on the null arm",
            "claimed_delta": 0.0,
            "claimed_delta_unit": UNIT,
            "noise_floor": null_floor,
            "noise_floor_benchmark": "null-arm-sha256",
            "verdict": classify_delta(0.0, null_floor),
            "reason": "zero delta is inside any non-negative floor",
            "source": "negative-control (planted; not an implementer claim)",
        },
        {
            "id": "estate-later-numeric-improvement",
            "claim": (
                "A later implementer summary on this estate claiming a speedup "
                "versus a Phase 0 benchmark number"
            ),
            "claimed_delta": None,
            "claimed_delta_unit": UNIT,
            "noise_floor": catalog_floor,
            "noise_floor_benchmark": "catalog-json-parse",
            "verdict": "ABSENT",
            "reason": (
                "No later artifact on this sparse worktree cites a numeric "
                "delta against a Phase 0 baseline. ARC-0005 stop-hook "
                "latency_ms is a detection-latency measurement, not an "
                "improvement versus Phase 0."
            ),
            "source": "estate scan of command-center artifacts",
        },
    ]

    return {
        "seed": SEED,
        "n_pool": N_POOL,
        "n_keep": N_KEEP,
        "interleave": "A1 B1 C1 ... not blocked per benchmark",
        "interleave_log": interleave,
        "benchmarks": benchmarks,
        "quiescence": {
            **qui,
            **qui_end,
            "mtime_before": before,
            "mtime_after": after,
            "mtime_changed": mtime_changed,
            "sibling_agents": sib,
            "freeze_label": freeze_label,
            "freeze_reasons": freeze_reasons,
            "procedure": (
                "Signal 1: /proc/loadavg and MemAvailable_kB at start (and end). "
                "Signal 2: sha256 of (path, mtime_ns, ctime_ns, size) over "
                "command-center files excluding this unit's output and probe dir. "
                "A single quiescence check is not proof; both signals are recorded. "
                "FREEZE only if neither sibling mutation nor overload is observed."
            ),
        },
        "recorded_sources": recorded_sources(repo),
        "improvement_claims": claims,
    }
