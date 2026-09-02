#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0054-ir-roundtrip-fidelity.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import UPSTREAM_ARTIFACTS  # noqa: E402
from harness import evaluate_all  # noqa: E402

OUT = "command-center/wfa/WFA-0054-ir-roundtrip-fidelity.json"
SCHEMA_REF = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AdapterConformanceReport"
QUESTION = (
    "For every adapter, does native-to-IR-to-native round-tripping preserve all "
    "fields the adapter declares it carries - and where it does not, is the loss "
    "already recorded in the lossy-field ledger rather than discovered here?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0054/probe1_field_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0054/probe2_planted_mutation.py"
)


def build_report() -> dict:
    live = evaluate_all()
    if not live["admissible"]:
        raise SystemExit(
            "FAILED:WFA-0054 harness not admissible: "
            + json.dumps(
                {
                    "undeclared_total": live["undeclared_total"],
                    "planted_all_caught": live["planted_all_caught"],
                    "silent_drop": live["silent_drop_control"]["caught"],
                    "anchor": live["missing_anchor_control"]["raised"],
                    "full_corpus": live["full_corpus"],
                    "adapter_count": live["adapter_count"],
                }
            )
        )
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    adapters = []
    for row in live["adapters"]:
        adapters.append(
            {
                "adapter_id": row["adapter_id"],
                "unit_id": row["unit_id"],
                "claimed_corpus_size": row["claimed_corpus_size"],
                "ran_corpus_size": row["ran_corpus_size"],
                "full_corpus": row["full_corpus"],
                "declared_carried_fields": row["declared_carried_fields"],
                "declared_lossy_fields": row["declared_lossy_fields"],
                "undeclared_loss_count": row["undeclared_loss_count"],
                "clean_on_declared": row["clean_on_declared"],
                "field_level_diffs": [
                    {
                        "corpus_id": item["corpus_id"],
                        "differing_carried_fields": [
                            d["path"] for d in item["differing_carried_fields"]
                        ],
                        "declared_lossy_observed": item["declared_lossy_observed"],
                        "undeclared_losses": item["undeclared_losses"],
                    }
                    for item in row["items"]
                ],
                "matrix_expansion": row.get("matrix_expansion"),
            }
        )
    return {
        "record_type": "AdapterConformanceReport",
        "unit_id": "WFA-0054",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0054",
        "title": (
            "Round-trip fidelity harness: native to IR to native must be lossless "
            "on declared fields"
        ),
        "question": QUESTION,
        "schema_ref": SCHEMA_REF,
        "schema_pack_present": schema_pack.is_file(),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subject": (
            "In-tree dialect adapters (saved-workflow, metaswarm, skill-markdown, "
            "slash-command, langgraph, crew-autogen, dag-scheduler, github-actions, "
            "paper-protocol). Upstream WFA-0044..WFA-0053 artifacts are absent on "
            "this worktree; this unit does not claim those catalog outputs exist."
        ),
        "corpus_policy": (
            "Each adapter's claimed fixture corpus is run in full. Live host trees "
            "(~/.claude/workflows, the 96-skill family, this estate's "
            ".github/workflows) are absent here and were not silently substituted."
        ),
        "upstream_artifacts": live["upstream_artifacts"],
        "lossy_ledger_source": (
            "Per-adapter declared_lossy_fields in "
            "command-center/p2-wave/probes/WFA-0054/adapters.py. "
            "WFA-0055 catalog ledger is absent."
        ),
        "adapter_count": live["adapter_count"],
        "corpus_items_total": live["corpus_items_total"],
        "full_corpus": live["full_corpus"],
        "undeclared_total": live["undeclared_total"],
        "adapters": adapters,
        "planted_mutation": {
            "both_states": True,
            "every_planted_caught": live["planted_all_caught"],
            "cases": live["planted_mutation"],
        },
        "undeclared_loss_control": live["silent_drop_control"],
        "ir_anchor_control": live["missing_anchor_control"],
        "tests": [
            {
                "id": "T1-full-corpus-field-diff",
                "requirement": (
                    "round-trip must be run on the FULL corpus each adapter claims, "
                    "not on a sample"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-planted-mutation-both-states",
                "requirement": (
                    "every planted mutation must be caught (both-states control on "
                    "the harness itself)"
                ),
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-undeclared-loss-is-failure",
                "requirement": (
                    "an undeclared loss is a unit failure; a declared loss present "
                    "in the ledger is a pass"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0054-probe2-planted-mutation",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "method": (
                "Re-ran the harness both-states control: clean round-trip admitted, "
                "planted IR corruption caught on every adapter, silent drop of a "
                "carried field refused, IR node without source_anchor rejected."
            ),
        },
        "evidence_a": (
            "Per-adapter field-level diffs between original native and re-rendered "
            "native on the full claimed corpus, with exact differing-field lists "
            "(empty on declared-carried fields; declared lossy fields listed as "
            "observed drops)."
        ),
        "evidence_b": (
            "Planted-mutation control: one IR field corrupted mid-round-trip per "
            "adapter. Clean state remains admissible; planted state is caught "
            "before any clean result is treated as evidence."
        ),
        "admissible": True,
        "completion_sentinel": "SUCCESS:WFA-0054",
    }


def write_artifact() -> Path:
    report = build_report()
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dest


def main() -> int:
    path = write_artifact()
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print("SUCCESS:WFA-0054 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
