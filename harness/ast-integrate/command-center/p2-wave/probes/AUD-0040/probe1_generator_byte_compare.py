#!/usr/bin/env python3
"""Probe 1: re-run the generator and byte-compare to the committed graph."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

ART = C.REPO / C.OUT_REL
SCHEMA = C.REPO / C.SCHEMA_REL
GRAPH = C.REPO / C.GRAPH_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0040-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = C.catalog_sentinel()
    if sentinel not in text:
        return fail("catalog completion_sentinel absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errors:
        return fail(f"schema {errors[0].message}")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail("schema accepted garbage")

    if not GRAPH.is_file() or GRAPH.stat().st_size <= 0:
        return fail("committed DEPENDENCY-GRAPH.json missing")

    cat = C.load_catalog_mod()
    live = cat.load()
    generated = C.generate_graph_bytes(live)
    committed = GRAPH.read_bytes().replace(b"\r\n", b"\n")
    gen2 = C.generate_graph_bytes(live)
    match = generated == committed
    twice = generated == gen2
    print(
        json.dumps(
            {
                "generated_bytes": len(generated),
                "committed_bytes": len(committed),
                "generated_sha256": C.sha256_bytes(generated),
                "committed_sha256": C.sha256_bytes(committed),
                "byte_match": match,
                "second_generation_identical": twice,
                "node_count": json.loads(generated.decode("utf-8"))["node_count"],
                "edge_count": json.loads(generated.decode("utf-8"))["edge_count"],
            },
            sort_keys=True,
        )
    )
    if not match:
        return fail("generator output != committed DEPENDENCY-GRAPH.json")
    if not twice:
        return fail("generator is not byte-deterministic")
    recorded = (doc.get("measurement") or {}).get("generator") or {}
    if recorded.get("generated_sha256") != C.sha256_bytes(generated):
        return fail("artifact generator sha256 drifted from live re-run")
    if recorded.get("byte_match") is not True:
        return fail("artifact does not record byte_match")
    print(
        f"byte_match=True bytes={len(generated)} sha256={C.sha256_bytes(generated)} "
        f"nodes={json.loads(generated.decode('utf-8'))['node_count']} "
        f"edges={json.loads(generated.decode('utf-8'))['edge_count']}"
    )
    print("SUCCESS:AUD-0040-probe1 generator byte-compare committed file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
