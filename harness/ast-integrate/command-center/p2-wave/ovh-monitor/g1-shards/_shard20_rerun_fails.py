#!/usr/bin/env python3
"""Re-run shard-20 IDs that failed Windows probes (diagnosis only)."""
from __future__ import annotations

import json
from pathlib import Path

import _shard20_win_probes as W

HERE = Path(__file__).resolve().parent
PREV = HERE / "_shard20_win_probes.jsonl"
OUT = HERE / "_shard20_win_probes.round2.jsonl"


def main() -> None:
    prev = {}
    if PREV.is_file():
        for line in PREV.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                prev[rec["id"]] = rec
    ids = [
        ln.strip()
        for ln in (HERE / "shard-20.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    with OUT.open("w", encoding="utf-8") as fh:
        for uid in ids:
            old = prev.get(uid)
            if old and old.get("ok"):
                fh.write(json.dumps(old, ensure_ascii=False) + "\n")
                print("keep-ok", uid)
                continue
            rec = W.run_one(uid)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            mark = "OK" if rec.get("ok") else "FAIL"
            fail = (rec.get("fails") or ["?"])[0][:180]
            print(mark, uid, fail if mark == "FAIL" else "probes-pass")
    ok = failn = 0
    for line in OUT.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("ok"):
            ok += 1
        else:
            failn += 1
    print(f"round2 ok={ok} fail={failn} n={ok+failn}")


if __name__ == "__main__":
    main()
