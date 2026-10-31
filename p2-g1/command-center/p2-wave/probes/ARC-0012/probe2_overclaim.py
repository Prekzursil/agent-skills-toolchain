#!/usr/bin/env python3
"""Probe 2: claims discipline + reviewer-added failure mode, verified live.

Every REFUTED claim names a defect locus (DESIGN vs SENTENCE) with a scoped
restatement; stripping one must turn the checker red (both-states). Anchors
resolve. The reviewer-added stale-bytes mode is present in the artifact and
demonstrated live: a non-empty generated file at the exact mapped path is
invisible to BOTH completeness directions once the registry row has drifted.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anchors as A  # noqa: E402
import live as L  # noqa: E402
from common import REPO, UNIT_ID, fail  # SENTINEL checked by probe1

ART = REPO / "command-center/phase3/A2/FAILURE-MODES.json"

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED"})


def check_claims(doc: dict) -> tuple[bool, str]:
    claims = doc.get("claims") or []
    if len(claims) < 3:
        return False, "claims-missing-or-short"
    refuted = confirmed = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        if not str(row.get("claim") or "").strip():
            return False, f"claims[{i}]-empty-claim"
        if verdict == "REFUTED":
            refuted += 1
            if str(row.get("defect_locus") or "") not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("scoped_restatement") or "").strip():
                return False, f"claims[{i}]-REFUTED-missing-scoped_restatement"
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1 or confirmed < 1:
        return False, "claims-lacking-both-verdict-poles"
    return True, f"refuted={refuted} confirmed={confirmed}"


def main() -> int:
    if not ART.is_file():
        return fail("FAILURE-MODES.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = check_claims(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        return fail(f"claims discipline failed: {why}")

    # Both-states mutation: stripping a defect_locus must turn the checker red.
    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        return fail("no REFUTED defect_locus to strip")
    mok, _ = check_claims(mutant)
    if mok:
        return fail("mutant without defect_locus was accepted")
    print("mutant_red=true stripping defect_locus turns the checker red")

    resolved = 0
    for i, row in enumerate(doc.get("evidence") or []):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            return fail(f"anchor[{i}] unresolved: {rwhy}")
        resolved += 1
    if resolved < 2:
        return fail(f"resolved anchors {resolved} < 2")

    rev = doc.get("reviewer") or {}
    added = rev.get("added_failure_mode") or {}
    if not added:
        return fail("reviewer-added failure mode absent")
    if not added.get("author_missed"):
        return fail("reviewer-added mode not marked author_missed")

    # Live demonstration of the reviewer-added stale-bytes gap.
    scratch = Path(tempfile.mkdtemp(prefix=f"{UNIT_ID.lower()}-p2-"))
    demo = L.stale_bytes_demo(scratch)
    demo["reviewer_added_id"] = added.get("id")
    print(json.dumps({"probe": "probe2-stale-bytes-demo", "unit_id": UNIT_ID, **demo}, sort_keys=True))
    if demo.get("gap_real") is not True:
        return fail("stale-bytes gap not demonstrated live")
    afm = doc.get("author_failure_modes")
    if not isinstance(afm, list) or not afm:
        return fail("author_failure_modes empty")
    print(
        f"SUCCESS:{UNIT_ID}-probe2 claims discipline + reviewer-added "
        "stale-bytes mode; gap demonstrated live"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
