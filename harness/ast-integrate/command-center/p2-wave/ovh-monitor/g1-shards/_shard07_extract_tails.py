#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-07.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
JSONL = HERE.parent / "g1-local-full.jsonl"
FAILED = re.compile(r"FAILED:[^\n]{0,240}")
MOD = re.compile(r"No module named '([^']+)'")
FILE = re.compile(r"No such file or directory: '([^']+)'")
ATTR = re.compile(r"AttributeError: ([^\n]{0,180})")
TYPE = re.compile(r"TypeError: ([^\n]{0,180})")
ASSERT = re.compile(r"AssertionError: ([^\n]{0,180})")
KEY = re.compile(r"KeyError: ([^\n]{0,120})")
rows = {}
for line in JSONL.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    uid = rec.get("id") or rec.get("uid")
    if uid not in IDS:
        continue
    tail = rec.get("tail") or rec.get("text") or rec.get("out") or ""
    if not tail and rec.get("probes"):
        tail = json.dumps(rec.get("probes"))[-2500:]
    rows[uid] = {
        "ok": rec.get("ok"),
        "last": rec.get("last") or rec.get("reason") or "",
        "failed": FAILED.findall(str(tail))[-3:],
        "mods": MOD.findall(str(tail))[:3],
        "files": FILE.findall(str(tail))[:3],
        "attr": ATTR.findall(str(tail))[:2],
        "type": TYPE.findall(str(tail))[:2],
        "assert": ASSERT.findall(str(tail))[:2],
        "key": KEY.findall(str(tail))[:2],
        "tail": str(tail)[-1800:],
    }
out = HERE / "_shard07_leftover_tails.json"
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(f"wrote {out} n={len(rows)}")
for uid in IDS:
    r = rows.get(uid) or {}
    print(f"{uid}: last={str(r.get('last') or '')[:80]}")
    if r.get("failed"):
        print(f"  fail={r['failed'][-1][:160]}")
    if r.get("mods"):
        print(f"  mod={r['mods']}")
    if r.get("files"):
        print(f"  file={r['files']}")
    if r.get("attr"):
        print(f"  attr={r['attr']}")
    if r.get("type"):
        print(f"  type={r['type']}")
    if r.get("assert"):
        print(f"  assert={r['assert']}")
    if r.get("key"):
        print(f"  key={r['key']}")
