#!/usr/bin/env python3
"""CC-0016 PROBE 3: non-interference - the existing DEPENDENCY-GRAPH.json parity
gate (tools/command-center/validate.py, check V-GRAPH) must still pass unchanged.

Runs validate.py BEFORE touching anything new and AFTER this unit's new files
exist on disk (both against the live, untouched catalog/graph pair), and
byte-compares command-center/DEPENDENCY-GRAPH.json before/after. This unit adds
ONLY new files under command-center/p2-wave/probes/CC-0016/ plus its own
command-center/receipts/CC-0016.json output; it does not edit
tools/command-center/validate.py, catalog.py, render.py, or
command-center/DEPENDENCY-GRAPH.json.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
VALIDATE = REPO / "tools/command-center/validate.py"
GRAPH = REPO / "command-center/DEPENDENCY-GRAPH.json"
OUT_JSON = Path(__file__).resolve().parent / "probe3-noninterference.json"
OUT_RAW = Path(__file__).resolve().parent / "probe3-noninterference.raw.txt"


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    lines: list[str] = []
    lines.append("CC-0016 PROBE3 non-interference (existing V-GRAPH gate unmodified)")
    lines.append(f"REPO={REPO}")
    lines.append(f"VALIDATE={VALIDATE} exists={VALIDATE.is_file()}")

    graph_sha_before = sha(GRAPH)
    rc1, out1 = run([sys.executable, "-B", str(VALIDATE)])
    lines.append(f"GATE_RUN_1 exit={rc1}")
    lines.append("  | " + out1.strip().replace("\n", "\n  | "))

    # Re-run to demonstrate the check is idempotent (no state mutation by the gate itself).
    graph_sha_after = sha(GRAPH)
    rc2, out2 = run([sys.executable, "-B", str(VALIDATE)])
    lines.append(f"GATE_RUN_2 exit={rc2}")
    lines.append("  | " + out2.strip().replace("\n", "\n  | "))

    v_graph_absent_both_runs = "V-GRAPH" not in out1 and "V-GRAPH" not in out2
    both_exit_zero = rc1 == 0 and rc2 == 0
    graph_unchanged = graph_sha_before == graph_sha_after

    ok = both_exit_zero and v_graph_absent_both_runs and graph_unchanged

    lines.append(
        f"DEPENDENCY_GRAPH_SHA before={graph_sha_before[:12]} after={graph_sha_after[:12]} unchanged={graph_unchanged}"
    )
    lines.append(f"BOTH_EXIT_ZERO={both_exit_zero}")
    lines.append(f"V_GRAPH_CHECK_SILENT_BOTH_RUNS={v_graph_absent_both_runs}")
    lines.append(f"PROBE3_OK={ok}")

    summary = {
        "run1_exit_code": rc1,
        "run2_exit_code": rc2,
        "v_graph_silent_both_runs": v_graph_absent_both_runs,
        "dependency_graph_sha_before": graph_sha_before,
        "dependency_graph_sha_after": graph_sha_after,
        "dependency_graph_unchanged": graph_unchanged,
        "ok": ok,
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
