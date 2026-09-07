#!/usr/bin/env python3
"""AUD-0046 NAMED PROBE 1: gate baseline exit code on the unmodified scratch worktree.

Catalog evidence_requirement Probe 1:
  gate exit code on the unmodified scratch worktree (must be 0). Either reading
  alone measures nothing -- this file only proves the GREEN half; probe2 plants
  the matched mutation and proves the RED half plus the revert-to-0 half.

Inputs (catalog `inputs`): the gate inventory from AUD-0041 (CI step inventory)
and AUD-0045 (fail-open gate census) -- 24 gate scripts present on disk out of
26 the catalog considers. This probe measures the baseline (0 exit code) for
the 8 gates this pass actually sweeps end-to-end (see `fixtures/gate_cases.json`
-> `gates`); the remaining 16 are carried forward as `not_yet_swept` residuals,
not silently dropped.

Isolation: everything runs inside a disposable `git worktree add --detach`
checkout, removed at the end of the run. The live tree is never touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-gate-baseline-census.json"
RAW = PROBE / "probe1-gate-baseline-census.raw.txt"
CASES_FILE = PROBE / "fixtures" / "gate_cases.json"


def run(cmd: list[str], cwd: Path, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"


def make_worktree() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="aud0046-p1-"))
    wt = tmp / "wt"
    rc, out = run(
        ["git", "worktree", "add", "--detach", str(wt), "HEAD"], cwd=REPO, timeout=300
    )
    if rc != 0:
        raise RuntimeError(f"git worktree add failed rc={rc}: {out[-2000:]}")
    return wt


def remove_worktree(wt: Path) -> None:
    run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO, timeout=120)


def main() -> int:
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    gates = cases["gates"]
    not_yet_swept = cases["not_yet_swept"]

    wt = make_worktree()
    lines: list[str] = []
    per_gate: list[dict] = []
    try:
        for g in gates:
            rc, out = run(g["command"], cwd=wt)
            ok = rc == g["expected_baseline_exit"]
            per_gate.append(
                {
                    "id": g["id"],
                    "gate": g["gate"],
                    "command": " ".join(g["command"]),
                    "baseline_exit": rc,
                    "expected_baseline_exit": g["expected_baseline_exit"],
                    "ok": ok,
                    "output_tail": out[-1500:],
                }
            )
            lines.append(
                f"GATE\t{g['id']}\t{g['gate']}\tbaseline_exit={rc}\t"
                f"expected={g['expected_baseline_exit']}\tok={ok}"
            )
    finally:
        remove_worktree(wt)

    baseline_all_ok = all(row["ok"] for row in per_gate)
    result = {
        "ok": baseline_all_ok,
        "unit": "AUD-0046",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gates_present_total": 24,
        "gates_swept_this_pass": len(gates),
        "gates_not_yet_swept": len(not_yet_swept),
        "not_yet_swept": not_yet_swept,
        "baseline_all_ok": baseline_all_ok,
        "per_gate": per_gate,
        "worktree_mode": "git worktree add --detach (removed after run)",
        "live_tree_mutated": False,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines.insert(0, "AUD-0046 NAMED PROBE 1: gate baseline exit code census")
    lines.insert(1, "unit=AUD-0046")
    lines.insert(2, f"gates_present_total=24 gates_swept_this_pass={len(gates)} "
                     f"gates_not_yet_swept={len(not_yet_swept)}")
    lines.append(f"baseline_all_ok={baseline_all_ok}")
    lines.append("SUCCESS:AUD-0046-probe1" if baseline_all_ok else "FAILED:AUD-0046-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if baseline_all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
