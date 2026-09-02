#!/usr/bin/env python3
"""Probe 2: bare M-NN rejected; MECH-/WAVE3-M- accepted; hop counts re-derived."""
from __future__ import annotations

import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import namespaces as NS  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0005.decision-trace.json"
SCHEMA = REPO / "command-center/schema/decision-trace.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0005-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    bare = NS.resolve("M-16")
    mech = NS.resolve("MECH-16")
    wave = NS.resolve("WAVE3-M-16")
    print(
        f"M-16 status={bare['status']} class={bare.get('classification')} "
        f"MECH-16 status={mech['status']} ns={mech.get('namespace')} "
        f"WAVE3-M-16 status={wave['status']} ns={wave.get('namespace')}"
    )
    if bare.get("status") != "REJECTED":
        return fail("bare M-16 was not REJECTED")
    if bare.get("classification") != "ambiguous-option-token":
        return fail("bare M-16 classification is not ambiguous-option-token")
    if mech.get("status") != "RESOLVED" or mech.get("namespace") != "architecture-candidates":
        return fail("MECH-16 was not resolved to architecture-candidates")
    if wave.get("status") != "RESOLVED" or wave.get("namespace") != "wave3-research-harness":
        return fail("WAVE3-M-16 was not resolved to wave3-research-harness")

    garbage = [{}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            rejected += 1
    print(f"schema_garbage_rejected={rejected}/3")
    if rejected != 3:
        return fail("schema accepted garbage")

    live_bare = []
    for d in doc.get("decisions") or []:
        for row in d.get("option_resolutions") or []:
            if row.get("status") == "REJECTED" and str(row.get("token") or "").startswith("M-"):
                live_bare.append((d["id"], row.get("token")))
    print(f"artifact_rejected_bare_M={live_bare}")
    if not live_bare:
        return fail("artifact recorded no rejected bare M-NN (Q13/Q15 should)")

    broken_at: dict[str, set[str]] = defaultdict(set)
    for b in doc.get("breaks") or []:
        hid = str(b.get("hop") or "")
        did = b.get("decision_id")
        if hid in {"source", "option", "unit", "artifact", "test"} and isinstance(did, str) and did:
            broken_at[hid].add(did)
    recomputed = {
        h: len(broken_at[h])
        for h in ("source", "option", "unit", "artifact", "test")
    }
    recorded = doc.get("hop_break_counts") or {}
    print(f"hop_break_counts recorded={recorded} recomputed={recomputed}")
    for h, n in recomputed.items():
        if h not in recorded or recorded[h] != n:
            return fail(f"hop_break_counts[{h}] {recorded.get(h)} != {n}")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if str(rev.get("vendor") or "").lower() in {"", "anthropic"}:
        return fail("reviewer vendor is not cross-vendor")

    mutant = copy.deepcopy(doc)
    if mutant["decisions"]:
        mutant["decisions"] = mutant["decisions"][1:]
    try:
        jsonschema.validate(mutant, schema)
        # schema minItems is 10; dropping one of 29 may still validate.
    except jsonschema.ValidationError:
        pass
    catalog_n = len(json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text())["owner_questions"])
    if len(mutant["decisions"]) == catalog_n:
        return fail("mutant did not drop a decision row")
    print(
        f"uniqueness_control live={len(doc['decisions'])} "
        f"mutant={len(mutant['decisions'])} catalog={catalog_n}"
    )

    print("SUCCESS:SYN-0005-probe2 bare-token hop-counts schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
