#!/usr/bin/env python3
"""Probe 1: known-existing ranks above BUILD; empty ranked set when nothing exists."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import workflow_scout as S  # noqa: E402

INCUMBENT = "wf-saved-agentic-repair-reliability"
BUILD = "build-proposed-agentic-repair-reliability"
UNKNOWN = "wf-public-unresolved-repair-oracle"
ART = (
    REPO
    / "command-center/foundry/"
    / "WFA-0143-workflow-scout-executable-search-rank-and-provenance.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0143-probe1 {msg}")
    return 1


def main() -> int:
    known = S.run_named_goal("known_existing")
    missing = S.run_named_goal("no_existing")
    ranked = known.get("ranked") or []
    ids = [str(h.get("id")) for h in ranked]
    unknown_ids = [str(h.get("id")) for h in (known.get("unknown_needs_probe") or [])]
    census = known.get("source_census") or {}

    print(f"SOURCES searched={known.get('sources_searched')}")
    print(f"CENSUS {json.dumps(census, sort_keys=True)}")
    print(f"KNOWN ranked_ids={ids}")
    print(f"KNOWN unknown_ids={unknown_ids}")
    print(
        "EMPTY ranked_n="
        f"{len(missing.get('ranked') or [])} "
        f"unknown_n={len(missing.get('unknown_needs_probe') or [])}"
    )

    if list(known.get("sources_searched") or []) != list(S.SOURCE_CLASSES):
        return fail("did not search all four source classes")
    for cls in S.SOURCE_CLASSES:
        if int(census.get(cls) or 0) < 1:
            return fail(f"source class {cls} has empty census")
    if INCUMBENT not in ids:
        return fail("incumbent missing from ranked set")
    if ids[0] != INCUMBENT:
        return fail(f"incumbent is not rank-1, ranked={ids}")
    if BUILD not in ids:
        return fail("BUILD proposal missing from ranked set (vacuous anti-rebuild)")
    if ids.index(INCUMBENT) >= ids.index(BUILD):
        return fail("incumbent did not outrank BUILD proposal")
    if UNKNOWN in ids:
        return fail("unresolved-provenance hit was ranked")
    if UNKNOWN not in unknown_ids:
        return fail("unresolved-provenance hit not in UNKNOWN-NEEDS-PROBE")
    if missing.get("ranked"):
        return fail(
            "no-existing goal returned a non-empty ranked set: "
            + str([h.get("id") for h in missing["ranked"]])
        )

    if not ART.is_file():
        return fail(f"artifact missing {ART}")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0143" not in text:
        return fail("artifact sentinel SUCCESS:WFA-0143 absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"artifact self-declared {doc.get('state')}")
    demo = doc.get("demonstration_runs") or []
    known_demo = next((r for r in demo if r.get("label") == "known-existing"), None)
    if not isinstance(known_demo, dict):
        return fail("artifact missing known-existing demonstration run")
    art_ids = [str(h.get("id")) for h in (known_demo.get("ranked") or [])]
    if art_ids[:1] != [INCUMBENT]:
        return fail(f"artifact ranked head {art_ids[:1]} != {[INCUMBENT]}")

    print(
        "NEGATIVE CONTROL verbatim: known-existing goal returns "
        f"{INCUMBENT} at rank 1 above {BUILD}; unresolved {UNKNOWN} is "
        "UNKNOWN-NEEDS-PROBE not ranked; no-existing goal ranked_n=0 "
        "(no fabricated hit)."
    )
    print(
        f"EVIDENCE engine={S.file_line(HERE / 'workflow_scout.py', 'rank-existing-above-build')} "
        f"incumbent={ranked[0].get('evidence_anchor')}"
    )
    print("SUCCESS:WFA-0143-probe1 known-existing-above-build and empty-ranked-set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
