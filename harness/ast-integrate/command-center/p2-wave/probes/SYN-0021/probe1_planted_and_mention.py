#!/usr/bin/env python3
"""Probe 1: planted missing-artifact claim is unbacked; requirements are not claims."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import extract as X  # noqa: E402
import shared_judge as SJ  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0021.completion-census.json"
PLANTED = HERE / "fixtures/planted_success_missing.json"
MENTION = HERE / "fixtures/requirement_mention.md"
CLAIM = HERE / "fixtures/asserted_claim.md"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0021-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:SYN-0021" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    body = X.census_body(doc)
    claims = body.get("claims") or []
    split = body.get("split") or {}
    if int(split.get("denominator") or 0) < 1:
        return fail("split has no denominator")
    if int(split.get("total") or -1) != int(split.get("backed") or 0) + int(split.get("unbacked") or 0):
        return fail("split total != backed+unbacked")
    if int(split.get("denominator") or 0) != int(split.get("total") or -1):
        return fail("denominator != total")
    for c in claims:
        if not isinstance((c.get("predicate") or {}).get("verdict"), str):
            return fail(f"claim {c.get('id')} missing predicate verdict")

    planted_rows = [c for c in claims if c.get("subject") == "SYN-0021-PLANTED"]
    if not planted_rows:
        return fail("planted claim missing from census")
    for p in planted_rows:
        if p.get("backed") is True or p.get("downgrade") != "unbacked":
            return fail("planted SUCCESS+missing-artifact was not reported unbacked")
        if p.get("predicate", {}).get("failing_condition_id") != 2:
            return fail(
                f"planted failing_condition_id={p.get('predicate', {}).get('failing_condition_id')} want=2"
            )

    receipt = json.loads(PLANTED.read_text(encoding="utf-8"))
    live = SJ.evaluate(receipt, REPO)
    if live.get("verdict") == "PASS" or live.get("failing_condition_id") != 2:
        return fail(f"live judge on planted: {live}")
    missing = REPO / "command-center/synthesis/_SYN-0021-planted-missing.json"
    if missing.is_file():
        return fail("planted artifact unexpectedly exists on disk")

    mention_text = MENTION.read_text(encoding="utf-8")
    for line in mention_text.splitlines():
        if X.classify_line(line) == "CLAIM":
            return fail(f"requirement line classified as CLAIM: {line!r}")
    claim_lines = [ln for ln in CLAIM.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    if not any(X.classify_line(ln) == "CLAIM" for ln in claim_lines):
        return fail("asserted claim fixture not classified as CLAIM")

    fake = [c for c in claims if c.get("subject") == "FAKE-0001"]
    if not fake:
        return fail("FAKE-0001 asserted claim missing from census")
    if any(c.get("backed") for c in fake):
        return fail("FAKE-0001 must be unbacked (no artifact)")

    excluded = json.dumps(body.get("mentions_excluded") or doc.get("mentions_excluded") or [])
    if "emitted only when" not in excluded.lower() and "complete only when" not in excluded.lower():
        return fail("requirement mention was not recorded as excluded")
    for c in claims:
        path = str(c.get("path") or "")
        if path.endswith("requirement_mention.md"):
            return fail("requirement fixture leaked into claims")

    print(
        "planted_unbacked=true failing_condition_id=2 "
        f"fake_unbacked=true mentions_excluded={len(body.get('mentions_excluded') or [])} "
        f"split={split.get('backed')}/{split.get('denominator')}"
    )
    print("SUCCESS:SYN-0021-probe1 planted unbacked and use-versus-mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
