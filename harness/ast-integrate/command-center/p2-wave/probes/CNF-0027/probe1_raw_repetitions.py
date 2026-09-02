#!/usr/bin/env python3
"""Named probe 1: sampling-frame redraw + raw-repetition invariants.

Re-draws the n=11 sample from the stored n=13 pool using the recorded seed
and requires identity with the artifact. Independently recomputes median/IQR
from the kept raw values. Also re-runs one live 11-rep series of the null arm
so the probe is not a pure file read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from stats import sample_indices, summarize  # noqa: E402
import harness as H  # noqa: E402
import schemautil as SU  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0027-baseline-variance.json"


def close(a: float, b: float, tol: float = 1e-12) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0027-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0027":
        print("FAILED:CNF-0027-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0027-probe1 self-declared", doc.get("state"))
        return 1
    text = ART.read_text(encoding="utf-8")
    sentinel = (
        "SUCCESS:CNF-0027 emitted only when the artifact at output_path exists"
    )
    if sentinel not in text:
        print("FAILED:CNF-0027-probe1 sentinel absent")
        return 1

    payload = SU.payload(doc)
    benches = payload["benchmarks"]
    if len(benches) < 2:
        print("FAILED:CNF-0027-probe1 too few benchmarks")
        return 1
    seed = int((payload["sampling"] or {}).get("seed") or -1)
    redrawn = 0
    for b in benches:
        bid = b["id"]
        n = int(b["n"])
        raw = b.get("raw_repetitions") or []
        pool = b.get("raw_pool") or []
        if n < 11 or len(raw) < 11:
            print(f"FAILED:CNF-0027-probe1 under-sampling {bid} n={n} raw={len(raw)}")
            return 1
        if any(not isinstance(x, (int, float)) for x in raw):
            print(f"FAILED:CNF-0027-probe1 non-numeric raw {bid}")
            return 1
        if len(pool) < 13:
            print(f"FAILED:CNF-0027-probe1 raw_pool short {bid} {len(pool)}")
            return 1
        want = sample_indices(len(pool), n, seed, bid)
        got = list(b.get("sample_indices") or [])
        if want != got:
            print(f"FAILED:CNF-0027-probe1 sample redraw mismatch {bid} {want} vs {got}")
            return 1
        rebuilt = [pool[i] for i in want]
        if rebuilt != list(raw):
            print(f"FAILED:CNF-0027-probe1 kept raw != pool[indices] {bid}")
            return 1
        stats = summarize(raw)
        for key in ("median", "q1", "q3", "iqr", "noise_floor"):
            if not close(stats[key], b[key]):
                print(f"FAILED:CNF-0027-probe1 {bid} {key} {stats[key]} vs {b[key]}")
                return 1
        if not isinstance(b.get("noise_floor"), (int, float)):
            print(f"FAILED:CNF-0027-probe1 {bid} noise_floor not numeric")
            return 1
        redrawn += 1

    # Live null-arm series: prove the harness still runs, do not require
    # equality with the frozen sample (that would be a flake detector).
    live = []
    ops = H.make_ops(REPO)
    for _ in range(11):
        live.append(H._ms(ops["null-arm-sha256"]["fn"]))
    live_stats = summarize(live)
    if live_stats["n"] != 11 or not isinstance(live_stats["noise_floor"], float):
        print("FAILED:CNF-0027-probe1 live null-arm did not produce a numeric floor")
        return 1

    out = {
        "probe": "probe1-raw-repetitions",
        "unit_id": "CNF-0027",
        "benchmarks_checked": redrawn,
        "sample_redraw_identical": True,
        "stats_recomputed": True,
        "live_null_arm_n": live_stats["n"],
        "live_null_arm_noise_floor_ms": live_stats["noise_floor"],
        "pass": True,
    }
    (HERE / "probe1-raw-repetitions.raw.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0027-probe1 raw repetitions and sample redraw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
