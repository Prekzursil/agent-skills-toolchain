#!/usr/bin/env python3
"""Probe 2: independent reviewer of two BURIED findings in context.

Does not trust the receipt's verdict field. Re-opens each cited file, re-runs
the classifier, and checks that a reader following the cited claim line does
not meet the caveat (trailing section or non-adjacent). Also requires the
receipt to report a 10-bucket distribution, not a mean alone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

UNIT = "BLD-0030"
RECEIPT = "command-center/receipts/BLD-0030.json"


def reader_meets_caveat(doc: A.DocResult, tag: A.TagHit) -> bool:
    """Would a reader who stops at the claim line have met this caveat?"""
    if tag.verdict == "INLINE":
        return True
    if tag.reason.startswith("trailing-caveat-section"):
        return False
    if tag.line <= tag.claim_line:
        # same line handled by INLINE; anything else is a classifier bug
        return tag.verdict == "INLINE"
    return False


def main() -> int:
    rec_path = A.REPO / RECEIPT
    if not rec_path.is_file():
        print("FAILED:" + UNIT + "-probe2 receipt missing " + RECEIPT)
        return 1
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    report = rec.get("report") if isinstance(rec.get("report"), dict) else {}
    dist = rec.get("position_distribution") or report.get("position_distribution") or {}
    deciles = dist.get("deciles")
    if not (isinstance(deciles, list) and len(deciles) == 10):
        print("FAILED:" + UNIT + "-probe2 distribution is not 10 deciles")
        return 1
    if dist.get("not_just_a_mean") is not True:
        print("FAILED:" + UNIT + "-probe2 mean-only distribution")
        return 1
    classes = rec.get("document_classes") or report.get("document_classes") or {}
    if "NO-TAGS" not in classes or "ALL-INLINE" not in classes:
        print("FAILED:" + UNIT + "-probe2 document classes missing NO-TAGS/ALL-INLINE")
        return 1
    findings = [
        f
        for f in (rec.get("buried_findings") or report.get("buried_findings") or [])
        if isinstance(f, dict)
    ]
    if len(findings) < 2:
        print("FAILED:" + UNIT + "-probe2 need two BURIED findings, got " + str(len(findings)))
        return 1

    confirmed = []
    for finding in findings[:2]:
        rel = str(finding.get("path") or "")
        src = A.REPO / rel
        if not src.is_file():
            print("FAILED:" + UNIT + "-probe2 missing cited file " + rel)
            return 1
        live = A.classify_path(src)
        buried = [t for t in live.tags if t.verdict == "BURIED"]
        if not buried:
            print("FAILED:" + UNIT + "-probe2 reclassify found no BURIED in " + rel)
            return 1
        tag = buried[0]
        for t in buried:
            if t.line == int(finding.get("tag_line") or 0):
                tag = t
                break
        text = src.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        tag_line = int(finding["tag_line"])
        claim_line = int(finding["claim_line"])
        if tag_line < 1 or tag_line > len(lines):
            print("FAILED:" + UNIT + "-probe2 tag_line out of range " + rel)
            return 1
        if claim_line < 1 or claim_line > len(lines):
            print("FAILED:" + UNIT + "-probe2 claim_line out of range " + rel)
            return 1
        live_line = lines[tag_line - 1]
        if finding["tag"] not in live_line and finding["tag"] not in tag.snippet:
            print("FAILED:" + UNIT + "-probe2 cited tag not on tag_line " + rel)
            return 1
        if reader_meets_caveat(live, tag):
            print("FAILED:" + UNIT + "-probe2 reader would meet caveat " + rel)
            return 1
        if tag.reason.startswith("trailing-caveat-section") is False and tag.verdict != "BURIED":
            print("FAILED:" + UNIT + "-probe2 not buried after reclassify " + rel)
            return 1
        confirmed.append(
            {
                "path": rel,
                "tag": tag.tag,
                "tag_line": tag.line,
                "claim_line": tag.claim_line,
                "reason": tag.reason,
                "reader_would_meet_caveat": False,
                "reclassified": tag.verdict,
            }
        )

    print(
        json.dumps(
            {
                "unit_id": UNIT,
                "confirmed": confirmed,
                "deciles": deciles,
                "final_15_percent": dist.get("final_15_percent"),
                "n_tags": dist.get("n_tags"),
            },
            indent=2,
        )
    )
    print(
        "confirmed="
        + str(len(confirmed))
        + " reader_meets=False deciles="
        + str(len(deciles))
    )
    print("SUCCESS:" + UNIT + "-probe2 two BURIED findings reader would not meet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
