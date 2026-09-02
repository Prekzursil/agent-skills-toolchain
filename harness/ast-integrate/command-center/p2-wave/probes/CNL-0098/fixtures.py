#!/usr/bin/env python3
"""Typed argument-graph fixtures for CNL-0098.

Planted-bad, known-good, detector-control, empty, diamond, legitimate
cross-reference, and URL-diverse cycle. JSON copies live under fixtures/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX_DIR = HERE / "fixtures"


def _node(nid: str, kind: str, text: str, **extra: Any) -> dict[str, Any]:
    row = {"id": nid, "kind": kind, "text": text}
    row.update(extra)
    return row


def _edge(eid: str, src: str, dst: str, kind: str) -> dict[str, Any]:
    return {"id": eid, "src": src, "dst": dst, "kind": kind}


def _doc(
    fixture_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    sentences: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "fixture_id": fixture_id,
        "argument_graph": {"nodes": nodes, "edges": edges},
        "synthesis": {"sentences": sentences},
    }
    doc.update(extra)
    return doc


def planted_weak() -> dict[str, Any]:
    """One grounded sentence and one orphan sentence. Weak synthesis FIRE."""
    return _doc(
        "planted-weak",
        [
            _node("evid-1", "evidence", "bench.json reports p99=12ms", url="https://ex.example/a"),
            _node("claim-1", "claim", "Latency is acceptable"),
            _node("syn-ok", "synthesis", "Latency is acceptable given the bench."),
            _node("syn-orphan", "synthesis", "Therefore migrate the fleet next week."),
        ],
        [
            _edge("e1", "evid-1", "claim-1", "SUPPORTS"),
            _edge("e2", "claim-1", "syn-ok", "GROUNDS"),
        ],
        [
            {"id": "syn-ok", "text": "Latency is acceptable given the bench."},
            {"id": "syn-orphan", "text": "Therefore migrate the fleet next week."},
        ],
    )


def planted_cycle() -> dict[str, Any]:
    """3-node support cycle with external evidence. Cycle FIRE, weak SILENT."""
    return _doc(
        "planted-cycle",
        [
            _node("evid-x", "evidence", "trace id T-9", url="https://ex.example/t"),
            _node("c1", "claim", "A is true because B"),
            _node("c2", "claim", "B is true because C"),
            _node("c3", "claim", "C is true because A"),
            _node("syn-ok", "synthesis", "A holds."),
        ],
        [
            _edge("ex", "evid-x", "c1", "SUPPORTS"),
            _edge("ab", "c1", "c2", "SUPPORTS"),
            _edge("bc", "c2", "c3", "SUPPORTS"),
            _edge("ca", "c3", "c1", "SUPPORTS"),
            _edge("g", "c1", "syn-ok", "GROUNDS"),
        ],
        [{"id": "syn-ok", "text": "A holds."}],
    )


def planted_circular_ungrounded() -> dict[str, Any]:
    """Cycle with no evidence: manufactures support out of nothing. Both FIRE."""
    return _doc(
        "planted-circular-ungrounded",
        [
            _node("u1", "claim", "U1 because U2"),
            _node("u2", "claim", "U2 because U3"),
            _node("u3", "claim", "U3 because U1"),
            _node("syn-fake", "synthesis", "The loop proves U1."),
        ],
        [
            _edge("u12", "u1", "u2", "SUPPORTS"),
            _edge("u23", "u2", "u3", "SUPPORTS"),
            _edge("u31", "u3", "u1", "SUPPORTS"),
            _edge("ug", "u1", "syn-fake", "GROUNDS"),
        ],
        [{"id": "syn-fake", "text": "The loop proves U1."}],
    )


def known_present() -> dict[str, Any]:
    """Detector-control: distinctive orphan id and 3-cycle KNOWN-A/B/C."""
    return _doc(
        "detector-control-known-present",
        [
            _node("KNOWN-EVID", "evidence", "control measurement", url="https://ex.example/k"),
            _node("KNOWN-CLAIM", "claim", "Control claim"),
            _node("KNOWN-A", "claim", "A cites B"),
            _node("KNOWN-B", "claim", "B cites C"),
            _node("KNOWN-C", "claim", "C cites A"),
            _node("syn-KNOWN-OK", "synthesis", "Control claim holds."),
            _node("syn-KNOWN-ORPHAN", "synthesis", "Orphan control sentence."),
        ],
        [
            _edge("ke", "KNOWN-EVID", "KNOWN-CLAIM", "SUPPORTS"),
            _edge("kg", "KNOWN-CLAIM", "syn-KNOWN-OK", "GROUNDS"),
            _edge("kab", "KNOWN-A", "KNOWN-B", "SUPPORTS"),
            _edge("kbc", "KNOWN-B", "KNOWN-C", "SUPPORTS"),
            _edge("kca", "KNOWN-C", "KNOWN-A", "SUPPORTS"),
        ],
        [
            {"id": "syn-KNOWN-OK", "text": "Control claim holds."},
            {"id": "syn-KNOWN-ORPHAN", "text": "Orphan control sentence."},
        ],
    )


def clean_linear() -> dict[str, Any]:
    return _doc(
        "clean-linear",
        [
            _node("evid-L", "evidence", "log line 44", url="https://ex.example/l"),
            _node("claim-L", "claim", "Error rate is below budget"),
            _node("syn-L", "synthesis", "Error rate is below budget."),
        ],
        [
            _edge("le", "evid-L", "claim-L", "SUPPORTS"),
            _edge("lg", "claim-L", "syn-L", "GROUNDS"),
        ],
        [{"id": "syn-L", "text": "Error rate is below budget."}],
    )


def diamond() -> dict[str, Any]:
    """Shared ancestor, two paths, join. Not a cycle."""
    return _doc(
        "diamond",
        [
            _node("evid-D", "evidence", "shared measurement", url="https://ex.example/d"),
            _node("claim-Da", "claim", "Path A"),
            _node("claim-Db", "claim", "Path B"),
            _node("claim-Join", "claim", "Join"),
            _node("syn-D", "synthesis", "Join holds."),
        ],
        [
            _edge("d1", "evid-D", "claim-Da", "SUPPORTS"),
            _edge("d2", "evid-D", "claim-Db", "SUPPORTS"),
            _edge("d3", "claim-Da", "claim-Join", "SUPPORTS"),
            _edge("d4", "claim-Db", "claim-Join", "SUPPORTS"),
            _edge("dg", "claim-Join", "syn-D", "GROUNDS"),
        ],
        [{"id": "syn-D", "text": "Join holds."}],
    )


def legit_cross_ref() -> dict[str, Any]:
    """Docs cite each other for distinct facts. No support cycle."""
    return _doc(
        "legit-cross-ref",
        [
            _node(
                "evid-A-fact1",
                "evidence",
                "Doc A fact 1",
                url="https://publisher-a.example/fact1",
                origin_id="origin-A",
            ),
            _node(
                "evid-B-fact2",
                "evidence",
                "Doc B fact 2",
                url="https://publisher-b.example/fact2",
                origin_id="origin-B",
            ),
            _node("claim-from-B", "claim", "B uses A's fact 1"),
            _node("claim-from-A", "claim", "A uses B's fact 2"),
            _node("syn-1", "synthesis", "B's use of fact 1 holds."),
            _node("syn-2", "synthesis", "A's use of fact 2 holds."),
        ],
        [
            _edge("xa", "evid-A-fact1", "claim-from-B", "SUPPORTS"),
            _edge("xb", "evid-B-fact2", "claim-from-A", "SUPPORTS"),
            _edge("xg1", "claim-from-B", "syn-1", "GROUNDS"),
            _edge("xg2", "claim-from-A", "syn-2", "GROUNDS"),
        ],
        [
            {"id": "syn-1", "text": "B's use of fact 1 holds."},
            {"id": "syn-2", "text": "A's use of fact 2 holds."},
        ],
        document_cross_refs={"docA": ["docB"], "docB": ["docA"]},
    )


def url_launder_cycle() -> dict[str, Any]:
    """Three distinct URLs in a support cycle. URL count must not hide the cycle."""
    return _doc(
        "url-launder-cycle",
        [
            _node("p1", "claim", "Paper 1 cites paper 2", url="https://doi.example/10.1/p1"),
            _node("p2", "claim", "Paper 2 cites paper 3", url="https://doi.example/10.1/p2"),
            _node("p3", "claim", "Paper 3 cites paper 1", url="https://doi.example/10.1/p3"),
        ],
        [
            _edge("p12", "p1", "p2", "CITES"),
            _edge("p23", "p2", "p3", "CITES"),
            _edge("p31", "p3", "p1", "CITES"),
        ],
        [],
    )


def empty_graph() -> dict[str, Any]:
    return _doc("empty-graph", [], [], [])


def all_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "planted-weak": planted_weak(),
        "planted-cycle": planted_cycle(),
        "planted-circular-ungrounded": planted_circular_ungrounded(),
        "detector-control-known-present": known_present(),
        "clean-linear": clean_linear(),
        "diamond": diamond(),
        "legit-cross-ref": legit_cross_ref(),
        "url-launder-cycle": url_launder_cycle(),
        "empty-graph": empty_graph(),
    }


PLANTED_BAD_IDS = (
    "planted-weak",
    "planted-cycle",
    "planted-circular-ungrounded",
    "url-launder-cycle",
)
CLEAN_IDS = ("clean-linear", "diamond", "legit-cross-ref")
CONTROL_ID = "detector-control-known-present"
EMPTY_ID = "empty-graph"


def dump_json() -> list[Path]:
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fid, doc in all_fixtures().items():
        path = FIX_DIR / f"{fid}.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in dump_json():
        print(p)
