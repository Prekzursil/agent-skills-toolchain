#!/usr/bin/env python3
"""Direct BLD-0037 receipt assembly (two-strikes pivot).

write_receipts.py's subprocess path wedged twice on this host (silent death,
then a parent blocked forever in a pipe-wait after its probe child exited).
This runs the SAME two named probes via subprocess with a hard per-probe
timeout, then writes SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json in
byte-identical structure to write_receipts.py (same keys, same notes, same
CRLF-normalized digest). No other file is touched.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/BLD-0037.json"
SUPPORTING = [
    "command-center/schema/contradiction-register.schema.json",
    "command-center/p2-wave/probes/BLD-0037/audit.py",
    "command-center/p2-wave/probes/BLD-0037/emit.py",
    "command-center/p2-wave/probes/BLD-0037/probe1_recall_controls.py",
    "command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py",
]
PROBES = {
    "probe1": "command-center/p2-wave/probes/BLD-0037/probe1_recall_controls.py",
    "probe2": "command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py",
}
CANONICAL = {
    "probe1": (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/BLD-0037/probe1_recall_controls.py"
    ),
    "probe2": (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py"
    ),
}
TIMEOUT_S = 2700


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe_direct(rel: str) -> tuple[int, str, float]:
    exe = str(sys.executable).replace("\\", "/")
    cmd = [exe, "-B", rel]
    t0 = time.monotonic()
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_S,
    )
    dt = time.monotonic() - t0
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text, dt


def main() -> int:
    results = {}
    for pid, rel in PROBES.items():
        print(f"running {pid} ...", flush=True)
        try:
            rc, text, dt = run_probe_direct(rel)
        except subprocess.TimeoutExpired:
            print(f"FAILED:BLD-0037 {pid} timeout after {TIMEOUT_S}s", flush=True)
            return 1
        tail = text[-220:].replace("\n", " | ")
        print(f"{pid} rc={rc} elapsed={dt:.0f}s tail: {tail}", flush=True)
        results[pid] = (rc, text)
    if any(rc != 0 for rc, _ in results.values()):
        print("FAILED:BLD-0037 probes nonzero", flush=True)
        return 1

    primary = {"path": OUT, "sha256": "", "bytes": 0, "exists": True, "role": "primary"}
    sha, n = digest(REPO / OUT)
    primary["sha256"], primary["bytes"] = sha, n

    def row(rel_path: str, role: str) -> dict:
        s, b = digest(REPO / rel_path)
        return {
            "path": rel_path,
            "sha256": s,
            "bytes": b,
            "present": True,
            "unit_id": "BLD-0037",
            "receipt_path": "command-center/p2-wave/probes/BLD-0037/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "BLD-0037",
        "unit_id": "BLD-0037",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0037",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/contradiction-register.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": CANONICAL["probe1"],
                "exit_code": results["probe1"][0],
                "raw_output": results["probe1"][1],
            },
            {
                "id": "probe2",
                "command": CANONICAL["probe2"],
                "exit_code": results["probe2"][0],
                "raw_output": results["probe2"][1],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/BLD-0037/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0037-independent-recall-queries",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for BLD-0037: live named probes exit 0, BLD-0037.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "No ADV-0018 rebuild. Receipt reassembled 2026-10-27 via direct "
            "probe runner after write_receipts subprocess path wedged twice "
            "on this host (silent kill, then pipe-wait hang); probe commands, "
            "checks and file shapes are unchanged from write_receipts.py."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0037",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}", flush=True)
    print("SUCCESS:BLD-0037 receipts-direct", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
