#!/usr/bin/env python3
"""Split the latest G-1 jsonl fails into class files, remaining_ids, and 24 shards.

Deterministic. Census agents must run this and copy numbers from classes.json;
they must not invent remaining_n=0.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
SUMMARY = WAVE / "ovh-monitor" / "g1-local-full.json"
OUT = WAVE / "ovh-monitor" / "g1-shards"
N_SHARDS = 24

BUCKETS = (
    "mod",
    "probe-missing",
    "probe-exit",
    "schema",
    "sha",
    "sentinel",
    "predicate",
    "output",
    "env",
    "other",
)


def bucket(rec: dict) -> str | None:
    if rec.get("ok"):
        return None
    cls = str(rec.get("cls") or "")
    line = str(rec.get("line") or "")
    tail = str(rec.get("tail") or "")
    blob = f"{cls}\n{line}\n{tail}".lower()
    if "modulenotfounderror" in blob or "no module named" in blob:
        return "mod"
    if "probe-file-missing" in blob or "no such file" in blob or "can't open file" in blob:
        return "probe-missing"
    if "schema-ref" in blob or "unresolvable" in blob or "refresolutionerror" in blob:
        return "schema"
    if "manifest-sha" in blob:
        return "sha"
    if "self-declared" in blob or "sentinel-absent" in blob or "return:blocked" in blob:
        return "sentinel"
    if (
        "predicate:absent" in blob
        or "catalog-missing" in blob
        or "named-probes-absent" in blob
        or "return-unparseable" in blob
        or "per-unit-manifest" in blob
        or "unparseable" in blob
    ):
        return "predicate"
    if "live-present" in blob:
        return "output"
    if "permissionerror" in blob or "permission denied" in blob:
        return "env"
    if cls == "probe-exit" or "probe-exit" in blob:
        return "probe-exit"
    return "other"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ids_by: dict[str, list[str]] = {k: [] for k in BUCKETS}
    remaining: list[str] = []
    n = ok = fail = 0
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            uid = rec.get("id")
            if not uid:
                continue
            n += 1
            if rec.get("ok"):
                ok += 1
                continue
            fail += 1
            remaining.append(uid)
            ids_by[bucket(rec) or "other"].append(uid)

    remaining_path = OUT / "remaining_ids.txt"
    remaining_path.write_text("".join(uid + "\n" for uid in remaining), encoding="utf-8")
    fp = hashlib.sha256(remaining_path.read_bytes()).hexdigest() if remaining else ""

    for name, uids in ids_by.items():
        (OUT / f"class-{name}.txt").write_text(
            "".join(uid + "\n" for uid in uids), encoding="utf-8"
        )

    for i in range(N_SHARDS):
        (OUT / f"shard-{i:02d}.txt").write_text("", encoding="utf-8")
    for i, uid in enumerate(remaining):
        p = OUT / f"shard-{i % N_SHARDS:02d}.txt"
        with p.open("a", encoding="utf-8") as fh:
            fh.write(uid + "\n")
    sizes = [
        sum(1 for ln in (OUT / f"shard-{i:02d}.txt").read_text(encoding="utf-8").splitlines() if ln.strip())
        for i in range(N_SHARDS)
    ]

    classes = {k: len(v) for k, v in ids_by.items()}
    payload = {
        "n": n,
        "ok": ok,
        "fail": fail,
        "remaining_n": fail,
        "remaining_fp": fp,
        "remaining_path": str(remaining_path),
        "classes": classes,
        "n_shards": N_SHARDS,
        "sizes": sizes,
        "note": "complete() only if n==2007 and ok==2007 and fail==0. Untested is fail.",
    }
    (OUT / "classes.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (OUT / "manifest.json").write_text(
        json.dumps({"n_ids": fail, "n_shards": N_SHARDS, "sizes": sizes, "dir": str(OUT)}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload), flush=True)
    if SUMMARY.is_file():
        try:
            summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
            print(
                json.dumps(
                    {
                        "summary_n": summary.get("n"),
                        "summary_ok": summary.get("ok"),
                        "summary_fail": summary.get("fail"),
                    }
                ),
                flush=True,
            )
        except (OSError, json.JSONDecodeError):
            pass
    return 0 if n == 2007 and ok == 2007 and fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
