#!/usr/bin/env python3
"""Re-run all 24 shard18-w4 probes under a FULL inherited environment
(the PROBE-CMDS semantic: PYTHONDONTWRITEBYTECODE=1 python -B, cwd=repo).
Records rc + first marker line per probe. Read-only wrt receipts.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ["TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116",
         "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138"]


def main():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    results = {}
    for uid in UNITS:
        rows = []
        for probe in sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe*.py")):
            try:
                cp = subprocess.run([sys.executable, "-B", str(probe)],
                                    cwd=str(REPO), capture_output=True, text=True,
                                    timeout=180, env=env)
                rc, out = cp.returncode, (cp.stdout or cp.stderr)
            except subprocess.TimeoutExpired:
                rc, out = "TIMEOUT", ""
            first = next((ln for ln in out.splitlines() if ln.strip()), "")
            rows.append({"probe": probe.name, "rc": rc, "marker": first[:200]})
        results[uid] = rows
        print(uid, "->", "; ".join("%s rc=%s" % (r["probe"], r["rc"]) for r in rows))
        for r in rows:
            if r["rc"] != 0:
                print("   FAIL-MARKER:", r["marker"])
    (Path(__file__).parent / "probe-fullenv-results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
