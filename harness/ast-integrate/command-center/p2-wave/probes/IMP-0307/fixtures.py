"""Hermetic ballots and an evidence graph for IMP-0307.

Real anchors are files under fixtures/evidence/ that probes independently
os.stat. Fabricated citations are plausible ids / DOIs / sibling paths
that MUST NOT exist on disk.
"""

from __future__ import annotations

from pathlib import Path

from council.vote.evidence_gate import Ballot

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "fixtures" / "evidence"
REPO = HERE.parents[3]

# Registered ids whose paths exist.
GRAPH: dict[str, str] = {
    "ev-hold-1": str(EVIDENCE / "node-hold-1.json"),
    "ev-hold-2": str(EVIDENCE / "node-hold-2.json"),
    "ev-ship-backed": str(EVIDENCE / "node-ship.json"),
    # Planted lie: looks registered, path is absent. Must not resolve.
    "ev-7f3a9c2b-looks-registered": str(EVIDENCE / "node-ship-doi-10.1000-xyz.json"),
}

FABRICATED = (
    "ev-7f3a9c2b-looks-registered",
    "https://doi.org/10.1000/fabricated-council-cite",
    str(EVIDENCE / "node-hold-1-missing-sibling.json"),
    "file:///opt/p2/ast-integrate/command-center/p2-wave/probes/IMP-0307/fixtures/evidence/no-such-anchor.json",
)


def majority_unbacked_minority_backed() -> list[Ballot]:
    majority = [
        Ballot(voter_id=f"maj-{i:02d}", position="ship-it", citations=())
        for i in range(1, 8)
    ]
    minority = [
        Ballot(voter_id="min-01", position="hold", citations=("ev-hold-1",)),
        Ballot(voter_id="min-02", position="hold", citations=("ev-hold-2",)),
    ]
    return majority + minority


def all_ballots_backed() -> list[Ballot]:
    majority = [
        Ballot(
            voter_id=f"maj-{i:02d}",
            position="ship-it",
            citations=("ev-ship-backed",),
        )
        for i in range(1, 8)
    ]
    minority = [
        Ballot(voter_id="min-01", position="hold", citations=("ev-hold-1",)),
        Ballot(voter_id="min-02", position="hold", citations=("ev-hold-2",)),
    ]
    return majority + minority


def fabricated_majority_real_minority() -> list[Ballot]:
    majority: list[Ballot] = []
    for i, cite in enumerate(FABRICATED, start=1):
        majority.append(
            Ballot(
                voter_id=f"fab-{i:02d}",
                position="ship-it",
                citations=(cite,),
            )
        )
    # Pad to 7 so this is still a numerical majority.
    while len(majority) < 7:
        n = len(majority) + 1
        majority.append(
            Ballot(
                voter_id=f"fab-{n:02d}",
                position="ship-it",
                citations=(FABRICATED[0],),
            )
        )
    minority = [
        Ballot(voter_id="min-01", position="hold", citations=("ev-hold-1",)),
        Ballot(voter_id="min-02", position="hold", citations=("ev-hold-2",)),
    ]
    return majority + minority


def fabricated_paths_must_be_absent() -> list[Path]:
    """Independent of the gate: these paths must not exist on disk."""
    return [
        EVIDENCE / "node-ship-doi-10.1000-xyz.json",
        EVIDENCE / "node-hold-1-missing-sibling.json",
        Path(
            "/opt/p2/ast-integrate/command-center/p2-wave/probes/IMP-0307/"
            "fixtures/evidence/no-such-anchor.json"
        ),
    ]
