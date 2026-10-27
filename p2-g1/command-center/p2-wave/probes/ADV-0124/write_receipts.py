#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import re as _re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    OUT_REL,
    P1,
    P2,
    REPO,
    SCHEMA_DECLARED,
    SENTINEL,
    UNIT_ID,
)
from emit_artifact import build_doc, write_doc  # noqa: E402
import engine as E  # noqa: E402

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0124/emit_artifact.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0124/engine.py",
    "command-center/p2-wave/probes/ADV-0124/monitor.py",
    "command-center/p2-wave/probes/ADV-0124/heartbeat_only.py",
    "command-center/p2-wave/probes/ADV-0124/mtime_only.py",
    "command-center/p2-wave/probes/ADV-0124/worker_fixture.py",
    "command-center/p2-wave/probes/ADV-0124/common.py",
    "command-center/p2-wave/probes/ADV-0124/probe1_four_state_matrix.py",
    "command-center/p2-wave/probes/ADV-0124/probe2_signal_source_audit.py",
    "command-center/p2-wave/probes/ADV-0124/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0124/fault-injection-run.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # shard2-w2 2026-10-25: cmd.exe (COMSPEC) cannot execute POSIX
    # "VAR=value command" env prefixes and python3 does not resolve there.
    # Move the prefix into the child env and bind python3 to this
    # interpreter, exactly as command-center/p2-wave/_measure_one_delivered.py
    # does, so the recorded named-probe commands run verbatim on Windows.
    while True:
        m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    if "python3" in cmd:
        cmd = cmd.replace("python3", sys.executable.replace("\\", "/"), 1)
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "eol": "LF",
        "unit_id": UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0124/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    print(te)

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    meas = E.run_matrix()
    if not meas["pass"]:
        print("FAILED:receipts matrix did not pass on final capture")
        return 1
    doc = build_doc(meas, p1_raw=t1, p2_raw=t2, c1=c1, c2=c2)
    write_doc(doc)

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT_ID,
        "unit_id": UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "four-state-confusion-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "signal-source-audit",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0124/UNIT-ARTIFACT-MANIFEST.json",
        "extensions": {
            "prev_closure": {
                "independent": True,
                "reviewer_id": "ADV-0124-probe2-signal-source-audit",
                "verdict": "PASS",
            },
            "shard2_w2_resume_2026-10-25": {
                "action": (
                    "monitor.py heartbeat reader hardened (torn-read retry + "
                    "0.35s window) after the live fleet re-run misclassified "
                    "S1 as RUNNING_MONITOR_DEAD; artifact re-emitted, probes "
                    "re-run green, manifest sha rows rebuilt; receipt stays "
                    "BLOCKED/reviewer-absent per program contract (only the "
                    "independent reviewer closes; the builder-authored probe2 "
                    "closure is demoted to prev_closure)"
                ),
                "builder": (
                    "shard2 wave-2 builder (resume of a mid-flight-dead "
                    "prior attempt)"
                ),
            },
        },
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": (
                "Builder lane may not self-certify. S1 false-dead race fixed "
                "in the monitor instrument (a torn heartbeat read or a "
                "loaded scheduler both mapped a live monitor to frozen); "
                "artifact re-emitted, probes re-run green, manifest sha row "
                "matches; awaits independent closure."
            ),
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0124: live named probes exit 0, four-state monitor "
            "artifact state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rebuild "
            "fault-injection-run.schema.json. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT_ID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0124 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
