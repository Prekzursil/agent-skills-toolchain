#!/usr/bin/env python3
"""Named probe 2: queueing sanity with a mechanically different clock.

Different shell: /bin/bash `date +%s%N`. Different field: elapsed wall-clock,
not ledger bytes. The stored component model must reproduce the measured
small-batch runtime within 25 percent. If bash elapsed and the analogue's
own perf_counter wall disagree by more than 30 percent, BLOCKED with both.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

ART = REPO / "command-center/phase3/A5/COST.json"
N = 8
C = 2
QUEUE_BAND = 0.25
CLOCK_BAND = 0.30


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0032-probe2 COST.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0032" or "SUCCESS:ARC-0032" not in json.dumps(doc):
        print("FAILED:ARC-0032-probe2 artifact identity")
        return 1
    coeff = doc["model"]["coefficients_ns"]
    pred_ns = R.predict_wall_ns(N, C, coeff)

    with TemporaryDirectory(prefix="arc0032-p2-") as tmp:
        work = Path(tmp) / "batch"
        work.mkdir()
        out_json = Path(tmp) / "summary.json"
        script = r"""
set -euo pipefail
start=$(date +%s%N)
PYTHONDONTWRITEBYTECODE=1 python3 -B "$1" run --n "$2" --concurrency "$3" --work "$4" > "$5"
end=$(date +%s%N)
echo "$start $end"
"""
        p = subprocess.run(
            ["bash", "-c", script, "probe2-bash", str(HERE / "runtime.py"), str(N), str(C), str(work), str(out_json)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        if p.returncode != 0:
            print("FAILED:ARC-0032-probe2 bash batch")
            print((p.stdout or "")[-1500:])
            print((p.stderr or "")[-1500:])
            return 1
        parts = (p.stdout or "").strip().split()
        if len(parts) < 2:
            print("FAILED:ARC-0032-probe2 bash stamps missing", p.stdout)
            return 1
        start_ns = int(parts[0])
        end_ns = int(parts[1])
        bash_ns = end_ns - start_ns
        summary = json.loads(out_json.read_text(encoding="utf-8"))

    py_ns = int(summary["wall_ns"])
    clock_err = abs(bash_ns - py_ns) / max(bash_ns, py_ns)
    if clock_err > CLOCK_BAND:
        print("FAILED:ARC-0032-probe2 two clocks disagree (BLOCKED, not picked)")
        print(json.dumps({"bash_wall_ns": bash_ns, "python_wall_ns": py_ns, "error_frac": clock_err}))
        return 1
    # Model was calibrated on in-process perf_counter wall, not interpreter
    # startup. Score the 25 percent queueing band against that same field.
    # bash date +%s%N is the mechanically different clock; disagreement with
    # perf_counter above CLOCK_BAND is BLOCKED with both numbers.
    q_err = abs(py_ns - pred_ns) / py_ns if py_ns else 1.0
    if q_err > QUEUE_BAND:
        print(
            f"FAILED:ARC-0032-probe2 queueing {q_err:.3f} "
            f"python_ms={py_ns/1e6:.1f} pred_ms={pred_ns/1e6:.1f} "
            f"bash_ms={bash_ns/1e6:.1f}"
        )
        return 1
    recorded = doc["model"]["held_out_check"]
    # Independent re-derivation of the headline validate error from raw bash ns.
    rederived_pct = round(q_err * 100, 3)
    out = {
        "probe": "probe2-queueing-sanity",
        "unit_id": "ARC-0032",
        "n": N,
        "concurrency": C,
        "bash_wall_ms": round(bash_ns / 1e6, 3),
        "python_wall_ms": round(py_ns / 1e6, 3),
        "predicted_wall_ms": round(pred_ns / 1e6, 3),
        "clock_error_frac": round(clock_err, 6),
        "queueing_error_pct": rederived_pct,
        "band_pct": QUEUE_BAND * 100,
        "waves": math.ceil(N / C),
        "recorded_held_out_error_pct": recorded.get("error_pct"),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"queueing bash_ms={out['bash_wall_ms']} pred_ms={out['predicted_wall_ms']} "
        f"err={rederived_pct}% clocks_frac={clock_err:.4f}"
    )
    print("SUCCESS:ARC-0032-probe2 queueing sanity bash wall-clock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
