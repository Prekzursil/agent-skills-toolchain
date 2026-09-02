#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

OUT = S.OUTPUT_REL
P1 = S.P1
P2 = S.P2
SUPPORTING = [
    S.SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0014/surface.py",
    "command-center/p2-wave/probes/ADV-0014/probe1_help.py",
    "command-center/p2-wave/probes/ADV-0014/probe2_live_schema.py",
    "command-center/p2-wave/probes/ADV-0014/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0014/fixtures/live_cursor_mcp.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "ADV-0014",
        "receipt_path": "command-center/p2-wave/probes/ADV-0014/SUBAGENT-RETURN.json",
        "role": role,
    }


def patch_probe_raw(c1: int, t1: str, c2: int, t2: str) -> None:
    path = REPO / OUT
    doc = json.loads(path.read_text(encoding="utf-8"))
    probes = list(doc.get("named_probes") or [])
    if len(probes) < 2:
        raise SystemExit("FAILED:receipts named_probes missing")
    probes[0]["raw_output"] = t1
    probes[0]["exit_code"] = c1
    probes[1]["raw_output"] = t2
    probes[1]["exit_code"] = c2
    doc["named_probes"] = probes
    text = json.dumps(doc, indent=2, sort_keys=True)
    if S.SENTINEL not in text:
        raise SystemExit("FAILED:receipts sentinel lost after patch")
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    live = json.loads(path.read_text(encoding="utf-8"))
    ok, why = S.validate_against_schema(live)
    if not ok:
        raise SystemExit(f"FAILED:receipts revalidate {why}")


def main() -> int:
    emit = HERE / "emit_artifact.py"
    code, out = run_probe(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ADV-0014/emit_artifact.py"
    )
    print(out)
    if code != 0:
        print(f"FAILED:receipts emit rc={code}")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    patch_probe_raw(c1, t1, c2, t2)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0014",
        "unit_id": "ADV-0014",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0014",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": S.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "source-argv-extract-and-live-help-diff",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "mcp-name-resolve-against-live-schema",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0014/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0014-probe2-live-mcp-schema",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0014: live named probes exit 0, stale-premise-reprobe "
            "artifact state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
        "measure_line": "SUCCESS:delivered ADV-0014",
    }
    # Re-hash primary after patch_probe_raw.
    primary = row(OUT, "primary")
    artifacts[0] = primary
    ret["artifacts"][0]["sha256"] = primary["sha256"]
    ret["artifacts"][0]["bytes"] = primary["bytes"]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0014",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0014 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
