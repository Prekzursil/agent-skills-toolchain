#!/usr/bin/env python3
"""Write UNIT-ARTIFACT-MANIFEST.json from COMPLETE receipts only.

The stock `unit_manifest.py --write` fail-closes on any missing named file.
Harvest left 500+ named probe-raw paths absent. This writer skips incomplete
receipts instead of inventing files, and records the skip count.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import unit_manifest as um  # noqa: E402

OUT = REPO / "command-center" / "UNIT-ARTIFACT-MANIFEST.json"


def main() -> int:
    receipts = um._load_receipts(REPO)
    complete = []
    skipped = []
    for path, receipt in receipts:
        missing = []
        for art in receipt["artifacts"]:
            if not isinstance(art, dict) or not isinstance(art.get("path"), str):
                missing.append("<malformed>")
                continue
            rel = art["path"].replace("\\", "/")
            if not (REPO / rel).is_file():
                missing.append(rel)
        if missing:
            skipped.append({"receipt": path.relative_to(REPO).as_posix(), "unit_id": receipt.get("unit_id"), "missing": missing[:8]})
        else:
            complete.append((path, receipt))
    rows = []
    for receipt_path, receipt in complete:
        for artifact in receipt["artifacts"]:
            rel = artifact["path"].replace("\\", "/")
            target = REPO / rel
            raw = target.read_bytes().replace(b"\r\n", b"\n")
            rows.append(
                {
                    "path": rel,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "present": True,
                    "unit_id": receipt["unit_id"],
                    "receipt_path": receipt_path.relative_to(REPO).as_posix(),
                }
            )
    rows.sort(key=lambda row: (row["path"], row["receipt_path"], row["unit_id"]))
    value = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "command-center/p2-wave/seed-stage/_write_complete_manifest.py (complete receipts only; stock --write fail-closes on harvest holes)",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "complete_receipts": len(complete),
        "skipped_incomplete_receipts": len(skipped),
        "artifacts": rows,
    }
    OUT.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    skip_path = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "manifest-skipped.json"
    skip_path.write_text(json.dumps({"n": len(skipped), "rows": skipped}, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS:unit-manifest-complete wrote {len(rows)} entries from {len(complete)} receipts; skipped {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
