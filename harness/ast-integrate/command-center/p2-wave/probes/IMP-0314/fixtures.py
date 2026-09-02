#!/usr/bin/env python3
"""Six graph shapes plus empty / missing-path extras for IMP-0314.

Shapes (catalog: unit cycle detection on 6 graph shapes):
  FIRE:   two-cycle, three-cycle, self-loop
  SILENT: linear, diamond, legit-cross-ref (distinct facts)
Empty graph is NOT-CHECKED (not one of the six).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX_DIR = HERE / "fixtures"
ANCHOR = "command-center/p2-wave/probes/IMP-0314/fixtures/anchors"
FACT_A = f"{ANCHOR}/fact-a.txt"
FACT_B = f"{ANCHOR}/fact-b.txt"
MEAS = f"{ANCHOR}/measurement.txt"
MISSING = f"{ANCHOR}/does-not-exist.txt"


def _n(nid: str, kind: str, text: str, **extra: Any) -> dict[str, Any]:
    row = {"id": nid, "kind": kind, "text": text}
    row.update(extra)
    return row


def _e(eid: str, src: str, dst: str, kind: str) -> dict[str, Any]:
    return {"id": eid, "src": src, "dst": dst, "kind": kind}


def _doc(
    fixture_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "fixture_id": fixture_id,
        "argument_graph": {"nodes": nodes, "edges": edges},
    }
    doc.update(extra)
    return doc


def two_cycle() -> dict[str, Any]:
    """A cites B cites A. Control: a real cycle must FIRE."""
    return _doc(
        "two-cycle",
        [
            _n("claim-A", "claim", "A because B", url="https://doi.example/10.1/a"),
            _n("claim-B", "claim", "B because A", url="https://doi.example/10.1/b"),
        ],
        [
            _e("ab", "claim-A", "claim-B", "CITES"),
            _e("ba", "claim-B", "claim-A", "CITES"),
        ],
    )


def three_cycle() -> dict[str, Any]:
    """p1→p2→p3→p1 with three distinct URLs. URL count must not hide the cycle."""
    return _doc(
        "three-cycle",
        [
            _n("p1", "claim", "P1 cites P2", url="https://doi.example/10.1/p1"),
            _n("p2", "claim", "P2 cites P3", url="https://doi.example/10.1/p2"),
            _n("p3", "claim", "P3 cites P1", url="https://doi.example/10.1/p3"),
        ],
        [
            _e("p12", "p1", "p2", "CITES"),
            _e("p23", "p2", "p3", "CITES"),
            _e("p31", "p3", "p1", "CITES"),
        ],
    )


def self_loop() -> dict[str, Any]:
    return _doc(
        "self-loop",
        [_n("claim-S", "claim", "S cites S", url="https://doi.example/10.1/s")],
        [_e("ss", "claim-S", "claim-S", "CITES")],
    )


def linear() -> dict[str, Any]:
    return _doc(
        "linear",
        [
            _n("evid-L", "evidence", "log line 44", path=MEAS),
            _n("claim-L", "claim", "Error rate is below budget"),
            _n("syn-L", "synthesis", "Error rate is below budget."),
        ],
        [
            _e("le", "evid-L", "claim-L", "SUPPORTS"),
            _e("lg", "claim-L", "syn-L", "GROUNDS"),
        ],
    )


def diamond() -> dict[str, Any]:
    """Shared ancestor, two paths, join. Not a cycle."""
    return _doc(
        "diamond",
        [
            _n("evid-D", "evidence", "shared measurement", path=MEAS),
            _n("claim-Da", "claim", "Path A"),
            _n("claim-Db", "claim", "Path B"),
            _n("claim-Join", "claim", "Join"),
            _n("syn-D", "synthesis", "Join holds."),
        ],
        [
            _e("d1", "evid-D", "claim-Da", "SUPPORTS"),
            _e("d2", "evid-D", "claim-Db", "SUPPORTS"),
            _e("d3", "claim-Da", "claim-Join", "SUPPORTS"),
            _e("d4", "claim-Db", "claim-Join", "SUPPORTS"),
            _e("dg", "claim-Join", "syn-D", "GROUNDS"),
        ],
    )


def legit_cross_ref() -> dict[str, Any]:
    """Docs mention each other; each uses the other's *distinct* fact. No node cycle."""
    return _doc(
        "legit-cross-ref",
        [
            _n(
                "evid-A-fact1",
                "evidence",
                "Doc A fact 1",
                path=FACT_A,
                url="https://publisher-a.example/fact1",
                origin_id="origin-A",
            ),
            _n(
                "evid-B-fact2",
                "evidence",
                "Doc B fact 2",
                path=FACT_B,
                url="https://publisher-b.example/fact2",
                origin_id="origin-B",
            ),
            _n("claim-from-B", "claim", "B uses A's fact 1"),
            _n("claim-from-A", "claim", "A uses B's fact 2"),
            _n("syn-1", "synthesis", "B's use of fact 1 holds."),
            _n("syn-2", "synthesis", "A's use of fact 2 holds."),
        ],
        [
            _e("xa", "evid-A-fact1", "claim-from-B", "SUPPORTS"),
            _e("xb", "evid-B-fact2", "claim-from-A", "SUPPORTS"),
            _e("xg1", "claim-from-B", "syn-1", "GROUNDS"),
            _e("xg2", "claim-from-A", "syn-2", "GROUNDS"),
        ],
        document_cross_refs={"docA": ["docB"], "docB": ["docA"]},
    )


def empty_graph() -> dict[str, Any]:
    return _doc("empty-graph", [], [])


def missing_path() -> dict[str, Any]:
    """Anchor-resolution must report the missing file, not drop it."""
    return _doc(
        "missing-path",
        [
            _n("evid-M", "evidence", "missing file", path=MISSING),
            _n("claim-M", "claim", "Claim with a dead path"),
        ],
        [_e("m1", "evid-M", "claim-M", "SUPPORTS")],
        cited_paths=[MISSING],
    )


SHAPE_BUILDERS = {
    "two-cycle": two_cycle,
    "three-cycle": three_cycle,
    "self-loop": self_loop,
    "linear": linear,
    "diamond": diamond,
    "legit-cross-ref": legit_cross_ref,
}

FIRE_IDS = ("two-cycle", "three-cycle", "self-loop")
SILENT_IDS = ("linear", "diamond", "legit-cross-ref")
SHAPE_IDS = FIRE_IDS + SILENT_IDS
CONTROL_ID = "two-cycle"
EMPTY_ID = "empty-graph"


def all_shapes() -> dict[str, dict[str, Any]]:
    return {k: fn() for k, fn in SHAPE_BUILDERS.items()}


def extras() -> dict[str, dict[str, Any]]:
    return {EMPTY_ID: empty_graph(), "missing-path": missing_path()}


def dump_json() -> list[Path]:
    dest = FIX_DIR / "graphs"
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fid, doc in {**all_shapes(), **extras()}.items():
        path = dest / f"{fid}.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in dump_json():
        print(p)

dump_json = dump_json
all_shapes = all_shapes
FIRE_IDS = FIRE_IDS
SILENT_IDS = SILENT_IDS
CONTROL_ID = CONTROL_ID
EMPTY_ID = EMPTY_ID
extras = extras
legit_cross_ref = legit_cross_ref
missing_path = missing_path
FACT_A = FACT_A
FACT_B = FACT_B
MEAS = MEAS
MISSING = MISSING
