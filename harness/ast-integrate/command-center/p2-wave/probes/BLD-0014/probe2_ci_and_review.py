#!/usr/bin/env python3
"""Probe 2: CI-workflow contradiction is caught; independent re-read of raw sources.

The author's summary in the receipt is not the input. Hand-written reviewer
predicates re-read the three highest-severity contradiction files from disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detect as D  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0014.json"
CI = HERE / "fixtures" / "plant-canary-ci.yml"
RAW_THREE = (
    HERE / "fixtures" / "plant-canary-ci.yml",
    HERE / "fixtures" / "plant-canary.md",
    HERE / "fixtures" / "plant-remote.sh",
)
MENTIONS = (
    HERE / "fixtures" / "mention-quote.md",
    HERE / "fixtures" / "mention-rejected.md",
    HERE / "fixtures" / "mention-no-remote.md",
)


def main() -> int:
    if not CI.is_file():
        print("FAILED:BLD-0014-probe2 CI fixture missing")
        return 1
    ci_hits = D.scan_path(CI, REPO, ["DEC-PR-ONLY"])
    ci_contra = [h for h in ci_hits if h["classification"] == "CONTRADICTS"]
    print(f"ci_detector_hits={ci_hits}")
    if not ci_contra:
        print("FAILED:BLD-0014-probe2 CI npm-publish plant not caught")
        return 1
    if ci_contra[0]["kind"] != "ci-workflow":
        print(f"FAILED:BLD-0014-probe2 CI kind={ci_contra[0]['kind']} want=ci-workflow")
        return 1
    if "npm publish" not in ci_contra[0]["snippet"].lower():
        print("FAILED:BLD-0014-probe2 CI snippet is not executable publish")
        return 1

    if not ART.is_file():
        print("FAILED:BLD-0014-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0014":
        print("FAILED:BLD-0014-probe2 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0014-probe2 self-declared", doc.get("state"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:BLD-0014" not in blob:
        print("FAILED:BLD-0014-probe2 sentinel absent")
        return 1

    findings = doc.get("live_findings") or []
    if len(findings) < 4:
        print(f"FAILED:BLD-0014-probe2 live_findings={len(findings)}")
        return 1
    for row in findings:
        cls = row.get("classification")
        anc = row.get("decision_anchor") or {}
        if not anc.get("path") or int(anc.get("line") or 0) < 1:
            print("FAILED:BLD-0014-probe2 decision anchor missing", row.get("decision_id"))
            return 1
        if cls == "CONTRADICTS":
            cons = row.get("contradictions") or []
            if not cons:
                print("FAILED:BLD-0014-probe2 CONTRADICTS without opposite anchor")
                return 1
            for c in cons:
                if not c.get("path") or int(c.get("line") or 0) < 1 or not c.get("snippet"):
                    print("FAILED:BLD-0014-probe2 incomplete opposite citation")
                    return 1
        elif cls == "CONFIRMED-CONSISTENT":
            if not row.get("search_surface_named"):
                print("FAILED:BLD-0014-probe2 CONFIRMED-CONSISTENT unnamed surface")
                return 1
            if row.get("contradictions"):
                print("FAILED:BLD-0014-probe2 consistent row still lists contradictions")
                return 1
        else:
            print("FAILED:BLD-0014-probe2 bad classification", cls)
            return 1

    tests = doc.get("tests") or {}
    for key in ("plant_canary_caught", "use_vs_mention_silent", "ci_workflow_caught"):
        if not (tests.get(key) or {}).get("pass"):
            print(f"FAILED:BLD-0014-probe2 test {key} not pass")
            return 1

    # Independent re-read: raw fixture bytes, not the receipt narrative.
    raw_hits = R.review_files(list(RAW_THREE))
    print(f"reviewer_raw_hits={len(raw_hits)}")
    by_file: dict[str, list[dict]] = {}
    for h in raw_hits:
        by_file.setdefault(Path(h["path"]).name, []).append(h)
    for required in ("plant-canary-ci.yml", "plant-canary.md", "plant-remote.sh"):
        if required not in by_file:
            print(f"FAILED:BLD-0014-probe2 reviewer missed {required}")
            return 1
    mention_hits = R.review_files(list(MENTIONS))
    print(f"reviewer_mention_hits={mention_hits}")
    if mention_hits:
        print("FAILED:BLD-0014-probe2 reviewer flagged use-vs-mention")
        return 1

    print("SUCCESS:BLD-0014-probe2 CI caught; independent raw-source review PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
