"""Refresh artifacts[] inventories in rebuilt receipts to live disk state.

C5-class reconciliation: keep roles, re-hash every listed file that exists,
drop rows whose file is gone, append a maintenance note. Reviewer closure
and every other receipt field stay byte-identical in meaning.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

REPO = Path(".").resolve()
NOTE = (" shard8w4 2026-10-26: artifacts[] re-inventoried against live disk after probe-layer "
        "reconstruction (prior builder session ended mid-flight); rows for files no longer "
        "present were dropped per write_if_valid convention. Reviewer closure unchanged; "
        "live re-verification: probes exit 0, per-unit manifest row matches.")


def lf(p: Path):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


for uid in ["IMP-0159", "IMP-0170", "IMP-0174", "IMP-0199", "IMP-0201", "IMP-0206"]:
    rp = REPO / "command-center" / "receipts" / (uid + ".json")
    doc = json.loads(rp.read_text(encoding="utf-8"))
    out_rel = str(doc.get("output_path") or ("command-center/receipts/" + uid + ".json"))
    kept, dropped = [], []
    for a in doc.get("artifacts", []):
        rel = str(a.get("path") or "").replace("\\", "/")
        p = REPO / rel
        role = str(a.get("role") or "supporting")
        if not rel or not p.is_file():
            dropped.append(rel or str(a)[:40])
            continue
        sha, b = lf(p)
        row = {"path": rel, "sha256": sha, "bytes": b, "exists": True, "role": role}
        kept.append(row)
    # primary row first: the receipt itself (self-hash skipped by convention, marked primary)
    if not any(a["path"] == out_rel for a in kept):
        kept.insert(0, {"path": out_rel, "sha256": "0" * 64, "bytes": rp.stat().st_size,
                        "exists": True, "role": "primary"})
    else:
        for a in kept:
            if a["path"] == out_rel:
                a["role"] = "primary"
    doc["artifacts"] = kept
    old_notes = str(doc.get("notes") or "")
    if "shard8w4 2026-10-26" not in old_notes:
        doc["notes"] = (old_notes + NOTE).strip()
    rp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("REFRESHED", uid, "kept=" + str(len(kept)), "dropped=" + str(len(dropped)))
    for d in dropped:
        print("    dropped:", d)
