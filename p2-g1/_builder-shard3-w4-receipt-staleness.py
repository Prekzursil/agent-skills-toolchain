#!/usr/bin/env python3
"""Verify each receipt's recorded artifact sha256 still matches the live artifact bytes (staleness check)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
IDS = [
    "AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057", "AUD-0064",
    "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072", "AUD-0075", "AUD-0080",
]


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    idx = {u["id"]: u for u in cat["work_units"]}
    stale = []
    for uid in IDS:
        u = idx[uid]
        out = REPO / str(u["output_path"]).replace("\\", "/")
        rec = json.loads((REPO / "command-center/receipts" / f"{uid}.json").read_text(encoding="utf-8"))
        live = digest(out)
        rows = [a for a in (rec.get("artifacts") or []) if str(a.get("path", "")).replace("\\", "/") == str(u["output_path"]).replace("\\", "/")]
        shas = {str(a.get("sha256")) for a in rows}
        ok = live in shas
        rev = rec.get("reviewer") or {}
        print(f"{uid}: receipt_sha_match_live={'yes' if ok else 'NO'} reviewer={rev.get('verdict')} reviewer_id={rev.get('reviewer_id')}")
        if not ok:
            stale.append(uid)
    print("STALE-RECEIPTS:", stale if stale else "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
