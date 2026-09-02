#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

IDS = {
    "ADV-0139",
    "ARC-0005",
    "ARC-0004",
    "ARC-0049",
    "ARC-0089",
    "AUD-0074",
    "BLD-0036",
    "CNF-0045",
    "CNF-0101",
    "IMP-0025",
    "IMP-0036",
    "RES-0010",
    "RES-0015",
    "RES-0102",
    "RES-0177",
    "TST-0072",
    "WFA-0018",
    "WFA-0039",
    "WFA-0044",
    "WFA-0045",
    "WFA-0133",
    "WFA-0141",
}
JSONL = Path(__file__).resolve().parents[1] / "g1-local-full.jsonl"
SUMMARY = Path(__file__).resolve().parents[1] / "g1-local-full.json"


def main() -> None:
    print("jsonl", JSONL, "exists", JSONL.is_file(), "size", JSONL.stat().st_size if JSONL.is_file() else 0)
    found = {}
    if JSONL.is_file():
        with JSONL.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                uid = rec.get("id")
                if uid in IDS:
                    found[uid] = rec
    print("found", len(found))
    for uid in sorted(IDS):
        rec = found.get(uid)
        print("====", uid)
        if not rec:
            print("  MISSING from jsonl")
            continue
        print("  ok", rec.get("ok"), "cls", rec.get("cls"))
        print("  line", str(rec.get("line") or "")[:400])
        tail = str(rec.get("tail") or "")
        for row in tail.splitlines()[-30:]:
            print("   ", row[:240])


if __name__ == "__main__":
    main()
