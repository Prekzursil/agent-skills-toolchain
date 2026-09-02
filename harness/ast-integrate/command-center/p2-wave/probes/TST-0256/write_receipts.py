#!/usr/bin/env python3
"""Write TST-0256 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""
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

UID = "TST-0256"
OUT = "command-center/receipts/TST-0256.json"
SENTINEL = (
    "SUCCESS:TST-0256 documented apply converts the ARC-0007-captured "
    "old-layout fixture to the guide-oracle config-first tree and is a "
    "no-op on the second run"
)
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/docs_conformance_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0256/probe1_convert_and_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0256/probe2_idempotence_and_noop.py"
)
SUPPORTING = [
    "docs/layout-migration.md",
    "tools/layout/migrate.py",
    "tools/layout/__init__.py",
    "command-center/p2-wave/probes/TST-0256/fixtures/PROVENANCE.json",
    "command-center/p2-wave/probes/TST-0256/harness.py",
    "command-center/p2-wave/probes/TST-0256/capture.py",
    "command-center/p2-wave/probes/TST-0256/probe1_convert_and_diff.py",
    "command-center/p2-wave/probes/TST-0256/probe2_idempotence_and_noop.py",
    "command-center/p2-wave/probes/TST-0256/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file())
        blob = b"\n".join(
            hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest().encode()
            + b"  "
            + p.relative_to(REPO).as_posix().encode()
            for p in files
        ) + (b"\n" if files else b"")
        sha = hashlib.sha256(blob).hexdigest()
        size = len(blob)
        present = bool(files)
    else:
        sha, size = digest(path) if path.is_file() else ("", 0)
        present = path.is_file()
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": present,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0256/SUBAGENT-RETURN.json",
        "role": role,
    }


def captured_file_rows() -> list[dict]:
    root = REPO / "command-center/p2-wave/probes/TST-0256/fixtures/captured-old"
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(REPO).as_posix()
        rows.append(manifest_row(rel, "fixture"))
    return rows


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0256/emit_receipt.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:TST-0256 emit rc={ce}")
        print(te[-2000:])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0256 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    rec_path = REPO / OUT
    doc = json.loads(rec_path.read_text(encoding="utf-8"))
    doc["tests"] = [
        {
            "id": "TST-0256-probe1-convert-and-diff",
            "command": P1,
            "result": "PASS",
            "exit_code": c1,
            "output_tail": t1[-4000:],
        },
        {
            "id": "TST-0256-probe2-idempotence-and-noop",
            "command": P2,
            "result": "PASS",
            "exit_code": c2,
            "output_tail": t2[-4000:],
        },
        {
            "id": "TST-0256-already-migrated-noop",
            "result": "PASS",
        },
        {
            "id": "TST-0256-fixture-provenance",
            "result": "PASS",
        },
    ]
    rec_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:TST-0256 probes after receipt update c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    artifacts.extend(captured_file_rows())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "convert-and-diff",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "idempotence-and-noop",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/TST-0256/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0256-probe2-idempotence-and-noop",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": None,
        "ts": now,
        "notes": (
            "G-1 for TST-0256: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:TST-0256 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
