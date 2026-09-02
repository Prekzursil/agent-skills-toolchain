#!/usr/bin/env python3
"""Probe 2: COVERED classification + independent 10% speaker re-read."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0038.json"


def main() -> int:
    gold = E.load_gold()
    rows, _meta = E.build_rows()
    cv = E.coverage_control(rows, gold)
    print(json.dumps(cv, sort_keys=True))
    if not cv["pass"]:
        print("FAILED:BLD-0038-probe2 coverage control")
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0038-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_rows = [r for r in (doc.get("rows") or []) if isinstance(r, dict)]
    pr = [r for r in art_rows if "pr-only" in (r.get("owner_quote") or "").lower()]
    if not pr or any(r.get("coverage") != "COVERED" for r in pr):
        print("FAILED:BLD-0038-probe2 PR-ONLY not COVERED on receipt")
        return 1
    planted = [r for r in art_rows if "hedge word" in (r.get("owner_quote") or "").lower()]
    if not planted or any(r.get("coverage") != "GAP" for r in planted):
        print("FAILED:BLD-0038-probe2 planted aside not GAP")
        return 1

    corpus = E.FIXTURE_CORPUS.read_text(encoding="utf-8")
    n = max(2, max(1, len(art_rows) // 10))
    sample = art_rows[:1] + art_rows[-1:]
    step = max(1, len(art_rows) // n) if art_rows else 1
    for i, r in enumerate(art_rows):
        if i % step == 0 and r not in sample:
            sample.append(r)
        if len(sample) >= n:
            break
    rejected = []
    for r in sample:
        quote = r.get("owner_quote") or ""
        found = False
        for turn in E.parse_turns(corpus):
            if quote in turn["body"]:
                found = True
                if turn["speaker"] != "owner" or E.is_formal_prompt(turn):
                    rejected.append(r.get("id"))
                break
        if not found:
            rejected.append(r.get("id"))
        for item in gold["agent_must_not_attribute"]:
            if item["snippet"] in quote:
                rejected.append(r.get("id"))
    print(f"reviewer_sample={len(sample)} rejected={rejected}")
    if rejected:
        print("FAILED:BLD-0038-probe2 reviewer sample")
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        print("FAILED:BLD-0038-probe2 reviewer field")
        return 1
    if "SUCCESS:BLD-0038" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0038-probe2 sentinel")
        return 1
    print("SUCCESS:BLD-0038-probe2 covered-not-new reviewer-sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
