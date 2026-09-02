#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")
FILE_RE = re.compile(r"(?:No such file or directory|can't open file)[: ]+['\"]?([^'\"]+)")
ASSERT_RE = re.compile(r"AssertionError.*|FAILED:[A-Z0-9-]+.*")


def main() -> None:
    rows = []
    for ln in (HERE / "_shard22_measure.jsonl").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
    ok = [r for r in rows if r.get("ok")]
    fail = [r for r in rows if not r.get("ok")]
    print(f"n={len(rows)} ok={len(ok)} fail={len(fail)}")
    print("OK", " ".join(r["id"] for r in ok))
    mods = Counter()
    files = Counter()
    last_fail = Counter()
    for r in fail:
        tail = r.get("tail") or ""
        last = r.get("line") or ""
        m = MOD_RE.findall(tail)
        f = FILE_RE.findall(tail)
        for x in m:
            mods[x] += 1
        for x in f:
            files[x] += 1
        fails = [ln.strip() for ln in tail.splitlines() if "FAILED:" in ln or "Error" in ln or "assert " in ln.lower() or "AssertionError" in ln]
        key = fails[-1][:180] if fails else last[:180]
        last_fail[key] += 1
        print("=" * 72)
        print(r["id"], r.get("cls"), r.get("line")[:120])
        for ln in (tail.splitlines()[-12:]):
            print("  ", ln[:220])
    print("\nMODS", dict(mods))
    print("FILES", dict(files.most_common(20)))
    print("LAST_FAIL")
    for k, v in last_fail.most_common():
        print(f"  {v:2d} {k}")


if __name__ == "__main__":
    main()
