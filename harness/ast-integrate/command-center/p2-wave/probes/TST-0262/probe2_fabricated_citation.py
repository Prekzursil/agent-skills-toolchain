#!/usr/bin/env python3
"""Probe 2: fabricated-citation control + annotation-only contrast.

A ballot citing an evidence id that does not exist must be unbacked, not
backed. Independent of probe 1: starts from the gate's classify/decide API
and the fabricated fixture, not from the implementer summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote import evidence_gate as G  # noqa: E402

ART = REPO / "command-center/receipts/TST-0262.json"
OUT = HERE / "probe2-fabricated-citation.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0262-probe2 {msg}")
    return 1


def main() -> int:
    graph, ballots = G.fabricated_citation_fixture()
    rec = G.decide(graph, ballots, election_id="TST-0262-probe2-fabricated")

    fabricator = next(b for b in rec["ballots"] if b["voter_id"] == "fabricator")
    backed = next(b for b in rec["ballots"] if b["voter_id"] == "backed-minority")

    if fabricator["backed"] or fabricator["counts"]:
        return fail("fabricated citation treated as backed/counting")
    if fabricator["status"] != "unbacked-non-counting":
        return fail(f"fabricator status={fabricator['status']}")
    reasons = {r["reason"] for r in fabricator["resolutions"]}
    if reasons != {"unknown-id"}:
        return fail(f"expected unknown-id, got {reasons}")
    if G.FABRICATED_EVIDENCE_ID not in fabricator["evidence_ids"]:
        return fail("fixture did not cite the fabricated id")
    if graph.get(G.FABRICATED_EVIDENCE_ID) is not None:
        return fail("fabricated id present in graph")
    if not backed["backed"] or not backed["counts"]:
        return fail("real evidence ballot was not backed")
    if rec["outcome"] != G.MINORITY_CHOICE:
        return fail(f"fabricated ballot decided the race outcome={rec['outcome']}")

    # Annotation-only would count the fabricator and tie 1-1 (non-binding)
    # or, on the 7v2 fixture, would keep the majority. Probe the 7v2
    # contrast here so a gate that only annotates goes red.
    g7, b7 = G.majority_unbacked_fixture()
    rec7 = G.decide(g7, b7, election_id="TST-0262-probe2-annotation-contrast")
    if rec7["annotated_only_winner"]["outcome"] != G.MAJORITY_CHOICE:
        return fail("annotation-only contrast did not keep majority")
    if rec7["outcome"] != G.MINORITY_CHOICE:
        return fail("non-counting gate failed on 7v2 from probe2")
    if rec7["annotated_only_winner"]["outcome"] == rec7["outcome"]:
        return fail("gate is annotation-only: unbacked votes still counted")

    # Plausible-looking citation that does not resolve (node present, resolves=False).
    dangling = G.CouncilGraph()
    dangling.add(
        G.EvidenceNode(
            id="EV-DANGLING",
            kind="citation",
            body="looks like evidence",
            resolves=False,
        )
    )
    dangling.add(
        G.EvidenceNode(
            id=G.REAL_EVIDENCE_ID,
            kind="executable-counterexample",
            body="real",
            resolves=True,
        )
    )
    rec_d = G.decide(
        dangling,
        [
            G.Ballot("dangle", G.MAJORITY_CHOICE, ("EV-DANGLING",)),
            G.Ballot("real", G.MINORITY_CHOICE, (G.REAL_EVIDENCE_ID,)),
        ],
        election_id="TST-0262-probe2-dangling",
    )
    drow = rec_d["ballots"][0]
    if drow["backed"]:
        return fail("unresolved node treated as backed")
    if drow["resolutions"][0]["reason"] != "does-not-resolve":
        return fail(f"dangling reason={drow['resolutions'][0]['reason']}")

    payload = {
        "probe": "probe2-fabricated-citation",
        "unit_id": "TST-0262",
        "pass": True,
        "fabricated_id": G.FABRICATED_EVIDENCE_ID,
        "fabricator_backed": False,
        "fabricator_counts": False,
        "fabricator_status": fabricator["status"],
        "fabricator_reason": "unknown-id",
        "fabricated_outcome": rec["outcome"],
        "annotation_only_would_elect": rec7["annotated_only_winner"]["outcome"],
        "non_counting_elects": rec7["outcome"],
        "dangling_reason": "does-not-resolve",
        "dangling_backed": False,
        "negative_control_ids": [
            "NC-FABRICATED-CITATION-UNBACKED",
            "NC-ANNOTATION-ONLY-STILL-COUNTS",
            "NC-UNRESOLVED-NODE-UNBACKED",
        ],
    }

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        nids = receipt.get("negative_control_ids") or []
        for nid in payload["negative_control_ids"]:
            if nid not in nids:
                return fail(f"receipt missing {nid}")
        if str(receipt.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt self-declared {receipt.get('state')}")
        fab = receipt.get("fabricated_citation") or {}
        if fab.get("fabricator_backed") is not False:
            return fail("receipt fabricated_citation.fabricator_backed drift")
        payload["receipt_matches_live"] = True
    else:
        payload["receipt_matches_live"] = False

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "fabricator_backed=False counts=False reason=unknown-id "
        f"annotation_only={rec7['annotated_only_winner']['outcome']} "
        f"gated={rec7['outcome']}"
    )
    print("SUCCESS:TST-0262-probe2 fabricated citation is unbacked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
