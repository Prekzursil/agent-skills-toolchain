#!/usr/bin/env python3
"""probe1 delivery predicate for {UID} (shard21 w2 resume).

Builder-phase predicate over the receipt end to end:
  * receipt parses and ADMITS via command-center/receipt_validate.py (C1-C4)
  * state=BLOCKED with failure.classification containing reviewer-absent
  * the catalog completion sentinel string is present in the receipt text
    (binding record; NOT a success claim - only the reviewer closes)
  * UNIT-ARTIFACT-MANIFEST.json row for the primary artifact matches the live
    bytes (CRLF-normalised sha256), and every registered row's file exists and
    still hashes to its recorded value.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "{UID}"
RECEIPT = REPO / "command-center" / "receipts" / (UID + ".json")
PROBE_DIR = REPO / "command-center" / "p2-wave" / "probes" / UID
MANIFEST = PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json"
RET = PROBE_DIR / "SUBAGENT-RETURN.json"


def digest_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    checks: dict[str, object] = {}
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    checks["receipt_parses"] = True
    checks["unit_id_matches"] = doc.get("unit_id") == UID
    checks["state_blocked"] = str(doc.get("state")) == "BLOCKED"
    failure = doc.get("failure") or {}
    checks["failure_reviewer_absent"] = "reviewer-absent" in (failure.get("classification") or [])
    catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next((u for u in catalog["work_units"] if u.get("id") == UID), {})
    sentinel = str(unit.get("completion_sentinel") or "")
    checks["catalog_sentinel_in_text"] = bool(sentinel) and sentinel in text
    proc = subprocess.run(
        [sys.executable, "-I", str(REPO / "command-center" / "receipt_validate.py"), str(RECEIPT)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    checks["receipt_admits"] = proc.returncode == 0
    if proc.returncode != 0:
        print(proc.stdout[-1500:], proc.stderr[-400:])
    ret = json.loads(RET.read_text(encoding="utf-8"))
    checks["return_status_delivered"] = str(ret.get("status", "")).upper() == "DELIVERED"
    ret_failure = ret.get("failure") or {}
    checks["return_reviewer_absent"] = "reviewer-absent" in (ret_failure.get("classification") or [])
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out_rel = str(unit.get("output_path", "")).replace("\\", "/")
    rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UID]
    primary = next((a for a in rows if str(a.get("path", "")).replace("\\", "/") == out_rel), {})
    checks["manifest_primary_row_present"] = bool(primary) and primary.get("present") is True
    checks["manifest_primary_sha_matches_live"] = bool(primary) and primary.get("sha256") == digest_lf(RECEIPT)
    all_rows_ok = True
    for a in rows:
        p = REPO / str(a.get("path", ""))
        if not p.is_file():
            all_rows_ok = False
            break
        if a.get("sha256") and a.get("sha256") != digest_lf(p):
            all_rows_ok = False
            break
    checks["every_manifest_row_verifies_live"] = all_rows_ok
    ok = all(bool(v) for v in checks.values())
    out = {
        "unit_id": UID,
        "probe": "probe1-delivery-predicate",
        "pass": ok,
        "checks": checks,
    }
    print(json.dumps(out))
    if ok:
        print(f"SUCCESS:{UID}-probe1 delivery predicate: admission ACCEPT, BLOCKED/reviewer-absent, catalog sentinel binds in text, manifest primary sha matches live, all registered rows verify")
        return 0
    print(f"FAILED:{UID}-probe1 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
