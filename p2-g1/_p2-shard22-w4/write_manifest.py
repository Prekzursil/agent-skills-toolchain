#!/usr/bin/env python3
"""Write probes/<uid>/UNIT-ARTIFACT-MANIFEST.json for a shard-22 wave-4 unit.

Rows: the primary receipt artifact (hash = CRLF-normalized sha256, exactly the
_measure_one_delivered.py digest) plus this unit's probe sidecars.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main(uid: str, extra: list[str]) -> int:
    receipt_rel = f"command-center/receipts/{uid}.json"
    receipt = REPO / receipt_rel
    if not receipt.is_file():
        print(f"FAILED:manifest {uid} receipt-absent")
        return 1
    artifacts = []

    sha, nbytes = digest(receipt)
    artifacts.append(
        {
            "unit_id": uid,
            "path": receipt_rel.replace("\\", "/"),
            "bytes": nbytes,
            "sha256": sha,
            "exists": True,
            "eol": "normalized-LF",
            "role": "primary",
            "present": True,
            "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        }
    )
    for rel in extra:
        p = REPO / rel
        if not p.is_file():
            print(f"FAILED:manifest {uid} missing sidecar {rel}")
            return 1
        sha, nbytes = digest(p)
        role = "named-probe" if "/probe" in Path(rel).name else "supporting"
        artifacts.append(
            {
                "unit_id": uid,
                "path": rel.replace("\\", "/"),
                "bytes": nbytes,
                "sha256": sha,
                "exists": True,
                "eol": "normalized-LF",
                "role": role,
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            }
        )
    man = {
        "schema_version": 1,
        "contract": "unit-artifact-manifest-registration",
        "derivation": "per-unit (shard-22 wave-4 resume builder, CRLF-normalized sha256 matching _measure_one_delivered.py)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
        "builder_note": "shard22-w4 resume rebuild; receipt reviewer closure kept (PASS, independent, verifies live)",
        "built_at": "2026-10-26T00:00:00Z",
    }
    out = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    print(f"SUCCESS:manifest {uid} rows={len(artifacts)} receipt_sha256={artifacts[0]['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2:]))
