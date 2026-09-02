#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0094-semantic-diff-engine.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import differ as D  # noqa: E402
import fixtures as F  # noqa: E402
import jsonschema  # noqa: E402
import reviewer as R  # noqa: E402
from ir import DIMENSIONS  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0094-semantic-diff-engine.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0094/semantic-diff.schema.json"
PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0094/probe1_gold_pair.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0094/probe2_invariants.py"
)
QUESTION = (
    "Implementation target: a differ that takes two workflow IRs and reports, "
    "per dimension, what one carries that the other does not — so 2B step 3 "
    "semantic-diff operates on structure rather than on prose similarity."
)


def main() -> int:
    gold = D.diff_irs(F.gold_left(), F.gold_right())
    got = D.signature(gold)
    want = sorted(F.GOLD_SIGNATURE)
    if got != want:
        print("FAILED:WFA-0094 emit gold signature mismatch")
        print("got ", got)
        print("want", want)
        return 1

    self_rows = []
    for ir in F.corpus():
        rep = D.self_diff(ir)
        ord_rep = D.order_invariant(ir)
        if not D.empty_report(rep) or not D.empty_report(ord_rep):
            print(f"FAILED:WFA-0094 emit self-diff nonempty id={ir['id']}")
            return 1
        self_rows.append({"id": ir["id"], "self_empty": True, "order_empty": True})

    decoy = D.sequence_decoy_diff(F.gold_left(), F.gold_right(), "role")
    if decoy["empty"]:
        print("FAILED:WFA-0094 emit sequence decoy was empty on role permutation")
        return 1
    role_dim = next(d for d in gold["dimensions"] if d["dimension"] == "role")
    if not role_dim["empty"]:
        print("FAILED:WFA-0094 emit set-differ treated role permutation as a delta")
        return 1

    left, mutated = F.present_but_different_pair()
    ch = D.diff_irs(left, mutated)
    gate = next(d for d in ch["dimensions"] if d["dimension"] == "gate")
    if not gate["changed"] or gate["left_only"] or gate["right_only"]:
        print("FAILED:WFA-0094 emit PRESENT-BUT-DIFFERENT collapsed")
        return 1

    left, missing = F.absent_tool_pair()
    ab = D.diff_irs(left, missing)
    tool = next(d for d in ab["dimensions"] if d["dimension"] == "tool")
    if not tool["left_only"] or tool["changed"]:
        print("FAILED:WFA-0094 emit ABSENT collapsed into changed")
        return 1

    rev = R.review()
    if rev["verdict"] != "PASS" or not rev["both_states_rerun"]:
        print("FAILED:WFA-0094 emit reviewer")
        print(json.dumps(rev, indent=2))
        return 1

    pack_present = (REPO / PACK_REL).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "WFA-0094",
        "record_type": "SemanticDiff",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0094",
        "completion": "SUCCESS:WFA-0094",
        "title": (
            "Semantic differ over two workflow IRs at stage, role, gate, "
            "tool and stop-rule granularity"
        ),
        "question": QUESTION,
        "dimensions": list(DIMENSIONS),
        "engine": {
            "module": "command-center/p2-wave/probes/WFA-0094/differ.py",
            "comparison": "set-per-dimension",
            "absent_distinct_from_present_but_different": True,
            "order_insensitive_as_sets": True,
        },
        "evidence_a": {
            "id": "gold-fixture-pair",
            "claim": (
                "On a fixture pair with a known ground-truth difference set, "
                "the differ reports exactly that set — no misses and no extras."
            ),
            "left_id": "gold-left",
            "right_id": "gold-right",
            "expected_signature": [list(t) for t in want],
            "observed_signature": [list(t) for t in got],
            "report": gold,
            "exact_match": True,
            "command": P1,
        },
        "evidence_b": {
            "id": "self-diff-invariant",
            "claim": (
                "Diffing any IR against itself returns the empty set for every "
                "dimension; a differ that reports spurious differences on "
                "identity is broken in a way a fixture pair can mask."
            ),
            "corpus_n": len(self_rows),
            "corpus_ids": [r["id"] for r in self_rows],
            "all_self_empty": True,
            "all_order_shuffle_empty": True,
            "command": P2,
        },
        "tests": [
            {
                "id": "self-diff-empty-five-dimensions",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "absent-distinct-from-present-but-different",
                "result": "PASS",
                "command": P2,
                "present_but_different_gate": gate["changed"][0]["id"],
                "absent_tool": tool["left_only"][0]["id"],
            },
            {
                "id": "order-insensitive-compared-as-sets",
                "result": "PASS",
                "command": P2,
                "set_differ_role_empty": True,
                "sequence_decoy_role_nonempty": True,
            },
        ],
        "reviewer": rev,
        "residual_unknowns": [
            {
                "id": "WFA-0044-ir-spec-absent",
                "status": "ABSENT-ON-WORKTREE",
                "path": "command-center/wfa/WFA-0044-workflow-ir-spec.json",
                "note": (
                    "Catalog dependency. Differ consumes a five-dimension IR "
                    "subset documented in ir.py; it does not claim to be the "
                    "WFA-0044 spec."
                ),
            },
            {
                "id": "WFA-0054-roundtrip-absent",
                "status": "ABSENT-ON-WORKTREE",
                "path": "command-center/wfa/WFA-0054-ir-roundtrip-fidelity.json",
                "note": "Catalog dependency. No round-trip fidelity ledger on this tree.",
            },
            {
                "id": "WFA-0001-schema-pack",
                "status": (
                    "SHIM-PRESENT-REMOTE-REF"
                    if pack_present
                    else "ABSENT-ON-WORKTREE"
                ),
                "path": PACK_REL,
                "note": (
                    "Catalog output_schema pack is a generated shim that $refs "
                    "https://ast-integrate.invalid/platform/schema/"
                    "artifact-class-profiles.schema.json#/$defs/SemanticDiff. "
                    "This unit validates against the local probe schema "
                    "(semantic-diff.schema.json), not the remote fragment."
                    if pack_present
                    else (
                        "Declared output_schema pack is absent. Artifact is "
                        "checked against the local probe schema, not the "
                        "missing pack $defs/SemanticDiff."
                    )
                ),
            },
            {
                "id": "live-saved-workflow-corpus-absent",
                "status": "ABSENT-ON-WORKTREE",
                "path": "~/.claude/workflows",
                "note": (
                    "The ten saved Claude Code workflows are not on this Linux "
                    "worktree. Evidence uses a fixture IR corpus that exercises "
                    "the five dimensions, including loop, fan-out, human "
                    "checkpoint, and retry/resume shapes."
                ),
            },
        ],
        "downstream_consumers": [
            {"unit_id": "WFA-0095", "uses": "union-preservation over differ output"},
            {"unit_id": "WFA-0096", "uses": "planted-mutant control of this differ"},
            {"unit_id": "WFA-0100", "uses": "structural splice against IR pairs"},
        ],
        "declared_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SemanticDiff"
        ),
        "schema_pack_present": pack_present,
        "emitted_at": now,
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={out.stat().st_size} pack_present={pack_present}")
    print("SUCCESS:WFA-0094 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
