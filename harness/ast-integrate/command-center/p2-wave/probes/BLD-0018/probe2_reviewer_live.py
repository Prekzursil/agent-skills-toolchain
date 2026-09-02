#!/usr/bin/env python3
"""Probe 2: independent reviewer of three APPROVED-DROP verdicts + live honesty.

Re-reads OWNER-DECISIONS.md (does not trust engine.verdict alone) and confirms
each cited decision actually authorises that drop. Also checks the live tree
does not invent Prompt One drops when earlier scope files are absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "BLD-0018.json"


def receipt_findings(doc: dict) -> list:
    findings = doc.get("findings")
    if isinstance(findings, list) and findings:
        return findings
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    findings = report.get("findings")
    return findings if isinstance(findings, list) else []


def receipt_sampled(doc: dict) -> list:
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    sampled = rev.get("sampled")
    if isinstance(sampled, list) and sampled:
        return sampled
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    sampled = report.get("reviewer_sampled")
    return sampled if isinstance(sampled, list) else []


def main() -> int:
    scratch = E.load_scratch(REPO, HERE)
    review = E.review_approved_drops(scratch, REPO, HERE)
    live = E.load_live(REPO)
    print(json.dumps({"review": review, "live_observation": live.get("observation")}, indent=2))
    for row in review.get("sampled") or []:
        print(
            "sample finding={0} decision={1} authorises={2} path={3}".format(
                row.get("finding_id"),
                row.get("decision_id"),
                row.get("authorises_drop"),
                row.get("decision_path"),
            )
        )
    if int(review.get("sampled_count") or 0) < 3:
        print("FAILED:BLD-0018-probe2 need three APPROVED-DROP samples")
        return 1
    if not review.get("ok"):
        print("FAILED:BLD-0018-probe2 a cited decision does not authorise that drop")
        return 1
    if live.get("observation") == "earlier-scope-files-absent":
        if live.get("drops"):
            print("FAILED:BLD-0018-probe2 invented live drops without earlier citations")
            return 1
    if RECEIPT.is_file():
        try:
            doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"FAILED:BLD-0018-probe2 receipt unparseable:{type(exc).__name__}")
            return 1
        if "SUCCESS:BLD-0018" not in RECEIPT.read_text(encoding="utf-8"):
            print("FAILED:BLD-0018-probe2 sentinel-absent")
            return 1
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:BLD-0018-probe2 self-declared:{st}")
            return 1
        findings = receipt_findings(doc)
        live_findings = [
            f
            for f in findings
            if isinstance(f, dict) and str(f.get("source") or "") == "live"
        ]
        if live.get("observation") == "earlier-scope-files-absent" and live_findings:
            print("FAILED:BLD-0018-probe2 receipt live findings without earlier files")
            return 1
        sampled = receipt_sampled(doc)
        if len(sampled) < 3:
            print("FAILED:BLD-0018-probe2 receipt reviewer sampled < 3")
            return 1
        print(
            "receipt_ok=True findings={0} sampled={1}".format(len(findings), len(sampled))
        )
    print(
        "reviewer_ok={0} sampled={1} live={2} git={3}".format(
            review.get("ok"),
            review.get("sampled_count"),
            live.get("observation"),
            live.get("git_available"),
        )
    )
    print("SUCCESS:BLD-0018-probe2 independent APPROVED-DROP review and live honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
