#!/usr/bin/env python3
"""Restore leftover-fill victims: merge extensions.legacy_root back to the root."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
KEEP = {
    "schema_version",
    "unit_id",
    "state",
    "disposition",
    "sentinel",
    "profile",
    "spec_anchor",
    "min_bytes_threshold",
    "artifacts",
    "evidence",
    "tests",
    "negative_controls",
    "reviewer",
    "defects",
    "manifest_registration",
    "downstream_consumers",
    "timestamps",
    "retry",
    "failure",
    "residual_unknowns",
    "produced_by",
    "report",
    "extensions",
}


def unfill(path: Path) -> bool:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return False
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    legacy = ext.get("legacy_root") if isinstance(ext.get("legacy_root"), dict) else {}
    if not legacy:
        return False
    merged = dict(legacy)
    for k, v in doc.items():
        if k in KEEP and k not in merged and k != "extensions":
            merged[k] = v
    # drop leftover-only envelope keys that local schemas reject
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return True


def main() -> int:
    uids = sys.argv[1:]
    by = {u["id"]: u for u in CATALOG["work_units"]}
    n = 0
    for uid in uids:
        rel = str((by.get(uid) or {}).get("output_path") or "").replace("\\", "/")
        if not rel:
            print("skip", uid, "no-output")
            continue
        path = REPO / rel
        if not path.is_file():
            print("skip", uid, "missing")
            continue
        if unfill(path):
            n += 1
            print("UNFILL", uid, rel)
        else:
            print("noop", uid)
    print("unfilled", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
