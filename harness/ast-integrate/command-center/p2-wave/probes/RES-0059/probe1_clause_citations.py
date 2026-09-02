#!/usr/bin/env python3
"""Probe 1: every kept clause has a live citation in captured bytes (two rails)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from engine import check_artifact, load_search_text, rails_ok  # noqa: E402

OUT = REPO / "command-center/research/RES-0059.json"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:RES-0059-probe1 artifact missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    fails = check_artifact(doc)
    kept = doc.get("minimal_clause_set") or []
    cited = 0
    two_rail = 0
    for cl in kept:
        cites = cl.get("citations") or []
        cited += len(cites)
        if rails_ok(cites):
            two_rail += 1
        for c in cites:
            text = load_search_text(c.get("source_id") or "")
            needle = c.get("needle") or ""
            hit = bool(needle) and needle in text
            print(
                f"clause={cl.get('id')} source={c.get('source_id')} "
                f"rail={c.get('rail')} needle_hit={hit}"
            )
            if not hit:
                fails.append(f"live-miss-{cl.get('id')}-{c.get('source_id')}")
    print(
        f"kept={len(kept)} two_rail_clauses={two_rail} citations={cited} fails={fails}"
    )
    if fails or len(kept) < 4 or two_rail < 4:
        print("FAILED:RES-0059-probe1 per-clause citations")
        return 1
    print("SUCCESS:RES-0059-probe1 per-clause citations in captured bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
