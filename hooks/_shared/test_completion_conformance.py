#!/usr/bin/env python3
"""Cross-implementation conformance harness for C1.

ONE case table, executed against EVERY implementation of the completion predicate. This is the
actual fix for the drift class -- not "delete the duplicates", because the duplication is FORCED:
a PowerShell wave-runner and a Databricks notebook cannot import a local Python module. What is
NOT forced is the drift, and a shared case table is what removes it.

The two live drifts this harness was written to pin, both real:

  * run-wave1.ps1's Test-UnitComplete required `exit == 0`. F036 exited NON-ZERO after writing a
    complete 24 KB artifact and was scored FAILED -- real work discarded by a stricter copy.
  * The tail scans measured DIFFERENT UNITS: PowerShell `Get-Content -Tail 6` reads six LINES,
    Python reads 600 BYTES. An artifact whose sentinel is followed by seven blank lines passes one
    gate and fails the other. Never hit in the wild, which is exactly why it survived -- a latent
    disagreement is still a disagreement.

Reuses build_cases() from test_completion.py so the two suites can never fall out of sync either.

Run:  python test_completion_conformance.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_completion import build_cases  # noqa: E402

# python kwarg -> PowerShell parameter name
PARAM_MAP = {
    "artifact": "Artifact",
    "sentinel": "Sentinel",
    "min_bytes": "MinBytes",
    "exit_code": "ExitCode",
    "pid_alive": "PidAlive",
    "cpu_delta_s": "CpuDeltaS",
    "cpu_total_s": "CpuTotalS",
    "idle_s": "IdleS",
    "stale_after_s": "StaleAfterS",
    "detector_ok": "DetectorOk",
}


def _pwsh() -> str | None:
    """Prefer PowerShell 7 (pwsh); fall back to Windows PowerShell. Returns None if neither."""
    for exe in ("pwsh", "powershell"):
        if shutil.which(exe):
            return exe
    return None


def run_powershell(cases, tmp: Path) -> list[str] | None:
    """Execute the whole case table in ONE pwsh process; return the verdict states in order."""
    exe = _pwsh()
    if not exe:
        return None
    payload = [{PARAM_MAP[k]: v for k, v in kwargs.items() if k in PARAM_MAP}
               for _, _, kwargs in cases]
    cases_file = tmp / "cases.json"
    cases_file.write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(HERE / "completion.ps1"), "-CasesFile", str(cases_file)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        print(f"  !! pwsh exited {proc.returncode}\n{proc.stderr.strip()[:1500]}")
        return None
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def main() -> int:
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cases = build_cases(tmp)

        print(f"=== conformance: {len(cases)} cases x PowerShell implementation ===")
        got = run_powershell(cases, tmp)

        if got is None:
            # A harness that cannot run must not report PASS. Rule 3 applied to itself: a failed
            # detector is not evidence of conformance.
            print("  XX HARNESS UNAVAILABLE -- pwsh missing or errored. NOT a pass.")
            return 2
        if len(got) != len(cases):
            print(f"  XX arity mismatch: {len(got)} verdicts for {len(cases)} cases")
            return 1

        for (label, want, _), ps_state in zip(cases, got):
            ok = ps_state == want
            if not ok:
                fails += 1
            print(f"  {'OK ' if ok else 'XX '} {label}: pwsh={ps_state} want={want}")

    print(f"\nRESULT: {'ALL PASS' if not fails else str(fails) + ' FAIL'}  ({len(cases)} cases)")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
