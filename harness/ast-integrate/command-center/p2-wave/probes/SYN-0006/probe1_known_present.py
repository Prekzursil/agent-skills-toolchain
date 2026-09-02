#!/usr/bin/env python3
"""Probe 1: known-present 17-DECISION-LOG.md:175 plus both-states detector."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detect as D  # noqa: E402

ART = REPO / D.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0006-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != D.UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if D.SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    errs = D.validate_schema(doc, D.load_schema())
    if errs:
        print("\n".join(errs[:12]))
        return fail("schema")
    sem = D.semantic_errors(doc)
    if sem:
        print("\n".join(sem[:12]))
        return fail("semantic")

    kpc = doc.get("known_present_control") or {}
    if kpc.get("found") is not True:
        return fail("known-present found!=True")
    if kpc.get("verdict") != "SUPERSEDED-UNRECORDED":
        return fail(f"known-present verdict {kpc.get('verdict')}")
    if "2026-08-07" not in str(kpc.get("fix_cited") or ""):
        return fail("known-present did not cite 2026-08-07")

    hit = None
    for row in doc.get("entries") or []:
        anchor = str(row.get("decision_anchor") or "").replace("\\", "/")
        if ":175" in anchor and "17-DECISION-LOG.md" in anchor:
            hit = row
            break
    if hit is None:
        return fail("no entry anchored at 17-DECISION-LOG.md:175")
    if hit.get("verdict") != "SUPERSEDED-UNRECORDED":
        return fail(f"line-175 verdict {hit.get('verdict')}")
    if "2026-08-07" not in str(hit.get("superseding_fix") or ""):
        return fail("line-175 superseding_fix missing 2026-08-07")

    for row in doc.get("entries") or []:
        if row.get("verdict") == "REOPEN-REQUIRED" and len(str(row.get("owner_question") or "")) < 20:
            return fail(f"{row.get('id')} REOPEN-REQUIRED without owner_question")

    scratch = Path(tempfile.mkdtemp(prefix="syn0006-p1-"))
    good_events = [
        {
            "id": "evt-log-175",
            "ts": "2026-07-15T12:00:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:175",
        },
        {
            "id": "evt-reprefix",
            "ts": D.REPREFIX_TS,
            "kind": "fix",
            "anchor": "13-ARCHITECTURE-CANDIDATES.md:3",
        },
    ]
    lit = D.scan(D.write_scratch_sources(scratch / "lit", collision=True, events=good_events))
    dark = D.scan(D.write_scratch_sources(scratch / "dark", collision=False, events=good_events))
    if lit["known_present_control"]["found"] is not True:
        return fail("detector silent on lit collision line")
    if dark["known_present_control"]["found"] is not False:
        return fail("detector fired when collision line was removed (hardcoded?)")

    print(
        json.dumps(
            {
                "probe": "probe1-known-present",
                "unit_id": D.UNIT,
                "found": True,
                "verdict": "SUPERSEDED-UNRECORDED",
                "fix_cited_2026_08_07": True,
                "lit_found": True,
                "dark_found": False,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("known_present=True verdict=SUPERSEDED-UNRECORDED fix=2026-08-07")
    print("lit_found=True dark_found=False hardcoded=False")
    print("SUCCESS:SYN-0006-probe1 known-present both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
