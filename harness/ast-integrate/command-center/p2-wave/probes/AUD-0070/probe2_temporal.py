#!/usr/bin/env python3
"""Probe 2: independent temporal reclassification.

The known decision-log-versus-doc-13 pair and the planted later-resolution
pair must be SUPERSEDED. The planted same-as_of pair must stay CONTRADICTION.
A timestamp-blind mutant must misclassify the known pair as CONTRADICTION
(both-states: the temporal check is load-bearing).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import claims as CL  # noqa: E402
import graph as G  # noqa: E402
import pairwise as P  # noqa: E402

ART = REPO / "command-center" / "audit" / "AUD-0070-contradiction-edge-extraction.json"
UNIT = "AUD-0070"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def _edge(edges: list[dict], id_a: str, id_b: str) -> dict | None:
    want = {id_a, id_b}
    for e in edges:
        ends = {e.get("source"), e.get("target")} | {e.get("left_id"), e.get("right_id")}
        if want <= ends:
            return e
    return None


def evaluate() -> dict:
    built = G.build()
    edges = built["edges"]
    blind = built["blind_edges"]
    known = _edge(edges, CL.KNOWN_A, CL.KNOWN_B)
    planted_same = _edge(edges, CL.PLANT_SAME_A, CL.PLANT_SAME_B)
    planted_later = _edge(edges, CL.PLANT_LATER_A, CL.PLANT_LATER_B)
    known_blind = _edge(blind, CL.KNOWN_A, CL.KNOWN_B)
    later_blind = _edge(blind, CL.PLANT_LATER_A, CL.PLANT_LATER_B)
    types = {e["edge_type"] for e in edges}
    payload = {
        "probe": "probe2-temporal",
        "unit_id": UNIT,
        "known_type": None if known is None else known["edge_type"],
        "planted_same_type": None if planted_same is None else planted_same["edge_type"],
        "planted_later_type": None if planted_later is None else planted_later["edge_type"],
        "known_blind_type": None if known_blind is None else known_blind["edge_type"],
        "later_blind_type": None if later_blind is None else later_blind["edge_type"],
        "has_both_edge_types": types >= {"CONTRADICTION", "SUPERSEDED"},
        "n_edges": len(edges),
        "n_superseded": sum(1 for e in edges if e["edge_type"] == "SUPERSEDED"),
        "n_contradiction": sum(1 for e in edges if e["edge_type"] == "CONTRADICTION"),
    }
    payload["pass"] = bool(
        known is not None
        and known["edge_type"] == "SUPERSEDED"
        and planted_later is not None
        and planted_later["edge_type"] == "SUPERSEDED"
        and planted_same is not None
        and planted_same["edge_type"] == "CONTRADICTION"
        and known_blind is not None
        and known_blind["edge_type"] == "CONTRADICTION"
        and later_blind is not None
        and later_blind["edge_type"] == "CONTRADICTION"
        and payload["has_both_edge_types"]
    )
    return payload


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:AUD-0070" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    payload = evaluate()
    print(json.dumps(payload, sort_keys=True, default=str))
    if not payload["pass"]:
        return fail("temporal reclassification did not discriminate")
    art_known = _edge(doc.get("edges") or [], CL.KNOWN_A, CL.KNOWN_B)
    if art_known is None or art_known.get("edge_type") != "SUPERSEDED":
        return fail("artifact known pair is not SUPERSEDED")
    print(
        f"known={payload['known_type']} same={payload['planted_same_type']} "
        f"later={payload['planted_later_type']} blind_known={payload['known_blind_type']}"
    )
    print("SUCCESS:AUD-0070-probe2 known pair SUPERSEDED; same-time CONTRADICTION; blind mutant fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
