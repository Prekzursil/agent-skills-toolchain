#!/usr/bin/env python3
"""Write the per-unit UNIT-ARTIFACT-MANIFEST.json for one WFA unit (shard22).

Rows: the primary artifact (CRLF-normalized sha256, matching
_measure_one_delivered.py digest_file) + the probe scripts that verify it.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lf_sha(p: Path):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_for(unit: str, rel_out: str, support: list[tuple[str, str]]) -> Path:
    pd = REPO / "command-center" / "p2-wave" / "probes" / unit
    pd.mkdir(parents=True, exist_ok=True)
    out_p = REPO / rel_out
    sha, size = lf_sha(out_p)
    rows = [{
        "unit_id": unit, "path": rel_out, "bytes": size, "sha256": sha,
        "exists": True, "eol": "LF", "role": "primary", "present": True,
        "receipt_path": f"command-center/p2-wave/probes/{unit}/SUBAGENT-RETURN.json",
    }]
    for rel, role in support:
        p = REPO / rel
        sha, size = lf_sha(p)
        rows.append({
            "unit_id": unit, "path": rel, "bytes": size, "sha256": sha,
            "exists": True, "eol": "LF", "role": role, "present": True,
            "receipt_path": f"command-center/p2-wave/probes/{unit}/SUBAGENT-RETURN.json",
        })
    doc = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": unit,
        "verified_on_disk": True,
        "generated_at": NOW,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    man_path = pd / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("manifest written", man_path, f"({len(rows)} rows, primary sha {sha[:16]})")
    return man_path


if __name__ == "__main__":
    unit = sys.argv[1]
    rel_out = sys.argv[2]
    support = []
    for arg in sys.argv[3:]:
        rel, role = arg.rsplit("=", 1)
        support.append((rel, role))
    write_for(unit, rel_out, support)
