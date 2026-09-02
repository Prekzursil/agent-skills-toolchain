#!/usr/bin/env python3
"""Emit the WFA-0139 license-lattice foundry artifact."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
import lattice as L  # noqa: E402
import loader as LD  # noqa: E402
import reviewer as R  # noqa: E402
import schema_merge as SM  # noqa: E402
import seed as S  # noqa: E402

OUT = "command-center/foundry/WFA-0139-license-and-credit-propagation-lattice-through-fusio.json"
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0139/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0139/probe2_independent_recompute.py"
)
QUESTION = (
    "Implement most-restrictive-wins license propagation and credit "
    "carry-through for fusion, seeded by the 7 license_classification_rules "
    "and the 45-row license_risk_register in the provenance graph. Question: "
    "for every fusion whose sources span more than one license class, what is "
    "the resulting license, which combinations are prohibited outright, and "
    "does any fusion currently lose an attribution required by a source?"
)


def needle_line(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:WFA-0139 emit missing needle {needle!r} in {rel}")


def schema_def() -> dict:
    return SM.ensure_shared(REPO)


def main() -> int:
    corpus = LD.load_corpus(REPO)
    register = corpus["register_by_id"]
    fusions = [
        L.fuse_merge_unit(unit, register) for unit in corpus["merge_units"]
    ]
    if len(fusions) != 30:
        print(f"FAILED:WFA-0139 emit fusion count {len(fusions)}")
        return 1
    multi = [row for row in fusions if row.get("multi_class")]
    credit_ids = [
        row["fusion_id"] for row in fusions if row.get("attribution_lost")
    ]
    by_status: dict[str, int] = {}
    for row in multi:
        st = str(row.get("status") or "")
        by_status[st] = by_status.get(st, 0) + 1
    copyleft = L.fuse(
        [register["LR-01"], register["LR-16"]],
        register,
        fusion_id="both-states-copyleft-permissive",
    )
    unknown = L.fuse(
        [register["LR-01"], register["LR-41"]],
        register,
        fusion_id="both-states-unknown",
    )
    if copyleft["status"] != "ALLOWED" or copyleft["result_class"] != "STRONG_COPYLEFT":
        print("FAILED:WFA-0139 emit copyleft+permissive did not yield STRONG_COPYLEFT")
        return 1
    if unknown["status"] != "BLOCKED" or unknown["result_class"] is not None:
        print("FAILED:WFA-0139 emit unknown did not BLOCK")
        return 1
    review = R.review()
    if review["verdict"] != "PASS":
        print(f"FAILED:WFA-0139 emit reviewer {review}")
        return 1
    hist = corpus.get("histogram") or S.histogram(corpus["register"])
    catalog41 = {
        "THIRD-PARTY": hist.get("THIRD-PARTY", 0),
        "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY": hist.get(
            "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY", 0
        ),
        "ATTRIBUTION-REQUIRED": hist.get("ATTRIBUTION-REQUIRED", 0),
        "RIDER-RESTRICTED": hist.get("RIDER-RESTRICTED", 0),
        "UNCLASSIFIED": hist.get("UNCLASSIFIED", 0),
    }
    live = corpus["kind"] == "live-graph"
    honesty = (
        "Live 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json and "
        "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json are absent on this worktree; "
        "the 7 rules and 45-row register are reconstructed from the WFA-0033 "
        "catalog histogram (26/11/2/1/1) plus four seed-extension rows, and the "
        "30 merge_units are fixtures with the documented field names. Results "
        "are computed by lattice.fuse, not asserted. Not legal advice; catalog "
        "owner_approval_required remains open for any redistribution decision. "
        "UNKNOWN never defaults to PERMISSIVE."
        if not live
        else (
            "Live harness-restore graph and merge maps were loaded; lattice "
            "applied to those 7 rules, 45 register rows, and 30 merge_units. "
            "Not legal advice; owner_approval_required remains open for "
            "redistribution. UNKNOWN never defaults to PERMISSIVE."
        )
    )
    resulting = []
    for row in multi:
        resulting.append(
            {
                "fusion_id": row["fusion_id"],
                "status": row["status"],
                "result_class": row.get("result_class"),
                "reason": row.get("reason"),
                "rules_applied": row.get("rules_applied"),
                "source_class_set": row.get("source_class_set"),
                "attribution_lost": row.get("attribution_lost"),
            }
        )
    answer = (
        f"On the {corpus['kind']} corpus, {len(multi)} of 30 fusions span more "
        f"than one effective license class: {by_status.get('ALLOWED', 0)} ALLOWED "
        f"(most-restrictive-wins), {by_status.get('PROHIBITED', 0)} PROHIBITED "
        f"(copyleft+proprietary or any rider fusion; alternative "
        f"CLEAN-ROOM-REIMPLEMENT), {by_status.get('BLOCKED', 0)} BLOCKED "
        f"(unresolved or UNKNOWN, never permissive). Credit loss on "
        f"{len(credit_ids)} fusion(s): {credit_ids or 'none'}. "
        f"Copyleft+permissive control yields STRONG_COPYLEFT; unknown control "
        f"is BLOCKED. {honesty} SUCCESS:WFA-0139"
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lattice_rel = "command-center/p2-wave/probes/WFA-0139/lattice.py"
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    doc = {
        "unit_id": "WFA-0139",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0139",
        "title": "License and credit propagation lattice through fusion",
        "question": QUESTION,
        "answer": answer,
        "mechanism": "most-restrictive-wins license lattice with fail-closed unknown handling",
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA + "#/$defs/license-lattice",
        "owner_approval_required": True,
        "owner_signoff": "pending",
        "legal_advice": False,
        "classification_rules": corpus["rules"],
        "license_risk_register": corpus["register"],
        "register_histogram": hist,
        "catalog_histogram_41": catalog41,
        "lattice": {
            "ranks": L.RANK,
            "copyleft_classes": sorted(L.COPYLEFT),
            "unknown_never_permissive": True,
            "spdx_class": L.SPDX_CLASS,
        },
        "fusions": fusions,
        "multi_class_fusions": resulting,
        "prohibited_combinations": L.prohibited_class_pairs(),
        "credit_loss": {
            "any": bool(credit_ids),
            "fusion_ids": credit_ids,
            "note": (
                "MU-22 and MU-29 drop required CC-BY credits by construction so "
                "the detector is shown in both states (loss vs carry)."
                if not live
                else "Computed from live merge_unit carried credits versus required source credits."
            ),
        },
        "both_states": {
            "copyleft_plus_permissive": {
                "sources": ["LR-01", "LR-16"],
                "status": copyleft["status"],
                "result_class": copyleft["result_class"],
                "rules_applied": copyleft["rules_applied"],
                "expected": "STRONG_COPYLEFT",
            },
            "unknown_license": {
                "sources": ["LR-01", "LR-41"],
                "status": unknown["status"],
                "result_class": unknown["result_class"],
                "rules_applied": unknown["rules_applied"],
                "expected": "BLOCKED",
                "silent_permissive_default": False,
            },
        },
        "live_source": {
            "kind": corpus["kind"],
            "graph_path": corpus.get("graph_path"),
            "maps_path": corpus.get("maps_path"),
            "tried": corpus.get("tried"),
            "documented_graph_bytes": 344197,
            "documented_maps_bytes": 161920,
            "catalog_histogram_anchor": f"{catalog_rel}:{needle_line(catalog_rel, '26 THIRD-PARTY, 11 OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY')}",
        },
        "honesty": honesty,
        "evidence": [
            {
                "kind": "command",
                "detail": "copyleft+permissive yields STRONG_COPYLEFT; unknown BLOCKS",
                "anchor": f"command-center/p2-wave/probes/WFA-0139/probe1_both_states.py:{needle_line('command-center/p2-wave/probes/WFA-0139/probe1_both_states.py', 'print(\"both-states copyleft+permissive\")')}",
            },
            {
                "kind": "file-line",
                "detail": "UNKNOWN fail-closed branch never returns PERMISSIVE",
                "anchor": f"{lattice_rel}:{needle_line(lattice_rel, 'R2 UNKNOWN-FAIL-CLOSED')}",
            },
        ],
        "tests": [
            {
                "id": "copyleft-plus-permissive",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "unknown-fail-closed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-recompute-and-rule-index",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": review["reviewer_id"],
            "verdict": review["verdict"],
            "independent": True,
            "both_states_rerun": True,
            "mismatch_count": review["mismatch_count"],
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "schema"},
            {"path": lattice_rel, "role": "engine"},
        ],
    }
    jsonschema.validate(doc, schema_def())
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} fusions={len(fusions)} multi={len(multi)} credit_loss={credit_ids}")
    print("SUCCESS:WFA-0139 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
