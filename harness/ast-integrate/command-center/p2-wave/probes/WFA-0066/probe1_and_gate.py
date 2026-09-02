#!/usr/bin/env python3
"""Probe 1: collapse requires BOTH signals; incidence overlap alone is not enough.

Negative control: incidence-only mutant merges the shared-source SBAR/PEER
pair. Production AND-gate must refuse that merge and still alias the synonym
pair. Ids are aliased, never deleted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import dedup as D  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0066-mechanism-level-dedup.json"
SYN_A = "MECH-CONFLICT-REFUSE"
SYN_B = "MECH-UNION-GUARD"
SHARE_A = "MECH-SBAR-HANDOFF"
SHARE_B = "MECH-PEER-REVIEW"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0066-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")
    if "SUCCESS:WFA-0066" not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    corp = C.load_corpus()
    live = D.evaluate(corp, incidence_only=False)
    mutant = D.evaluate(corp, incidence_only=True)

    orig_ids = {str(m["id"]) for m in corp["mechanisms"]}
    if set(live["mechanism_ids"]) != orig_ids:
        return fail(f"ids deleted live={live['mechanism_ids']}")
    if live["ids_deleted"]:
        return fail(f"ids_deleted={live['ids_deleted']}")

    if not D.same_canonical(live, SYN_A, SYN_B):
        return fail("synonym pair not collapsed under AND-gate")
    if D.same_canonical(live, SHARE_A, SHARE_B):
        return fail("shared-source SBAR/PEER collapsed under AND-gate")
    if not D.same_canonical(mutant, SHARE_A, SHARE_B):
        return fail("incidence-only mutant did not merge SBAR/PEER")
    if not D.same_canonical(mutant, SYN_A, SYN_B):
        return fail("incidence-only mutant lost the synonym collapse")

    syn_edge = [
        e
        for e in live["duplicate_of_edges"]
        if {e["alias"], e["canonical"]} == {SYN_A, SYN_B}
    ]
    if not syn_edge:
        return fail("synonym pair has no duplicate-of edge")

    art_collapses = doc.get("collapses") or []
    art_pairs = {(c.get("left"), c.get("right")) for c in art_collapses if c.get("collapse")}
    live_pairs = {(p["left"], p["right"]) for p in live["collapses"]}
    if art_pairs != live_pairs:
        return fail(f"artifact collapses != live {art_pairs} vs {live_pairs}")

    share_live = next(
        p
        for p in live["pair_verdicts"]
        if {p["left"], p["right"]} == {SHARE_A, SHARE_B}
    )
    if not share_live["suspect"]:
        return fail("SBAR/PEER was not an incidence suspect")
    if share_live["discrimination"]["indistinguishable"]:
        return fail("SBAR/PEER definitions were not distinguishable")
    if share_live["collapse"]:
        return fail("SBAR/PEER collapsed")

    payload = {
        "probe": "probe1-and-gate",
        "unit_id": "WFA-0066",
        "computed_not_asserted": True,
        "synonym_collapsed": True,
        "shared_source_refused": True,
        "incidence_only_mutant_merged_shared_source": True,
        "ids_deleted": live["ids_deleted"],
        "duplicate_of_edges": live["duplicate_of_edges"],
        "shared_source_jaccard": share_live["incidence_jaccard"],
        "shared_source_accuracy": share_live["discrimination"]["accuracy"],
        "negative_control": {
            "fired": True,
            "what_the_check_does": (
                "incidence-only mutant collapses SBAR/PEER; AND-gate refuses"
            ),
            "observed": (
                f"mutant_same_canonical={D.same_canonical(mutant, SHARE_A, SHARE_B)} "
                f"and_gate_same_canonical={D.same_canonical(live, SHARE_A, SHARE_B)}"
            ),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "synonym collapsed "
        f"{SYN_A}/{SYN_B} canonical={live['canonical_of'][SYN_A]}"
    )
    print(
        "shared-source refused "
        f"{SHARE_A}/{SHARE_B} jaccard={share_live['incidence_jaccard']} "
        f"acc={share_live['discrimination']['accuracy']}"
    )
    print(
        "NEGATIVE-CONTROL incidence-only mutant merged SBAR/PEER; "
        "AND-gate did not"
    )
    print("SUCCESS:WFA-0066-probe1 both-signals AND-gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
