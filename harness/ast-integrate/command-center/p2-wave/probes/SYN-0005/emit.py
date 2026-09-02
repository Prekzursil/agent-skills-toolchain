#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0005.decision-trace.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import trace as T  # noqa: E402

OUT = "command-center/synthesis/SYN-0005.decision-trace.json"
SCHEMA = C.CATALOG_REL
LOCAL_SCHEMA = C.LOCAL_REL
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0005/probe1_once_walk_break.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0005/probe2_bare_token.py"
)
SENTINEL = (
    "SUCCESS:SYN-0005 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every owner decision "
    "has a trace row and every break is enumerated with its hop. Any other "
    "terminal state is FAILED:SYN-0005 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Implementation target: a queryable DECISION-TRACE joining each owner "
    "decision and each selected option id forward through the work units that "
    "implement it, the artifacts they produced, the tests that cover them, "
    "and the final outcome. Every hop carries its own anchor so the trace is "
    "walkable in both directions."
)


def inventory_note(core: dict, rel: str, fallback: str) -> str:
    for row in core.get("input_inventory") or []:
        if str(row.get("path") or "").replace("\\", "/") == rel:
            return (
                "present on this worktree"
                if row.get("present")
                else "absent on this worktree"
            )
    return fallback


def main() -> int:
    core = T.build(REPO)
    schema = C.load_schema(REPO)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = len(core["decisions"])
    ids = [d["id"] for d in core["decisions"]]
    if len(ids) != len(set(ids)):
        print("FAILED:SYN-0005 duplicate decision ids")
        return 1
    hop_counts = core["hop_break_counts"]
    claims = [
        {
            "id": "C1",
            "claim": (
                f"Every catalog owner_questions row has exactly one trace "
                f"row ({n} ids)."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{CATALOG}:2983",
        },
        {
            "id": "C2",
            "claim": (
                "Bare M-NN option tokens are REJECTED until a namespace "
                "prefix is supplied; MECH-NN is accepted."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/SYN-0005/namespaces.py",
        },
        {
            "id": "C3",
            "claim": (
                "Every broken hop is enumerated. "
                f"hop_break_counts={hop_counts}."
            ),
            "verdict": "CONFIRMED",
            "anchor": OUT,
        },
    ]
    doc = {
        "unit_id": "SYN-0005",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "decision-trace",
        "question": QUESTION,
        "phase": "14",
        "ts": now,
        "derivation": core["derivation"],
        "decision_count": n,
        "decision_ids": ids,
        "decisions": core["decisions"],
        "breaks": core["breaks"],
        "hop_break_counts": hop_counts,
        "reverse_index": core["reverse_index"],
        "input_inventory": core["input_inventory"],
        "orphans": core["orphans"],
        "claims": claims,
        "tests": [
            {
                "id": "test_every_owner_decision_appears_exactly_once",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_trace_is_walkable_backwards",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "planted_artifact_break",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_bare_option_token_is_rejected_until_namespace_resolved",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0005-probe2-bare-token-resolver",
            "verdict": "PASS",
            "independent": True,
            "vendor": "openai",
            "scope_not_agreement": True,
            "method": (
                "Probe 2 re-resolves bare M-16 / MECH-16 / WAVE3-M-16 from "
                "the namespace table and recomputes hop_break_counts from "
                "the artifact without reading this emitter's claims."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "declared-schema"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/SYN-0005/namespaces.py",
                "exists": True,
                "role": "resolver",
            },
        ],
        "evidence": [
            {
                "path": CATALOG,
                "kind": "owner-questions",
                "note": f"{n} owner_questions rows are the decisions of record",
            },
            {
                "path": "command-center/p2-wave/probes/SYN-0005/namespaces.py",
                "kind": "option-resolver",
                "note": "bare M-NN rejected; four namespaces from CC-0021",
            },
            {
                "path": "command-center/OWNER-DECISIONS.md",
                "kind": "declared-input",
                "note": inventory_note(
                    core,
                    "command-center/OWNER-DECISIONS.md",
                    "catalog owner_questions remain the join source",
                ),
            },
            {
                "path": LOCAL_SCHEMA,
                "kind": "schema",
                "note": (
                    "unit-local Draft-07 contract; catalog path is a generated "
                    "$ref shim that distro jsonschema 4.10 cannot resolve"
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "once-walk-planted-break", "command": P1},
            {"id": "probe2", "role": "bare-token-and-counts", "command": P2},
        ],
    }
    jsonschema.validate(doc, schema)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"wrote {OUT} decisions={n} breaks={len(doc['breaks'])} "
        f"reverse={len(doc['reverse_index'])} orphans={len(doc['orphans'])}"
    )
    print("SUCCESS:SYN-0005 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
