#!/usr/bin/env python3
"""Live estate scan: which catalog protocols already have code on this tree.

A protocol is IMPLEMENTED only when a real module path exists. Catalog
intent (IMP-0333 oxford.py) is not implementation. Tournament pairing is
not a role committee.
"""
from __future__ import annotations

from pathlib import Path

# protocol_id -> candidate rows. First existing path wins as implementing_candidate_id.
ESTATE_CANDIDATES: dict[str, list[dict]] = {
    "debate": [
        {
            "candidate_id": "IMP-0333",
            "relpath": "tools/council/protocol/oxford.py",
            "kind": "production-module",
        },
        {
            "candidate_id": "IMP-0333",
            "relpath": "tools/council/protocol/debate.py",
            "kind": "production-module",
        },
    ],
    "delphi": [
        {
            "candidate_id": "IMP-0286",
            "relpath": "tools/council/topology/delphi.py",
            "kind": "production-module",
        },
        {
            "candidate_id": "CNL-0035",
            "relpath": "command-center/p2-wave/probes/CNL-0035/delphi.py",
            "kind": "probe-module",
        },
        {
            "candidate_id": "TST-0291",
            "relpath": "command-center/receipts/TST-0291.json",
            "kind": "receipt",
        },
    ],
    "verifier-in-the-loop": [
        {
            "candidate_id": "WFA-0105",
            "relpath": "tools/council/protocol/verifier.py",
            "kind": "production-module",
        },
    ],
    "execution-consensus": [
        {
            "candidate_id": "WFA-0105",
            "relpath": "command-center/wfa/WFA-0105-fusion-ensemble.json",
            "kind": "fusion-artifact",
        },
        {
            "candidate_id": "WFA-0105",
            "relpath": "tools/fusion/ensemble.py",
            "kind": "production-module",
        },
    ],
    "best-of-n": [
        {
            "candidate_id": "WFA-0105",
            "relpath": "tools/council/protocol/best_of_n.py",
            "kind": "production-module",
        },
    ],
    "self-consistency": [
        {
            "candidate_id": "WFA-0105",
            "relpath": "tools/council/protocol/self_consistency.py",
            "kind": "production-module",
        },
    ],
    "role-committees": [
        {
            "candidate_id": "IMP-0331",
            "relpath": "tools/council/topology/committee.py",
            "kind": "production-module",
        },
        {
            "candidate_id": "IMP-0331",
            "relpath": "tools/council/topology/caucus.py",
            "kind": "production-module",
        },
    ],
}

# Related but non-equivalent files: recorded so we do not silently promote them.
NON_EQUIVALENT = {
    "role-committees": [
        {
            "relpath": "tools/council/topology/tournament.py",
            "why": (
                "Pairwise Swiss/round-robin Copeland ranking, not SOP role "
                "committees (product-manager / architect / engineer)."
            ),
        }
    ],
    "debate": [
        {
            "relpath": "tools/council/protocol/negotiate.py",
            "why": (
                "Matched-pair negotiation with a voteless mediator, not "
                "multi-agent debate with shared-context rebuttal rounds."
            ),
        }
    ],
}


def scan_estate(repo: Path) -> dict:
    protocols: dict[str, dict] = {}
    for pid, cands in ESTATE_CANDIDATES.items():
        hits = []
        for c in cands:
            path = repo / c["relpath"]
            hits.append(
                {
                    "candidate_id": c["candidate_id"],
                    "relpath": c["relpath"],
                    "kind": c["kind"],
                    "exists": path.is_file() and path.stat().st_size > 0,
                    "bytes": path.stat().st_size if path.is_file() else 0,
                }
            )
        implemented = [h for h in hits if h["exists"]]
        related = []
        for extra in NON_EQUIVALENT.get(pid, []):
            p = repo / extra["relpath"]
            related.append(
                {
                    "relpath": extra["relpath"],
                    "why": extra["why"],
                    "exists": p.is_file(),
                    "treated_as_implementation": False,
                }
            )
        if implemented:
            status = "IMPLEMENTED"
            implementing_candidate_id = implemented[0]["candidate_id"]
            implementing_path = implemented[0]["relpath"]
        else:
            status = "NOT-IMPLEMENTED"
            implementing_candidate_id = None
            implementing_path = None
        planned = sorted({c["candidate_id"] for c in cands})
        protocols[pid] = {
            "protocol_id": pid,
            "estate_status": status,
            "implementing_candidate_id": implementing_candidate_id,
            "implementing_path": implementing_path,
            "planned_candidate_ids": planned,
            "path_hits": hits,
            "non_equivalent": related,
        }
    return {"protocols": protocols, "scan": "filesystem"}
