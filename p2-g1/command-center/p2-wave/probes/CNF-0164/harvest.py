#!/usr/bin/env python3
"""CNF-0164 corpus harvester.

Re-derives the corpus case rows live: reads the phase3 origin artifact's
evidence rows (snippets presented as quotes of a cited path), then classifies
each snippet against the CURRENT worktree bytes at the cited path using the
recorded staged policy (EOL-norm exact substring first). Emits one JSON row
per evidence item with the live verdict, the live line number of the first
exact match, and drift of the live line vs the recorded anchor line.

This tool is the regeneration lane for the receipt's corpus cases; probe2
re-implements its checks independently rather than importing this module, so
the two lanes stay mechanically distinct.

Re-materialized 2026-10-26 (shard8-w3 builder) after the prior attempt died
mid-flight; rebuilt to the recorded behavior, not byte-identical to the
lost August file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DEFAULT_ORIGIN = "command-center/phase3/A7/SECURITY.json"


def norm_eol(raw: bytes) -> str:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8", errors="replace")


def harvest(origin_rel: str = DEFAULT_ORIGIN) -> list[dict]:
    origin = REPO / origin_rel
    doc = json.loads(origin.read_text(encoding="utf-8"))
    rows = []
    for i, ev in enumerate(doc.get("evidence") or [], 1):
        snippet = ev.get("snippet")
        path = ev.get("path")
        rec_line = ev.get("line")
        if not isinstance(snippet, str) or not isinstance(path, str):
            continue
        target = REPO / path
        if not target.is_file():
            rows.append({"origin": origin_rel, "origin_index": i, "path": path,
                         "recorded_line": rec_line, "class": "ABSENT-FILE",
                         "live_line": None, "note": "cited path missing from worktree"})
            continue
        src = norm_eol(target.read_bytes())
        q = snippet.replace("\r\n", "\n")
        cls = "exact" if q in src else "not-exact"
        live_line = None
        if cls == "exact":
            live_line = src[:src.find(q)].count("\n") + 1
        rows.append({"origin": origin_rel, "origin_index": i, "path": path,
                     "recorded_line": rec_line, "class": cls, "live_line": live_line,
                     "anchor_drift": (None if live_line is None or rec_line is None
                                      else live_line - rec_line),
                     "snippet_head": snippet[:60]})
    return rows


def main() -> int:
    origin = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ORIGIN
    rows = harvest(origin)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    exact = sum(1 for r in rows if r["class"] == "exact")
    print(json.dumps({"origin": origin, "rows": len(rows), "exact": exact}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
