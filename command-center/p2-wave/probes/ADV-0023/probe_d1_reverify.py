#!/usr/bin/env python3
"""ADV-0023 D1 re-verification (2026-10-21, Windows estate): is the prior P0 still live?

AGENTS.md 9 discipline: NEVER print a secret value. This probe records ONLY:
the ledger path's existence, line count, the NUMBER of dapi-pattern matches and
their line numbers, and the matched prefix class. No file content is emitted.

Two mechanically independent detectors:
  source   : regex scan (dapi[0-9a-fA-F]{32}) over the whole file
  verifier : splitlines + substring-prefix census (no regex), reporting only counts
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LEDGER = Path(r"C:/Users/Prekzursil/.claude/event-ledger/GitHub-f0c32f04/events.jsonl")
RX = re.compile(r"dapi[0-9a-fA-F]{32}")


def main() -> int:
    src: dict = {"method": "regex-scan", "pattern": "dapi[0-9a-fA-F]{32}"}
    ver: dict = {"method": "splitlines-substring-census", "needle_prefix": "dapi"}
    src["ledger_exists"] = LEDGER.is_file()
    if not LEDGER.is_file():
        out = {"date": "2026-10-21", "ledger": str(LEDGER), "source": src,
               "verifier": ver, "conclusion": "ledger absent -> D1 not verifiable here"}
        print("ADV0023_D1_BEGIN"); print(json.dumps(out, indent=2, sort_keys=True)); print("ADV0023_D1_END")
        return 0
    data = LEDGER.read_bytes()
    text = data.decode("utf-8", errors="replace")
    src["total_bytes"] = len(data)
    src["total_lines"] = text.count("\n") + (0 if text.endswith("\n") else 1)
    hits = [(i + 1) for i, line in enumerate(text.splitlines()) if RX.search(line)]
    src["hit_count"] = len(hits)
    src["hit_line_numbers"] = hits
    src["prefix_class_only"] = "dapi"  # value NEVER captured or printed

    lines = text.splitlines()
    ver_hits = []
    for i, line in enumerate(lines):
        # independent: count occurrences of the literal prefix, then length-class the
        # following 32 chars WITHOUT emitting them
        idx = 0
        found = False
        while True:
            j = line.find("dapi", idx)
            if j < 0:
                break
            tail = line[j + 4:j + 4 + 32]
            if len(tail) == 32 and all(c in "0123456789abcdefABCDEF" for c in tail):
                found = True
                break
            idx = j + 4
        if found:
            ver_hits.append(i + 1)
    ver["hit_line_numbers"] = ver_hits
    ver["hit_count"] = len(ver_hits)
    ver["agrees_with_source"] = ver_hits == hits

    out = {
        "date": "2026-10-21",
        "ledger": str(LEDGER),
        "source": src,
        "verifier": ver,
        "conclusion": (
            "D1 STILL LIVE: the prior P0 secret exposure is present on this estate "
            "today (values never printed; only counts and line numbers recorded)"
            if hits else "no dapi-pattern occurrence found; D1 not reproducible today"
        ),
    }
    print("ADV0023_D1_BEGIN"); print(json.dumps(out, indent=2, sort_keys=True)); print("ADV0023_D1_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
