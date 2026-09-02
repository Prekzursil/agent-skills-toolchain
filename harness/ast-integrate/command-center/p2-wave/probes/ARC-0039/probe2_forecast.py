#!/usr/bin/env python3
"""Probe 2: forecast check + mechanically different remeasure.

Requires a falsifiable model_naming forecast with a confidence band.
Re-counts OpenAI dated entries via the day-header field (not the entry splitter)
and compares to COST.json. GitHub published_at vs created_at must not be silently
picked when they disagree.
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


def main() -> int:
    doc = json.loads(COST.read_text(encoding="utf-8"))
    fc = doc.get("forecast") or {}
    surface = fc.get("surface")
    statement = fc.get("falsifiable_statement") or ""
    band = fc.get("confidence_band") or {}
    print(f"forecast_surface={surface}")
    print(f"forecast_window={fc.get('window_start')}..{fc.get('window_end')}")
    print(f"confidence_point={fc.get('confidence_point')} band={band}")
    print(f"statement_len={len(statement)}")
    ok = True
    if surface != "model_naming":
        print("FAILED:ARC-0039-probe2 forecast surface is not model_naming")
        ok = False
    if len(statement) < 40 or "FALSE" not in statement:
        print("FAILED:ARC-0039-probe2 forecast is not falsifiable")
        ok = False
    try:
        lo = float(band.get("low"))
        hi = float(band.get("high"))
        if not (0 < lo < hi < 1):
            raise ValueError("band")
    except (TypeError, ValueError):
        print("FAILED:ARC-0039-probe2 confidence band missing")
        ok = False
        lo, hi = 0.0, 0.0
    oa_a, oa_b = L.two_openai_entry_counts()
    stated = None
    for h in doc.get("headline_numbers") or []:
        if h.get("name") == "openai_api_dated_entries_in_window":
            stated = h.get("value")
    print(f"openai_remeasure A={oa_a} B={oa_b} stated={stated}")
    if oa_a != oa_b or stated != oa_a:
        print("FAILED:ARC-0039-probe2 openai headline mismatch or probe disagreement")
        ok = False
    gh = (doc.get("remeasure") or {}).get("claude_code_github_releases") or {}
    print(
        f"github_claude_code published={gh.get('value_a')} created={gh.get('value_b')} "
        f"agree={gh.get('agree')}"
    )
    if gh.get("value_a") != gh.get("value_b") and gh.get("agree") is True:
        print("FAILED:ARC-0039-probe2 GitHub disagreement was picked")
        ok = False
    if gh.get("value_a") != gh.get("value_b"):
        headlines = [h.get("name") for h in doc.get("headline_numbers") or []]
        if any("github" in str(n).lower() or "claude_code" in str(n).lower() for n in headlines):
            print("FAILED:ARC-0039-probe2 disagreed GitHub count used as headline")
            ok = False
    must = doc.get("versioned_surfaces") or []
    print(f"must_version={must}")
    if set(must) != set(L.SURFACES):
        print("FAILED:ARC-0039-probe2 versioned_surfaces != seven catalog surfaces")
        ok = False
    if not ok:
        print("FAILED:ARC-0039-probe2 forecast/remeasure")
        return 1
    print("SUCCESS:ARC-0039-probe2 forecast and remeasure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
