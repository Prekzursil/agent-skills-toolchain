#!/usr/bin/env python3
"""Emit probe1_delivery_predicate.py for a unit (shard 21 w2 resume)."""
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
TEMPLATE = '''#!/usr/bin/env python3
"""probe1 delivery predicate for {uid} (shard21 w2 resume).

Checks the builder-phase predicate end to end:
  * receipt parses, admits via receipt_validate (C1-C4)
  * state=BLOCKED, failure.classification contains reviewer-absent
  * catalog completion sentinel present in text (binding, not a success claim)
  * UNIT-ARTIFACT-MANIFEST row sha256 (CRLF-normalized) matches the live artifact
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "{uid}"
RECEIPT = REPO / "command-center" / "receipts" / (UID + ".json")
PROBE_DIR = REPO / "command-center" / "p2-wave" / "probes" / UID
MANIFEST = PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json"
RETURN = PROBE_DIR / "SUBAGENT-RETURN.json"


def digest_lf(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    checks: dict[str, bool] = {{}}
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks["receipt_parses"] = True
    checks["unit_id_matches"] = doc.get("unit_id") == UID
    checks["state_blocked"] = str(doc.get("state")) == "BLOCKED"
    failure = doc.get("failure") or {{}}
    checks["failure_reviewer_absent"] = "reviewer-absent" in (failure.get("classification") or [])
    catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next((u for u in catalog["work_units"] if u.get("id") == UID), {{}})
    sentinel = str(unit.get("completion_sentinel") or "")
    checks["catalog_sentinel_in_text"] = bool(sentinel) and sentinel in RECEIPT.read_text(encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-I", str(REPO / "command-center" / "receipt_validate.py"), str(RECEIPT)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    checks["receipt_admits"] = proc.returncode == 0
    if proc.returncode != 0:
        print(proc.stdout[-2000:], proc.stderr[-500:])
    ret = json.loads(RETURN.read_text(encoding="utf-8"))
    checks["return_delivered"] = str(ret.get("status")).upper() == "DELIVERED"
    ret_failure = ret.get("failure") or {{}}
    checks["return_reviewer_absent"] = "reviewer-absent" in (ret_failure.get("classification") or [])
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out_rel = str(unit.get("output_path") or "").replace("\\\\", "/")
    rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UID]
    checks["manifest_row_present"] = any(
        str(a.get("path", "")).replace("\\\\", "/") == out_rel and a.get("present") is True for a in rows
    )
    row = next((a for a in rows if str(a.get("path", "")).replace("\\\\", "/") == out_rel), {{}})
    checks["manifest_sha_matches_live"] = bool(row) and row.get("sha256") == digest_lf(RECEIPT)
    all_probe_rows_present = True
    for a in rows:
        p = REPO / str(a.get("path", ""))
        if not p.is_file():
            all_probe_rows_present = False
        elif a.get("sha256") and a.get("sha256") != digest_lf(p):
            all_probe_rows_present = False
    checks["all_manifest_rows_verify"] = all_probe_rows_present
    ok = all(checks.values())
    out = {{"unit_id": UID, "probe": "probe1-delivery-predicate", "pass": ok, "checks": checks}}
    print(json.dumps(out))
    if ok:
        print(f"SUCCESS:{{UID}}-probe1 delivery predicate: admission ACCEPT, BLOCKED/reviewer-absent, sentinel binds, manifest sha matches live")
        return 0
    print(f"FAILED:{{UID}}-probe1 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

def main() -> int:
    uid = sys.argv[1]
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    probe_dir.mkdir(parents=True, exist_ok=True)
    out = probe_dir / "probe1_delivery_predicate.py"
    out.write_text(TEMPLATE.format(uid=uid), encoding="utf-8", newline="\n")
    print("wrote", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
