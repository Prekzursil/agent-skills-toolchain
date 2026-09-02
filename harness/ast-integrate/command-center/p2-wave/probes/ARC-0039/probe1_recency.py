#!/usr/bin/env python3
"""Probe 1: recency control — every COST.json citation has entry_date and retrieved_on.

Also re-derives the Anthropic heading headline via the strptime field and
asserts it matches COST.json. Mutant: dropping retrieved_on must fail recency_ok.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

COST = REPO / "command-center/phase3/A6/COST.json"


def citations(doc: dict) -> list[dict]:
    out: list[dict] = []
    for surface in doc.get("surfaces") or []:
        out.extend(surface.get("citations") or [])
    return out


def main() -> int:
    doc = json.loads(COST.read_text(encoding="utf-8"))
    cites = citations(doc)
    if len(cites) < 7:
        print(f"FAILED:ARC-0039-probe1 expected >=7 citations got {len(cites)}")
        return 1
    bad = 0
    for c in cites:
        ok, why = L.recency_ok(c)
        print(
            f"cite vendor={c.get('vendor')} entry_date={c.get('entry_date')} "
            f"retrieved_on={c.get('retrieved_on')} staleness_days={c.get('staleness_days')} "
            f"ok={ok} why={why}"
        )
        if not ok:
            bad += 1
    mutant = dict(cites[0])
    mutant.pop("retrieved_on", None)
    m_ok, m_why = L.recency_ok(mutant)
    print(f"mutant_missing_retrieved_on ok={m_ok} why={m_why}")
    a, b = L.two_anthropic_heading_counts()
    stated = None
    for h in doc.get("headline_numbers") or []:
        if h.get("name") == "anthropic_api_dated_headings_in_window":
            stated = h.get("value")
    print(f"heading_remeasure A={a} B={b} stated={stated}")
    if bad:
        print("FAILED:ARC-0039-probe1 recency control")
        return 1
    if m_ok:
        print("FAILED:ARC-0039-probe1 mutant with missing retrieved_on still passed")
        return 1
    if a != b or stated != a:
        print("FAILED:ARC-0039-probe1 heading headline mismatch")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0039-probe1 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:ARC-0039-probe1 recency control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
