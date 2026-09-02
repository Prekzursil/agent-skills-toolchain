#!/usr/bin/env python3
"""Probe 2: both-states for UNVERIFIED vs VERIFIED, and undated claims."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402
import sweep as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0021-sweep-vendor-documentation.json"

DOCS = {
    "kind": "docs",
    "url": "https://code.claude.com/docs/en/example",
    "retrieved_at": "2026-08-24T18:00:00Z",
}
CHANGELOG = {
    "kind": "changelog",
    "url": "https://code.claude.com/docs/en/changelog",
    "retrieved_at": "2026-08-24T18:00:00Z",
}
UNDATED_DOCS = {
    "kind": "docs",
    "url": "https://code.claude.com/docs/en/example",
    "retrieved_at": "",
}


def main() -> int:
    one = L.grade_surfaces([DOCS])
    two = L.grade_surfaces([DOCS, CHANGELOG])
    undated = L.grade_surfaces([UNDATED_DOCS])
    two_docs = L.grade_surfaces(
        [DOCS, {**DOCS, "url": "https://code.claude.com/docs/en/other"}]
    )

    if one["status"] != "UNVERIFIED":
        print("FAILED:WFA-0021-probe2 single-surface not UNVERIFIED", one)
        return 1
    if not one.get("settling_probe"):
        print("FAILED:WFA-0021-probe2 UNVERIFIED missing settling_probe")
        return 1
    if two["status"] != "VERIFIED":
        print("FAILED:WFA-0021-probe2 dual-surface not VERIFIED", two)
        return 1
    if two.get("settling_probe") is not None:
        print("FAILED:WFA-0021-probe2 VERIFIED still has settling_probe")
        return 1
    if undated["status"] != "REJECTED-UNDATED":
        print("FAILED:WFA-0021-probe2 undated not rejected", undated)
        return 1
    if two_docs["status"] != "UNVERIFIED":
        print("FAILED:WFA-0021-probe2 two docs pages promoted", two_docs)
        return 1
    if not (one["status"] == "UNVERIFIED" and two["status"] == "VERIFIED"):
        print("FAILED:WFA-0021-probe2 both-states xor broken")
        return 1

    # Dropping the changelog surface from a live VERIFIED spec must flip.
    caps = S.load_captures()
    specs = [dict(s) for s in S.MECHANISMS if s["id"] == "anthropic.claude-code.skills"]
    if not specs:
        print("FAILED:WFA-0021-probe2 skills spec missing")
        return 1
    intact = S.run_sweep(caps=caps, specs=specs)
    if intact["mechanisms"][0]["verification"] != "VERIFIED":
        print("FAILED:WFA-0021-probe2 skills control not VERIFIED")
        return 1
    mutant_spec = dict(specs[0])
    mutant_spec["surface_ids"] = ["cc-skills-docs"]
    mutant = S.run_sweep(caps=caps, specs=[mutant_spec])
    if mutant["mechanisms"][0]["verification"] != "UNVERIFIED":
        print("FAILED:WFA-0021-probe2 skills mutant still VERIFIED")
        return 1
    if mutant["mechanisms"][0]["promoted"]:
        print("FAILED:WFA-0021-probe2 mutant promoted")
        return 1

    undated_caps = {k: dict(v) for k, v in caps.items()}
    undated_caps["cc-skills-docs"]["retrieved_at"] = ""
    try:
        S.run_sweep(caps=undated_caps, specs=specs)
        print("FAILED:WFA-0021-probe2 undated quote capture did not fail")
        return 1
    except RuntimeError as exc:
        if "undated" not in str(exc):
            print("FAILED:WFA-0021-probe2 unexpected", exc)
            return 1

    if not ART.is_file():
        print("FAILED:WFA-0021-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0021" or doc.get("state") != "SUCCESS":
        print("FAILED:WFA-0021-probe2 artifact state")
        return 1
    if S.SENTINEL not in json.dumps(doc):
        print("FAILED:WFA-0021-probe2 sentinel absent")
        return 1
    mechs = doc.get("mechanisms") or []
    if len(mechs) < 6:
        print("FAILED:WFA-0021-probe2 too few mechanisms")
        return 1
    live_unverified = []
    for rec in mechs:
        if not L.timestamp_ok(rec.get("quote_retrieved_at")):
            print("FAILED:WFA-0021-probe2 undated finding", rec.get("id"))
            return 1
        for surf in rec.get("surfaces") or []:
            if not L.timestamp_ok(surf.get("retrieved_at")):
                print("FAILED:WFA-0021-probe2 undated surface", rec.get("id"))
                return 1
        if rec.get("verification") == "UNVERIFIED":
            live_unverified.append(rec["id"])
            if rec.get("promoted"):
                print("FAILED:WFA-0021-probe2 live UNVERIFIED promoted")
                return 1
            if not rec.get("settling_probe"):
                print("FAILED:WFA-0021-probe2 live UNVERIFIED no settling_probe")
                return 1
        if rec.get("verification") == "VERIFIED" and rec.get("promoted") is not True:
            print("FAILED:WFA-0021-probe2 VERIFIED not promoted flag")
            return 1
    if "google.antigravity.workflows" not in live_unverified:
        print("FAILED:WFA-0021-probe2 antigravity not UNVERIFIED", live_unverified)
        return 1
    if "anthropic.claude-code.skills" not in [
        r["id"] for r in mechs if r.get("verification") == "VERIFIED"
    ]:
        print("FAILED:WFA-0021-probe2 skills not VERIFIED on live artifact")
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-unverified-and-timestamps",
                "single_surface": one["status"],
                "dual_surface": two["status"],
                "two_docs": two_docs["status"],
                "undated": undated["status"],
                "skills_mutant": mutant["mechanisms"][0]["verification"],
                "live_unverified": live_unverified,
                "xor": True,
                "unit_id": "WFA-0021",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0021-probe2 UNVERIFIED both-states and timestamps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
