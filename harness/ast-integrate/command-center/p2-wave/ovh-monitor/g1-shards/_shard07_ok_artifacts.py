#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
G = Path(__file__).resolve().parent
ART = re.compile(r"artifact (\S+) bytes=(\d+) sha256=([0-9a-f]+)")
rows = {}
for name in ("_shard07_g1_measure.jsonl", "_shard07_g1_remeasure.jsonl"):
    for line in (G / name).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        rows[rec["id"]] = rec
print("ok_with_artifact")
for uid, rec in rows.items():
    if not rec.get("ok"):
        continue
    m = ART.search(rec.get("tail") or "")
    if m:
        print(uid, m.group(1), "bytes", m.group(2), "sha256", m.group(3))
    else:
        print(uid, "SUCCESS_NO_ARTIFACT_LINE_IN_TAIL")
        print(" last=", rec.get("last"))
        print(" tail_end=", (rec.get("tail") or "")[-300:])
