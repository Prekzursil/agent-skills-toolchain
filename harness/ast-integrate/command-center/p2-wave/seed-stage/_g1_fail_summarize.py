#!/usr/bin/env python3
"""Summarize class-other.measure.jsonl tails for the next fix pass."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "ovh-monitor" / "g1-shards" / "class-other.measure.jsonl"
MOD_RE = re.compile(r"No module named '([^']+)'")
FILE_RE = re.compile(r"(?:No such file or directory|can't open file|FileNotFoundError)[:\s]*'?([^'\n]{1,200})")
FAILED_RE = re.compile(r"FAILED:[A-Z0-9-]+(?:-probe\d)?[^\n]{0,160}")


def main() -> int:
    mods = Counter()
    files = Counter()
    failed = Counter()
    cls = Counter()
    samples: dict[str, list] = {}
    n = 0
    for line in P.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        n += 1
        if rec.get("ok"):
            continue
        c = rec.get("cls") or "?"
        cls[c] += 1
        tail = rec.get("tail") or ""
        for m in MOD_RE.findall(tail):
            mods[m] += 1
        for m in FILE_RE.findall(tail):
            files[m.strip()[:120]] += 1
        fm = FAILED_RE.findall(tail)
        if fm:
            failed[fm[-1][:160]] += 1
        samples.setdefault(c, []).append({"id": rec.get("id"), "tail": tail[-500:]})
    out = {
        "n": n,
        "cls": dict(cls),
        "mods": dict(mods.most_common()),
        "files": dict(files.most_common(40)),
        "failed_msgs": dict(failed.most_common(40)),
        "sample_ids": {k: [x["id"] for x in v[:8]] for k, v in samples.items()},
    }
    dest = P.with_name("class-other.fail-summary.json")
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n", "cls", "mods")}, indent=2))
    print("files", json.dumps(out["files"], indent=2)[:2500])
    print("failed", json.dumps(out["failed_msgs"], indent=2)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
