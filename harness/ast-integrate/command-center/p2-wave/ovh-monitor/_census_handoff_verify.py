#!/usr/bin/env python3
"""This-turn dual-signal census verification. Prints machine-readable blocks."""
from __future__ import annotations

import collections
import hashlib
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
FILES = {
    "summary": BASE / "g1-local-full.json",
    "jsonl": BASE / "g1-local-full.jsonl",
    "heartbeat": BASE / "g1-local-heartbeat.json",
    "mod": BASE / "g1-mod-census.json",
    "classes": BASE / "g1-shards" / "classes.json",
    "remaining": BASE / "g1-shards" / "remaining_ids.txt",
    "census": BASE / "g1-until-green-census.md",
    "catalog": BASE.parent.parent / "WORK-UNIT-CATALOG.json",
}


def main() -> int:
    print("===FILES===")
    for key, path in FILES.items():
        st = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        mtime = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        print(f"{key}\t{st.st_size}\t{mtime}\t{digest}\t{path}")

    summary = json.loads(FILES["summary"].read_text(encoding="utf-8"))
    classes = json.loads(FILES["classes"].read_text(encoding="utf-8"))
    heart = json.loads(FILES["heartbeat"].read_text(encoding="utf-8"))
    mod = json.loads(FILES["mod"].read_text(encoding="utf-8"))
    cat = json.loads(FILES["catalog"].read_text(encoding="utf-8"))
    cat_ids = [u["id"] for u in cat["work_units"]]

    n = ok = fail = 0
    seen: dict[str, dict] = {}
    cls: collections.Counter[str] = collections.Counter()
    ok_ids: list[str] = []
    fail_recs: list[dict] = []
    with FILES["jsonl"].open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            n += 1
            uid = rec.get("id")
            seen[uid] = rec
            cls[rec.get("cls") or "?"] += 1
            if rec.get("ok"):
                ok += 1
                ok_ids.append(uid)
            else:
                fail += 1
                fail_recs.append(rec)

    missing = [u for u in cat_ids if u not in seen]
    extra = [u for u in seen if u not in set(cat_ids)]
    rem_ids = [ln.strip() for ln in FILES["remaining"].read_text(encoding="utf-8").splitlines() if ln.strip()]
    fp = hashlib.sha256(FILES["remaining"].read_bytes()).hexdigest()
    fail_ids = [r["id"] for r in fail_recs]

    print("===COUNTS===")
    print(
        json.dumps(
            {
                "catalog": len(cat_ids),
                "jsonl_n": n,
                "unique": len(seen),
                "missing": len(missing),
                "extra": len(extra),
                "jsonl_ok": ok,
                "jsonl_fail": fail,
                "summary_n": summary.get("n"),
                "summary_ok": summary.get("ok"),
                "summary_fail": summary.get("fail"),
                "summary_ts": summary.get("ts"),
                "resume": summary.get("resume"),
                "jsonl_unique_field": summary.get("jsonl_unique"),
                "heartbeat_done": heart.get("done"),
                "heartbeat_n": heart.get("n"),
                "heartbeat_ok": heart.get("ok"),
                "heartbeat_fail": heart.get("fail"),
                "resume_finished": heart.get("resume_finished"),
                "classes_n": classes.get("n"),
                "classes_ok": classes.get("ok"),
                "classes_fail": classes.get("fail"),
                "remaining_n": classes.get("remaining_n"),
                "remaining_fp_classes": classes.get("remaining_fp"),
                "remaining_path": classes.get("remaining_path"),
                "remaining_file_n": len(rem_ids),
                "remaining_fp_file": fp,
                "fp_match": fp == classes.get("remaining_fp"),
                "remaining_set_eq": set(rem_ids) == set(fail_ids),
                "cls": dict(cls.most_common()),
                "buckets": classes.get("classes"),
                "mods": mod.get("mods"),
                "sizes_sum": sum(classes.get("sizes") or []),
                "ok_samples": [(uid, seen[uid].get("line", "")[:160]) for uid in ok_ids[:5]],
            },
            indent=2,
        )
    )
    print("===FAIL_BY_CLS===")
    by: dict[str, list] = collections.defaultdict(list)
    for rec in fail_recs:
        by[rec.get("cls") or "?"].append(rec)
    for key, recs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        first = recs[0]
        print(f"{key}\tn={len(recs)}\tfirst={first['id']}\tline={(first.get('line') or '')[:220]}")
        bits = [ln for ln in (first.get("tail") or "").splitlines() if ln.strip()][-4:]
        for ln in bits:
            print("  ", ln[:220])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
