#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

JSONL = Path(
    r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave"
    r"\ovh-monitor\g1-shards\class-envelope.measure.jsonl"
)


def main() -> None:
    rows = []
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    fails = [r for r in rows if not r.get("ok")]
    print("n", len(rows), "ok", sum(1 for r in rows if r.get("ok")), "fail", len(fails))
    print("cls", Counter(r.get("cls") for r in fails))
    for cls in ("ModuleNotFoundError", "probe-file-missing", "probe-exit"):
        hits = [r for r in fails if r.get("cls") == cls]
        print(f"\n=== {cls} n={len(hits)} ===")
        for r in hits[:12]:
            tail = (r.get("tail") or r.get("line") or "")[-400:]
            print(r["id"], r.get("line", "")[:120])
            for ln in tail.splitlines()[-6:]:
                print("   ", ln)


if __name__ == "__main__":
    main()
