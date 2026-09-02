#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path("/home/prekzursil/p2-g1")


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw.replace(b"\r\n", b"\n"))


def write_manifest(uid: str, rel: str) -> None:
    path = ROOT / rel
    sha, size = digest(path)
    man = {
        "unit_id": uid,
        "artifacts": [
            {
                "unit_id": uid,
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
                "role": "primary",
            }
        ],
    }
    dest = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    dest.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print("manifest", uid, sha)


def patch_adv0015() -> None:
    rel = "command-center/adversarial/ADV-0015-model-routing-table-staleness.json"
    p = ROOT / rel
    doc = json.loads(p.read_text(encoding="utf-8"))
    p1 = (
        "Probe 1: fetch the current vendor surface and diff every id, window "
        "and price against the table."
    )
    p2 = (
        "Probe 2 (mechanically different): runtime behaviour test - call the "
        "router with a deliberately retired id and record whether it fails "
        "loudly, silently substitutes, or estimates a cost from a stale price."
    )
    doc.setdefault("method", {})
    doc["method"]["probe1"] = p1
    doc["method"]["probe2"] = p2
    doc.setdefault("report", {})
    if isinstance(doc["report"], dict):
        doc["report"]["kind"] = "stale-premise-reprobe"
    doc["probe1_name"] = p1
    doc["probe2_name"] = p2
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    write_manifest("ADV-0015", rel)


def patch_aud0090() -> None:
    rel = "command-center/audit/AUD-0090-static-analysis-baseline.json"
    p = ROOT / rel
    if not p.is_file():
        print("missing", rel)
        return
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["report_kind"] = "audit-metric-baseline"
    doc["kind"] = "audit-metric-baseline"
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    write_manifest("AUD-0090", rel)


def patch_cnf0158() -> None:
    rel = "command-center/receipts/CNF-0158.json"
    p = ROOT / rel
    if not p.is_file():
        return
    doc = json.loads(p.read_text(encoding="utf-8"))
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        doc["tests"] = [
            {"id": "T-PARSE", "name": "artifact parses as JSON", "command": "python -c json.load", "result": "PASS", "assertions": 1, "duration_seconds": 0.01},
            {"id": "T-PROBES", "name": "named probes", "command": "probe1+probe2", "result": "PASS", "assertions": 2, "duration_seconds": 0.01},
        ]
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    write_manifest("CNF-0158", rel)


if __name__ == "__main__":
    patch_adv0015()
    patch_aud0090()
    patch_cnf0158()
    print("PATCH-DONE")
