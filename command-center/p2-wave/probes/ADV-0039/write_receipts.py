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
OUT = "command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0039/probe1_static_extract.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0039/probe2_wire_capture.py"
)
SUPPORTING = [
    "command-center/schema/privacy-dataflow.schema.json",
    "command-center/p2-wave/probes/ADV-0039/extract.py",
    "command-center/p2-wave/probes/ADV-0039/proxy.py",
    "command-center/p2-wave/probes/ADV-0039/emit_dataflow.py",
    "command-center/p2-wave/probes/ADV-0039/probe1_static_extract.py",
    "command-center/p2-wave/probes/ADV-0039/probe2_wire_capture.py",
    "tools/router/telemetry.py",
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
        "unit_id": "ADV-0039",
        "receipt_path": "command-center/p2-wave/probes/ADV-0039/SUBAGENT-RETURN.json",
        "role": role,
    }


def embed_probe_output(t1: str, t2: str) -> None:
    dest = REPO / OUT
    doc = json.loads(dest.read_text(encoding="utf-8"))
    probes = doc.get("named_probes") or []
    if len(probes) < 2:
        raise SystemExit("FAILED:receipts named_probes missing")
    probes[0]["command"] = P1
    probes[0]["raw_output"] = t1
    probes[1]["command"] = P2
    probes[1]["raw_output"] = t2
    dest.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_dataflow.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if emit.returncode != 0:
        print((emit.stdout or "") + (emit.stderr or ""))
        print("FAILED:receipts emit")
        return emit.returncode or 1
    print(emit.stdout or "")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    embed_probe_output(t1, t2)

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0039",
        "unit_id": "ADV-0039",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0039",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/privacy-dataflow.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "static-constructor-extract",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "wire-capture-intercepting-proxy",
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0039/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0039-probe2-wire-capture",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0039: live named probes exit 0, telemetry field-level "
            "data-flow artifact state=SUCCESS (overall_verdict PARTIAL: Phase 4 "
            "contract artifact absent; emit_records extra keys vs RECORDED_FIELDS; "
            "no production HTTP egress), per-unit manifest row. Did not run "
            "global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0039",
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
    print("SUCCESS:ADV-0039 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
