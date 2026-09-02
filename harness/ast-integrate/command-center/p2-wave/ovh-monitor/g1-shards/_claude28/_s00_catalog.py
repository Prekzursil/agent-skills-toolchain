#!/usr/bin/env python3
"""Extract catalog output_path for shard-00 remaining IDs. Not a measurement."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
p = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
ids = [
    "ARC-0063",
    "AUD-0010",
    "AUD-0052",
    "AUD-0090",
    "BLD-0027",
    "CNF-0029",
    "CNF-0059",
    "CNF-0145",
    "CNL-0002",
    "CNL-0118",
    "IMP-0060",
    "IMP-0200",
    "IMP-0263",
    "IMP-0358",
    "IMP-0400",
    "RES-0028",
    "RES-0089",
    "RES-0144",
    "RES-0165",
    "SYN-0041",
    "TST-0054",
    "TST-0104",
    "TST-0147",
    "TST-0182",
    "TST-0224",
    "TST-0258",
    "TST-0289",
    "WFA-0025",
    "WFA-0082",
    "WFA-0153",
]
data = json.loads(p.read_text(encoding="utf-8"))
want = set(ids)
found = {}
for u in data.get("work_units") or []:
    uid = u.get("id")
    if uid in want:
        found[uid] = {
            "output_path": u.get("output_path"),
            "completion_sentinel": u.get("completion_sentinel"),
            "output_schema": u.get("output_schema"),
        }

rows = []
for uid in ids:
    info = found.get(uid) or {}
    rel = str(info.get("output_path") or "")
    art = REPO / rel if rel else None
    exists = bool(art and art.is_file())
    keys = []
    reviewer = None
    tests_t = None
    report_kind = None
    if exists:
        try:
            doc = json.loads(art.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                keys = sorted(doc.keys())
                rev = doc.get("reviewer")
                if isinstance(rev, dict):
                    reviewer = rev.get("reviewer_id")
                tests = doc.get("tests")
                tests_t = type(tests).__name__
                report_kind = doc.get("report_kind") or (doc.get("report") or {}).get("kind") if isinstance(doc.get("report"), dict) else doc.get("report_kind")
        except Exception as exc:
            keys = [f"PARSE-ERR:{type(exc).__name__}"]
    rows.append(
        {
            "id": uid,
            "output_path": rel,
            "exists": exists,
            "bytes": art.stat().st_size if exists else 0,
            "reviewer_id": reviewer,
            "tests_type": tests_t,
            "report_kind": report_kind,
            "n_keys": len(keys),
            "sentinel": info.get("completion_sentinel"),
            "schema": info.get("output_schema"),
        }
    )

out = REPO / "command-center/p2-wave/ovh-monitor/g1-shards/_claude28/_s00_catalog.out.json"
out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out} n={len(rows)}")
for r in rows:
    print(f"{r['id']}\texists={r['exists']}\trev={r['reviewer_id']}\ttests={r['tests_type']}\t{r['output_path']}")
