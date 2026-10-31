#!/usr/bin/env python3
"""Refresh UNIT-ARTIFACT-MANIFEST.json sha256 rows to the live artifact for given unit IDs.

Per-unit manifests only (never global unit_manifest.py --write). CRLF-normalized
sha256, matching _measure_one_delivered.py digest_file().
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CATALOG["work_units"]}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    for uid in sys.argv[1:]:
        unit = UNITS.get(uid)
        if unit is None:
            print(f"{uid}: NOT-IN-CATALOG")
            continue
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        art = REPO / out_rel
        if not art.is_file():
            print(f"{uid}: artifact missing {out_rel}")
            continue
        live_sha, live_bytes = digest(art)
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man = json.loads(man_path.read_text(encoding="utf-8"))
        rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
        hit = False
        for a in rows:
            if str(a.get("path") or "").replace("\\", "/") == out_rel:
                old = a.get("sha256")
                a["sha256"] = live_sha
                a["bytes"] = live_bytes
                a["present"] = True
                hit = True
                print(f"{uid}: {out_rel} sha {str(old)[:12]}.. -> {live_sha[:12]}.. bytes={live_bytes}")
        if not hit:
            man.setdefault("artifacts", []).append(
                {"unit_id": uid, "path": out_rel, "sha256": live_sha, "bytes": live_bytes, "present": True}
            )
            print(f"{uid}: added manifest row for {out_rel} sha={live_sha[:12]}..")
        man_path.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
