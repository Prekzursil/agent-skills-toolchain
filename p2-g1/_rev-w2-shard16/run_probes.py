#!/usr/bin/env python3
"""Independent reviewer w2s16 - LIVE PROBE re-run (2026-10-26).

Runs every probes/<id>/probe*.py for the 12 shard-16 units from the repo root,
the same way the recorded SUBAGENT-RETURNs ran them:
  PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/<id>/<probe>.py
Requires rc==0 AND a SUCCESS: marker line in the output. Read-only w.r.t. unit
artifacts; probes may write their own scratch output (they are the shipped probes).
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

UNITS = [
    "IMP-0470", "IMP-0478",
    "REL-0001", "REL-0006", "REL-0014", "REL-0017", "REL-0020", "REL-0021", "REL-0022",
    "RES-0004", "RES-0009", "RES-0011",
]


def main() -> int:
    out = {}
    any_fail = False
    for uid in UNITS:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        probes = sorted(pdir.glob("probe*.py"))
        entry = {"probes": []}
        if not probes:
            entry["fail"] = ["no-probe-scripts-found"]
            any_fail = True
        for p in probes:
            rel = p.relative_to(REPO).as_posix()
            cmd = [sys.executable, "-B", rel]
            import os
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            try:
                r = subprocess.run(
                    cmd, cwd=str(REPO), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=300, env=env,
                )
                rc, so, se = r.returncode, r.stdout or "", r.stderr or ""
            except subprocess.TimeoutExpired:
                rc, so, se = 124, "", "TIMEOUT 300s"
            lines = [ln for ln in (so + se).splitlines() if ln.strip()]
            last = lines[-1] if lines else ""
            success_marker = any(
                ln.startswith("SUCCESS:") or
                (ln.startswith("PROBE-") and "-COMPLETE:" in ln)
                for ln in lines
            )
            failed_marker = any(ln.startswith("FAILED:") for ln in lines)
            ok = (rc == 0) and success_marker and not failed_marker
            entry["probes"].append({
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}",
                "exit_code": rc,
                "success_marker": success_marker,
                "failed_marker": failed_marker,
                "last_line": last[:200],
                "tail": (so + se)[-400:],
            })
            if not ok:
                entry.setdefault("fail", []).append(f"probe-failed: {p.name} rc={rc} last={last[:120]}")
                any_fail = True
        out[uid] = entry
        status = "PROBES-OK" if "fail" not in entry else "PROBES-FAIL " + "; ".join(entry["fail"])
        print(f"{uid}: {len(entry['probes'])} probes -> {status}")
    (Path(__file__).parent / "probe-rerun.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("ANY-PROBE-FAIL" if any_fail else "ALL-PROBES-OK")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
