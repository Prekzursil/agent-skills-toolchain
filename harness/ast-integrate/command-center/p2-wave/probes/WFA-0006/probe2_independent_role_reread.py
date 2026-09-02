#!/usr/bin/env python3
"""Probe 2: independent token-window re-read of every citing sentence.

Imports classify_b only (must not import classify_a). Recomputes live and
planted roles and matches the artifact. Both-states: stripping the
capability clause from the plant must flip it to DISCOVERY-AWARE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify_b as B  # noqa: E402
import graph as G  # noqa: E402

if "classify_a" in sys.modules:
    print("FAILED:WFA-0006-probe2 imported classify_a")
    raise SystemExit(1)

ART = REPO / "command-center/wfa/WFA-0006-discovery-only-consumers.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0006-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if "SUCCESS:WFA-0006" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    rows = G.iter_citations(REPO)
    mention = [r for r in rows if r["kind"] == "planted-mention"]
    plant = [r for r in rows if r["kind"] == "planted-capability"]
    live = [r for r in rows if r["kind"] == "live"]
    if not mention or not plant:
        return fail("planted fixtures missing from graph")

    for row in mention:
        if B.classify_sentence(row["quoted_sentence"]) != B.ROLE_DISCOVERY:
            return fail(
                f"independent mention consumer {row['path']}:{row['line']}"
            )
    plant_fired = sum(
        1
        for r in plant
        if B.classify_sentence(r["quoted_sentence"]) == B.ROLE_CAPABILITY
    )
    if plant_fired < 1:
        return fail("independent re-read missed planted capability sentence")

    stripped = plant[0]["quoted_sentence"]
    stripped = stripped.replace("is shipped capability", "self-declares discovery_only")
    stripped = stripped.replace("have been executed in production and merged", "are discovery records")
    if B.classify_sentence(stripped) != B.ROLE_DISCOVERY:
        return fail("stripping capability clause did not flip plant to DISCOVERY-AWARE")
    if B.classify_sentence(plant[0]["quoted_sentence"]) != B.ROLE_CAPABILITY:
        return fail("restored plant not CAPABILITY-ASSERTING")

    live_b = sum(
        1
        for r in live
        if B.classify_sentence(r["quoted_sentence"]) == B.ROLE_CAPABILITY
    )
    art_b = int((doc.get("independent_reread") or {}).get("live_capability_asserting") or 0)
    if live_b != art_b:
        return fail(f"live capability B {live_b} != artifact {art_b}")
    art_live = int(doc.get("live_citation_count") or -1)
    if art_live != len(live):
        return fail(f"live citation count {len(live)} != artifact {art_live}")
    if not (doc.get("controls") or {}).get("plant_detected"):
        return fail("artifact plant_detected false")

    print(
        f"mention_silent=True plant_fired={plant_fired} live_b={live_b} "
        f"live_rows={len(live)} strip_flips=True"
    )
    print(
        "SUCCESS:WFA-0006-probe2 independent token-window re-read; "
        "plant fires; mention silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
