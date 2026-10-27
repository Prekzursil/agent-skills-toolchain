#!/usr/bin/env python3
"""ADV-0127 wave-4 receipt refresh (BLOCKED/reviewer-absent form preserved).

Re-runs emit + both named probes, then updates SUBAGENT-RETURN.json keeping
the program-contract receipt form: status=DELIVERED, state=BLOCKED,
failure.classification=["reviewer-absent"], reviewer=None, prior closure kept
in extensions.prev_closure. Refreshes named_probes exit codes + raw outputs,
primary artifact sha row, ts, notes. Rewrites UNIT-ARTIFACT-MANIFEST.json
rows with live CRLF-normalized sha256 values.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
PROBE = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0127"
OUT = "command-center/adversarial/ADV-0127-clock-skew-timezone-dst-effects.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0127/probe1_static_audit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0127/probe2_behavioral.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0127/fault-injection-run.schema.json",
    "command-center/p2-wave/probes/ADV-0127/clock_lib.py",
    "command-center/p2-wave/probes/ADV-0127/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0127/probe1_static_audit.py",
    "command-center/p2-wave/probes/ADV-0127/probe2_behavioral.py",
    "tools/command-center/close.py",
    "tools/marketplace/vuln_ingestion.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    import os
    import re

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # cmd.exe cannot run POSIX "VAR=value command" prefixes; hoist them.
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": "ADV-0127",
        "receipt_path": "command-center/p2-wave/probes/ADV-0127/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ret_path = PROBE / "SUBAGENT-RETURN.json"
    man_path = PROBE / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_path.is_file() or not man_path.is_file():
        print("FAILED:adv0127w4 receipt files absent")
        return 1
    ret = json.loads(ret_path.read_text(encoding="utf-8"))
    man = json.loads(man_path.read_text(encoding="utf-8"))

    c0, t0 = run_probe(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0127/emit_artifact.py"
    )
    if c0 != 0:
        print(f"FAILED:adv0127w4 emit c={c0}")
        print(t0[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:adv0127w4 probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    primary = row(OUT, "primary")
    # refresh named probes
    ret["named_probes"] = [
        {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
        {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
    ]
    arts = ret.get("artifacts") or []
    if arts and arts[0].get("path") == OUT:
        arts[0]["sha256"] = primary["sha256"]
        arts[0]["bytes"] = primary["bytes"]
        arts[0]["exists"] = True
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = (
        "Wave-4 builder 2026-10-26: live-tree drift repair. Concurrent fleet "
        "work removed parse_iso_z/iso_z/with_retry from "
        "tools/marketplace/vuln_ingestion.py and added a naive-strptime "
        "freshness() gate; static_audit re-measured (fingerprint refreshed), "
        "behavioral re-anchored on the live vi.freshness()/now_iso() paths, "
        "census detector now classifies datetime.strptime as naive-local, and "
        "TARGET-RETRY-BACKOFF is disclosed NOT-CHECKED (anchor removed). Both "
        "named probes re-run exit 0; artifact re-emitted canonically. Receipt "
        "form unchanged: state BLOCKED / failure reviewer-absent; prior "
        "mechanical closure kept in extensions.prev_closure for the "
        "independent reviewer to confirm or overturn."
    )
    prev_notes = str(ret.get("notes") or "").strip()
    ret["notes"] = (prev_notes + "\n" if prev_notes else "") + note
    ret["ts"] = now
    ext = ret.setdefault("extensions", {})
    w4 = ext.setdefault("wave4_2026_10_26", {})
    w4["action"] = "drift repair: static_audit re-measured + behavioral re-anchored on live vi.freshness; probes exit 0; receipt form preserved"
    w4["artifacts_sha256"] = primary["sha256"]
    w4["probes_exit"] = [c1, c2]

    # refresh manifest rows
    rows = {a.get("path"): a for a in man.get("artifacts") or []}
    for rel in [OUT] + SUPPORTING:
        r = row(rel, "primary" if rel == OUT else "supporting")
        if rel in rows:
            rows[rel].update(r)
        else:
            man.setdefault("artifacts", []).append(r)
    man["verified_on_disk"] = True
    man["present"] = sum(1 for a in man["artifacts"] if a.get("present"))
    man["expected"] = len(man["artifacts"])

    ret_path.write_text(json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    man_path.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0127 wave-4 receipts refreshed (BLOCKED/reviewer-absent preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
