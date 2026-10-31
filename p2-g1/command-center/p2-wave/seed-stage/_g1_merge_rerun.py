#!/usr/bin/env python3
"""Merge g1-fails-rerun.jsonl (and repair-claude batches) into g1-local-full.jsonl.

Appends the newest row per remeasured ID to the census jsonl (append-only,
never wipes), then recounts the whole catalog taking the LAST row per id.
Writes g1-local-full.json summary + a dual-verification recount file.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MON = Path(__file__).resolve().parent.parent / "ovh-monitor"
REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
MAIN = MON / "g1-local-full.jsonl"
SUMMARY = MON / "g1-local-full.json"
RERUN = MON / "g1-fails-rerun.jsonl"


def load_last(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("id"):
                rows[rec["id"]] = rec
    return rows


def main() -> int:
    catalog = [u["id"] for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]]
    main_rows = load_last(MAIN)
    rerun_rows = load_last(RERUN)
    updates = []
    for uid, rec in rerun_rows.items():
        old = main_rows.get(uid)
        if old is None or json.dumps(old, sort_keys=True) != json.dumps(rec, sort_keys=True):
            updates.append(rec)
    with MAIN.open("a", encoding="utf-8") as fh:
        for rec in updates:
            fh.write(json.dumps(rec) + "\n")
    rows = load_last(MAIN)
    classes: Counter[str] = Counter()
    ok = fail = 0
    fail_ids = []
    for uid in catalog:
        rec = rows.get(uid)
        if rec is None:
            fail += 1
            fail_ids.append(uid)
            classes["unmeasured"] += 1
            continue
        classes[rec.get("cls") or "?"] += 1
        if rec.get("ok"):
            ok += 1
        else:
            fail += 1
            fail_ids.append(uid)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = {
        "ts": ts,
        "n": len(catalog),
        "ok": ok,
        "fail": fail,
        "classes": dict(classes.most_common()),
        "fail_ids_head": fail_ids[:80],
        "fail_n": len(fail_ids),
        "merged_updates": len(updates),
        "note": "merged g1-fails-rerun into census; last row per id wins",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    sha = hashlib.sha256(MAIN.read_bytes()).hexdigest()
    recount = {
        "ts": ts,
        "catalog_n": len(catalog),
        "jsonl_lines": sum(1 for l in MAIN.read_text(encoding="utf-8").splitlines() if l.strip()),
        "jsonl_unique": len(rows),
        "missing": len([u for u in catalog if u not in rows]),
        "ok": ok,
        "fail": fail,
        "jsonl_sha256": sha,
    }
    (MON / "g1-recount-merged_2026-08-27.json").write_text(
        json.dumps(recount, indent=2) + "\n", encoding="utf-8"
    )
    (MON / "repair-claude" / "fail_ids_after_merge.txt").write_text(
        "\n".join(fail_ids) + "\n", encoding="utf-8"
    )
    print(json.dumps({"summary": summary, "recount": recount}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
