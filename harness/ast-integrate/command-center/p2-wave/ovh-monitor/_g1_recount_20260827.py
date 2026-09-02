#!/usr/bin/env python3
"""Independent dual-signal recount of g1-local-full.jsonl vs WORK-UNIT-CATALOG.json.

Reads only. Prints literal counts; no green/red interpretation beyond arithmetic.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

OVH = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor")
CAT = Path("/home/prekzursil/p2-g1/command-center/WORK-UNIT-CATALOG.json")

catalog_ids = [u["id"] for u in json.loads(CAT.read_text(encoding="utf-8"))["work_units"]]
cat_set = set(catalog_ids)

rows = {}
lines = 0
for line in (OVH / "g1-local-full.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    lines += 1
    rec = json.loads(line)
    rows[rec["id"]] = rec

ok_ids = sorted(uid for uid, r in rows.items() if r.get("ok"))
fail_ids = sorted(uid for uid, r in rows.items() if not r.get("ok"))
missing = sorted(cat_set - set(rows))
extra = sorted(set(rows) - cat_set)
classes = Counter(r.get("cls") or "?" for r in rows.values())

summary = json.loads((OVH / "g1-local-full.json").read_text(encoding="utf-8"))
jsonl_sha = hashlib.sha256((OVH / "g1-local-full.jsonl").read_bytes()).hexdigest()

out = {
    "catalog_n": len(catalog_ids),
    "jsonl_lines": lines,
    "jsonl_unique": len(rows),
    "ok": len(ok_ids),
    "fail": len(fail_ids),
    "missing_from_jsonl": len(missing),
    "extra_not_in_catalog": len(extra),
    "classes": dict(classes.most_common()),
    "summary_file": {k: summary[k] for k in ("ts", "n", "ok", "fail")},
    "match_summary": summary["n"] == len(rows) and summary["ok"] == len(ok_ids) and summary["fail"] == len(fail_ids),
    "jsonl_sha256": jsonl_sha,
    "ok_sample": ok_ids[:5],
    "fail_sample": fail_ids[:5],
}
(OVH / "g1-recount_2026-08-27.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
