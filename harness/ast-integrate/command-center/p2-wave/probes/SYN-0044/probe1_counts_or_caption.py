#!/usr/bin/env python3
"""Probe 1: rendered counts equal source, or the omission is captioned (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import generate as G  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0044.diagram-set.json"
SCHEMA = REPO / "command-center/schema/diagram-manifest.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0044-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "SYN-0044":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if G.SENTINEL not in text:
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    dep = G.load_dependency_source(REPO)
    phase = G.load_phase_source(REPO)
    arch = G.load_architecture_source(REPO)
    live = {
        "dependency-register": dep,
        "phase-full": phase,
        "phase-critical-path": phase,
        "architecture-b06-inventory": arch,
    }

    matching = 0
    captioned = 0
    for rec in doc.get("diagrams") or []:
        did = rec.get("id")
        src = live.get(did)
        if src is None:
            return fail(f"unknown diagram id {did}")
        mermaid_path = REPO / rec["output_path"]
        if not mermaid_path.is_file():
            return fail(f"diagram file missing {rec['output_path']}")
        mermaid = mermaid_path.read_text(encoding="utf-8")
        node_n, edge_n = G.mermaid_counts(mermaid)
        source_n = len(src["nodes"])
        source_e = len(src["edges"])
        if rec["source_node_count"] != source_n or rec["source_edge_count"] != source_e:
            return fail(
                f"{did} recorded source {rec['source_node_count']}/{rec['source_edge_count']} "
                f"live {source_n}/{source_e}"
            )
        if node_n != rec["rendered_node_count"] or edge_n != rec["rendered_edge_count"]:
            return fail(
                f"{did} mermaid {node_n}/{edge_n} != recorded "
                f"{rec['rendered_node_count']}/{rec['rendered_edge_count']}"
            )
        if rec.get("counts_match") is True:
            if node_n != source_n or edge_n != source_e:
                return fail(
                    f"{did} claimed match but rendered {node_n}/{edge_n} source {source_n}/{source_e}"
                )
            matching += 1
        else:
            cap = rec.get("omission_caption") or rec.get("caption") or ""
            if node_n >= source_n and edge_n >= source_e:
                return fail(f"{did} claimed omission but counts are not below source")
            if len(cap) < 24 or cap not in mermaid:
                return fail(f"{did} omission not captioned in the diagram file")
            captioned += 1
        print(
            f"{did} source={source_n}/{source_e} rendered={node_n}/{edge_n} "
            f"match={rec.get('counts_match')}"
        )

    if matching < 1:
        return fail("no matching-count diagram")
    if captioned < 1:
        return fail("no captioned-omission diagram (caption path untested)")
    print(f"matching={matching} captioned_omission={captioned}")
    print("SUCCESS:SYN-0044-probe1 counts equal source or omission captioned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
