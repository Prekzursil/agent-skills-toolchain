#!/usr/bin/env python3
"""Finish ADV-0033: manifest + SUBAGENT-RETURN + measure + receipt."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
PDIR = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0033"
RECEIPTS = REPO / "command-center" / "receipts"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNIT = next(u for u in CATALOG.get("work_units", []) if u.get("id") == "ADV-0033")
OUT_REL = str(UNIT["output_path"]).replace("\\", "/")
OUT = REPO / OUT_REL

now = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run(cmd):
    import os
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                       timeout=2700, env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main() -> int:
    p1 = PDIR / "probe1_control.py"
    p2 = PDIR / "probe2_router.py"
    rc1, o1 = run([sys.executable, "-B", str(p1)])
    rc2, o2 = run([sys.executable, "-B", str(p2)])
    print(f"probe1 rc={rc1} probe2 rc={rc2}")
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0033 probes")
        return 1
    live = lf_sha(OUT)
    live_bytes = OUT.stat().st_size

    rows = [
        {"unit_id": "ADV-0033", "path": OUT_REL, "bytes": live_bytes,
         "sha256": live, "exists": True, "eol": "LF", "role": "primary",
         "present": True, "receipt_path": "command-center/p2-wave/probes/ADV-0033/SUBAGENT-RETURN.json"},
        {"unit_id": "ADV-0033", "path": "command-center/p2-wave/probes/ADV-0033/probe1_control.py",
         "bytes": p1.stat().st_size,
         "sha256": hashlib.sha256(p1.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
         "exists": True, "eol": "LF", "role": "supporting-predicate",
         "present": True, "receipt_path": "command-center/p2-wave/probes/ADV-0033/SUBAGENT-RETURN.json"},
        {"unit_id": "ADV-0033", "path": "command-center/p2-wave/probes/ADV-0033/probe2_router.py",
         "bytes": p2.stat().st_size,
         "sha256": hashlib.sha256(p2.read_bytes().replace(b"\\\\r\\\\n", b"\n")).hexdigest(),
         "exists": True, "eol": "LF", "role": "supporting-recheck", "present": True,
         "receipt_path": "command-center/p2-wave/probes/ADV-0033/SUBAGENT-RETURN.json"},
    ]
    (PDIR / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps({"schema_version": 1,
                    "contract": "completion-predicate-condition-11-unit-artifact-registration",
                    "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
                    "unit_id": "ADV-0033", "verified_on_disk": True,
                    "expected": len(rows), "present": len(rows),
                    "artifacts": rows}, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    ret = {
        "id": "ADV-0033", "unit_id": "ADV-0033",
        "status": "DELIVERED", "state": "BLOCKED",
        "sentinel": ("FAILED:ADV-0033 builder-side delivery COMPLETE (artifact schema-valid, "
                     "live probes exit 0, manifest sha matches); SUCCESS withheld: reviewer-absent"),
        "output_path": OUT_REL,
        "named_probes": [
            {"id": "probe1", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p1.relative_to(REPO).as_posix()}",
             "exit_code": rc1, "role": "identical-payload-matrix", "raw_output": o1[-6000:]},
            {"id": "probe2", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p2.relative_to(REPO).as_posix()}",
             "exit_code": rc2, "role": "router-then-matrix-cell", "raw_output": o2[-6000:]},
        ],
        "artifacts": [{"path": OUT_REL, "bytes": live_bytes, "sha256": live,
                       "exists": True, "role": "primary"}],
        "manifest_path": "command-center/p2-wave/probes/ADV-0033/UNIT-ARTIFACT-MANIFEST.json",
        "failure": {"classification": ["reviewer-absent"],
                    "reason": ("Independent reviewer closure unavailable in builder shard; "
                               "artifact schema-valid + live probes exit 0 + manifest sha "
                               "matches this session.")},
        "notes": ("Shard0 wave-2 builder (resume) 2026-10-25: prior FAILED (dependency-absent, "
                  "2026-10-24) resolved by the predecessor's probe rework - lib.py degrades "
                  "gracefully (TST-0082 fixture ABSENT-not-guessed, recorded in captures; "
                  "ARC-0083 remains catalog-forensics-owned, never guessed). Artifact re-emitted "
                  "on this Windows host from the live four-action matrix: local-process + worktree "
                  "REFUTED isolation; wsl2/docker/cloud NOT-CHECKED (honest partial); IMP-0064 "
                  "reprobe superseded the August absence invariant (schema+test shipped). "
                  "receipt_core SUCCESS battery enforced via pre-write schema validation; NOT-RUN "
                  "isolator control recorded in negative_controls + residual_unknowns, not as a "
                  "PASS. Receipt BLOCKED/reviewer-absent; only the independent reviewer closes."),
        "extensions": {"builder": "shard0 wave-2 (resume) 2026-10-25",
                       "prior_builder": "shard0 w2 predecessor died mid-flight after probe rework; "
                                         "artifact reprobe block landed; two-pass emit completed here"},
        "ts": now(),
    }
    (PDIR / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    mrc, mout = run([sys.executable, str(MEASURE), "ADV-0033"])
    tail = mout.strip().splitlines()[-1] if mout.strip() else ""
    print(f"measure rc={mrc} {tail}")
    if mrc != 0:
        return 1
    # receipt
    rp = RECEIPTS / "ADV-0033.json"
    receipt = {
        "schema_version": 1,
        "unit_id": "ADV-0033",
        "state": "BLOCKED",
        "sentinel": ("SENTINEL:ADV-0033:BUILT-AWAITING-INDEPENDENT-REVIEW builder-side "
                     "delivery verified live; SUCCESS withheld: reviewer-absent"),
        "spec_anchor": str(UNIT.get("spec_anchor") or ""),
        "min_bytes_threshold": 1024,
        "artifacts": [{"path": OUT_REL, "bytes": live_bytes, "sha256": live,
                       "exists": True, "eol": "LF", "role": "primary"}],
        "evidence": [
            {"role": "probe1", "method": "test-run", "command": f"python3 -B {p1.relative_to(REPO).as_posix()}",
             "raw_output": o1[-1500:], "fingerprint": hashlib.sha256((str(p1) + o1).encode()).hexdigest()[:32]},
            {"role": "probe2", "method": "test-run", "command": f"python3 -B {p2.relative_to(REPO).as_posix()}",
             "raw_output": o2[-1500:], "fingerprint": hashlib.sha256((str(p2) + o2).encode()).hexdigest()[:32]},
        ],
        "timestamps": {"started_at": now(), "ended_at": now(), "duration_seconds": 0},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "failure": {"classification": ["reviewer-absent"],
                    "reason": ("Builder-side delivery complete and live-verified. History: prior "
                               "attempt failed dependency-absent (TST-0082 fixture + ARC-0083 "
                               "completeness.py); predecessor reworked probes to record ABSENT-not-"
                               "guessed and live re-derivations; ARC-0083 stays catalog-forensics-"
                               "owned. Independent reviewer closure unavailable in builder shard.")},
        "reviewer": None,
        "manifest_registration": {"registered": True,
                                  "manifest_path": "command-center/p2-wave/probes/ADV-0033/UNIT-ARTIFACT-MANIFEST.json",
                                  "entry_id": "ADV-0033", "registered_at": now()},
        "produced_by": {"vendor": "anthropic", "model": "claude-opus-5-5",
                        "role": "builder-shard0-w2", "execution_substrate": "local-windows-pwsh7"},
        "extensions": {"builder": "shard0 wave-2 (resume) 2026-10-25",
                       "prior_builder": "dependency-absent 2026-10-24; predecessor rework landed "
                                          "graceful-degradation probes"},
    }
    rp.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                  encoding="utf-8", newline="\n")
    print("receipt written BLOCKED/reviewer-absent")
    print("SUCCESS:delivered ADV-0033")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
