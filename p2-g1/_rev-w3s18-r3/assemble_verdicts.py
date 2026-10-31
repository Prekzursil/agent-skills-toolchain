#!/usr/bin/env python3
"""Assemble VERDICTS-w3s18-r3.json from verify_out.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
v = json.loads((HERE / "verify_out.json").read_text(encoding="utf-8"))
res = v["results"]

unit_meta = {
    "RES-0179": "existing w4s16 closure genuine in provenance (independent, reviewed_at 2026-10-26T07:29:25Z) but stamp sits on a schema-invalid artifact; program gate c6 also UNSATISFIED (advisory)",
    "RES-0180": "same shape as RES-0179 (reviewed_at 07:29:26Z)",
    "RES-0182": "same shape as RES-0179 (reviewed_at 07:29:27Z); artifact is CRLF on disk, receipt/manifest rows correctly use the contract CRLF->LF basis",
    "TST-0018": "closure fabricated by builder/probe voice; program gate Layer-1 also 1 error; gate unsat [4]",
    "TST-0028": "closure fabricated; Layer-1 38 errors; gate unsat [4,11,12]",
    "TST-0032": "closure fabricated; Layer-1 31 errors; gate unsat [3,4,12]",
    "TST-0057": "closure fabricated; Layer-1 43 errors; gate unsat [3,4,6,8,11,12]",
    "TST-0060": "reviewer_id is literally schema-resolver (an instrument, not a reviewer); Layer-1 2 errors; gate unsat [4]",
    "TST-0066": "closure fabricated; Layer-1 63 errors; gate unsat [3,4,6,8,11,12]",
    "TST-0067": "closure fabricated; Layer-1 19 errors; gate unsat [3,4,6,12]",
    "TST-0068": "closure fabricated; Layer-1 17 errors; gate unsat [3,4,6]",
    "TST-0070": "closure fabricated; Layer-1 22 errors; gate unsat [3,4,6,11,12]",
}

out = {
    "wave": 3,
    "shard": 18,
    "round": "r3 (fresh independent reviewer; r1 and r2 both failed 12/12 on the same unrepaired receipts)",
    "reviewer": "claude-opus-5-5 independent reviewer review:w3s18 r3 2026-10-26",
    "units": v["units"],
    "battery": (
        "_rev-w3s18-r3/verify_w3s18_r3.py: A artifact (exists/non-empty/parses/"
        "not-self-blocked/sentinel), B live probe re-runs through the program DELIVERED "
        "transport (command-center/p2-wave/_measure_one_delivered.py) executed by THIS "
        "reviewer, C manifest row sha256+bytes on the contract CRLF->LF basis, "
        "D output_schema via TWO instruments (platform/lib/schema_resolver.validate_artifact "
        "+ direct Draft2020-12 compile of the declared file through a file:// registry) that "
        "AGREE on all 12, E receipt closure genuineness, F program receipt gate "
        "(receipt_schema_gate evaluate_full, advisory record). D2 both-states control "
        "executed: deleting a required field raises errors 2->3, repairing drops 2->1 - "
        "detector alive."
    ),
    "verdict_tally": v["verdict_tally"],
    "receipts_modified": False,
    "state_since_r2": (
        "all 12 receipts byte-unchanged since before the r2 review (mtimes: RES "
        "2026-10-26T07:31Z w4s16 closure write, TST 2026-10-24T05:50Z); the repair lane r2 "
        "named never ran, so the r2 defects persist byte-identically"
    ),
    "closure_assessment": (
        "0/12 closable. Green substance side held 12/12 (artifacts parse and are not "
        "self-blocked; every probe re-run by this reviewer exits 0; every manifest primary "
        "row digest-matches live on the normalized basis; sentinels present). But check D "
        "fails on every unit: each artifact violates its CATALOG-DECLARED output_schema "
        "(resolver and direct instrument agree exactly per unit), which makes every "
        "existing PASS stamp - including the three genuine-provenance w4s16 closures - "
        "unconfirmable under this shard contract, consistent with the w3s17-r3 "
        "closure_assessment precedent. Additionally 9/12 TST receipts carry FABRICATED "
        "independent-closure blocks (builder/probe-voiced reviewer_id, no reviewed_at): "
        "TST-0060 names an instrument (schema-resolver) as the reviewer. Per the unit "
        "contract only the independent reviewer closes; confirming those stamps would "
        "launder builder self-certification. Program completion predicate (gate_a) is "
        "UNSATISFIED on all 12 receipts (advisory F). Receipts left byte-unchanged per the "
        "FAIL rule."
    ),
    "schema_topology_note": (
        "declared command-center/schema/*.json are generated $ref shims into "
        "platform/schema; the errors (downstream_consumers / artifacts / "
        "manifest_registration required at root, tests[].command, artifacts[].bytes) look "
        "receipt-envelope-shaped, i.e. the root cause may be program-wide schema-topology "
        "rather than per-unit authoring - but D is a hard check under this wave contract "
        "(w3s9-r3/w3s17-r3/w3s24-r3 binding rule: resolver + raw draft-2020-12, both must "
        "be clean), so the units FAIL regardless of where the topology fix lands"
    ),
    "repair_lanes": {
        "TST-0018..TST-0070 (9 units)": "receipt-authoring lane rebuilds each receipt in receipt_core-valid shape with CURRENT digests, records the real probe evidence (c6 disjoint-method pairs, c8 negative controls, c11 manifest_registration block, c12 consumer rows), sets state per protocol (builder lanes must NOT stamp SUCCESS/independent), then RE-PINS probes/<id>/UNIT-ARTIFACT-MANIFEST.json (artifact==receipt, so the sha row must be recomputed after any receipt write); only then re-offer for independent review",
        "RES-0179/0180/0182": "closure emitter re-authors each artifact to satisfy its declared output_schema (or the schema-topology owner corrects the shim mapping), re-runs evaluate_full to complete:true, and re-pins the manifest row; the genuine w4s16 closure blocks can then be re-stamped on valid artifacts",
        "program-wide": "reconcile gate c3 raw-bytes hashing with the contract CRLF->LF-normalized basis (r2 note on RES-0182 still stands)",
    },
    "per_unit": {},
}

for uid, r in res.items():
    art = r["info"].get("artifact") or {}
    out["per_unit"][uid] = {
        "verdict": r["verdict"],
        "failing": r["fails"],
        "notes": unit_meta[uid],
        "green_sides": {
            "artifact_bytes_raw": art.get("bytes_raw"),
            "artifact_sha256_lf": art.get("sha256_lf"),
            "measure_delivered_live_by_this_reviewer": r["info"].get("measure_delivered_live"),
            "manifest_primary_sha_matches_live": not any(f.startswith("C ") for f in r["fails"]),
            "gate_complete": r["info"].get("gate_complete"),
            "gate_unsat_conditions": r["info"].get("gate_unsat_conditions"),
        },
    }

(HERE / "VERDICTS-w3s18-r3.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print("written; tally:", json.dumps(v["verdict_tally"]))
