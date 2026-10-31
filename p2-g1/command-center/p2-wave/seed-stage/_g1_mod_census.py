#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

JSONL = Path(__file__).resolve().parents[1] / "ovh-monitor" / "g1-local-full.jsonl"
OUT = Path(__file__).resolve().parents[1] / "ovh-monitor" / "g1-mod-census.json"
MOD_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")


def main() -> int:
    cls: Counter[str] = Counter()
    mods: Counter[str] = Counter()
    n = ok = fail = 0
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            n += 1
            c = rec.get("cls") or "?"
            cls[c] += 1
            if rec.get("ok"):
                ok += 1
                continue
            fail += 1
            blob = (rec.get("tail") or "") + "\n" + (rec.get("line") or "")
            for m in MOD_RE.findall(blob):
                mods[m] += 1
    rec = {"n": n, "ok": ok, "fail": fail, "classes": dict(cls.most_common()), "mods": dict(mods.most_common(40))}
    OUT.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
