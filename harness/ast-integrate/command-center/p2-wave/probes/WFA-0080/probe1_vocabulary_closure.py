#!/usr/bin/env python3
"""Probe 1: node set equals frozen vocabulary; every edge endpoint resolves.

Both-states: extra node, dropped node, and dangling endpoint must fire.
Silent on the live emitted graph.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import semantic_graph as G  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0080-semantic-component-graph.json"
SCHEMA = HERE / "graph.schema.json"


def load_art() -> dict:
    return json.loads(ART.read_text(encoding="utf-8"))


def node_ids(doc: dict) -> set[str]:
    return {n["id"] for n in doc["nodes"]}


def endpoint_errors(doc: dict) -> list[str]:
    ids = node_ids(doc)
    bad: list[str] = []
    for e in doc["edges"]:
        if e["source"] not in ids:
            bad.append(f"dangling-source:{e['id']}:{e['source']}")
        if e["target"] not in ids:
            bad.append(f"dangling-target:{e['id']}:{e['target']}")
    return bad


def set_delta(doc: dict) -> dict[str, list[str]]:
    return G.node_set_delta(node_ids(doc), G.vocab_id_set())


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return [
        f"{list(e.path)}: {e.message}"
        for e in Draft202012Validator(schema).iter_errors(doc)
    ]


def main() -> int:
    if not ART.is_file():
        print("FAILED:WFA-0080-probe1 artifact missing")
        return 1
    doc = load_art()
    vocab = G.vocab_id_set()
    ids = node_ids(doc)
    delta = set_delta(doc)
    dangling = endpoint_errors(doc)
    sch = schema_errors(doc)
    rels = {e["relation"] for e in doc["edges"]}
    print(f"VOCAB n={len(vocab)}")
    print(f"NODES n={len(ids)}")
    print(f"DELTA missing={delta['missing_from_graph']} extra={delta['extra_in_graph']}")
    print(f"DANGLING n={len(dangling)} {dangling[:4]}")
    print(f"SCHEMA_ERRORS n={len(sch)}")
    print(f"RELATIONS {sorted(rels)}")
    print(f"SENTINEL {doc.get('sentinel')} STATE {doc.get('state')}")

    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0080-probe1 self-declared not delivering")
        return 1
    if "SUCCESS:WFA-0080" not in json.dumps(doc):
        print("FAILED:WFA-0080-probe1 sentinel absent")
        return 1
    if delta["missing_from_graph"] or delta["extra_in_graph"]:
        print("FAILED:WFA-0080-probe1 node set != vocabulary")
        return 1
    if dangling:
        print("FAILED:WFA-0080-probe1 dangling endpoints")
        return 1
    if sch:
        print("FAILED:WFA-0080-probe1 schema " + sch[0])
        return 1
    if not rels >= set(G.RELATIONS):
        print(f"FAILED:WFA-0080-probe1 missing relations {set(G.RELATIONS) - rels}")
        return 1

    extra = copy.deepcopy(doc)
    extra["nodes"].append(
        {
            "id": "mech.not-in-vocabulary",
            "kind": "canonical-mechanism",
            "label": "Planted extra",
            "definition": "Planted extra node that must break vocabulary equality.",
            "discriminating_example": "This id is not in the frozen vocabulary.",
            "catalog_source": "planted-mutant",
        }
    )
    d_extra = G.node_set_delta(node_ids(extra), vocab)
    if not d_extra["extra_in_graph"]:
        print("FAILED:WFA-0080-probe1 extra-node mutant did not fire")
        return 1

    missing = copy.deepcopy(doc)
    drop = missing["nodes"][0]["id"]
    missing["nodes"] = [n for n in missing["nodes"] if n["id"] != drop]
    d_missing = G.node_set_delta(node_ids(missing), vocab)
    if drop not in d_missing["missing_from_graph"]:
        print("FAILED:WFA-0080-probe1 missing-node mutant did not fire")
        return 1

    dang = copy.deepcopy(doc)
    dang["edges"].append(
        {
            "id": "e:planted-dangling",
            "source": doc["nodes"][0]["id"],
            "target": "mech.does-not-exist",
            "relation": "requires",
            "justification": "Planted dangling endpoint for the endpoint detector.",
        }
    )
    dang_errs = endpoint_errors(dang)
    live_errs = endpoint_errors(doc)
    if not dang_errs:
        print("FAILED:WFA-0080-probe1 dangling mutant did not fire")
        return 1
    if live_errs:
        print("FAILED:WFA-0080-probe1 live graph not silent for endpoints")
        return 1

    print(
        "NEGATIVE CONTROL verbatim: extra-node mutant extra_in_graph fires; "
        "dropped-node mutant missing_from_graph fires; planted dangling "
        "target fires; live graph is silent on all three."
    )
    print(
        "BOTH-STATES: FIRED on extra/missing/dangling mutants; SILENT on live "
        f"graph n={len(ids)}"
    )
    print("SUCCESS:WFA-0080-probe1 vocabulary-closure endpoints schema both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
