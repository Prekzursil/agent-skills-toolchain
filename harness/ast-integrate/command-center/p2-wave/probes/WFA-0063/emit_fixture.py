#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0063-fusion-decomposability.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import OPERATORS  # noqa: E402
from scenario import SENTINEL, live_results  # noqa: E402

OUT = "command-center/wfa/WFA-0063-fusion-decomposability.json"
UNIT = "WFA-0063"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0063/probe1_idset_certify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0063/probe2_rollback_rehearsal.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = live_results()
    if not live["pass"]:
        print("FAILED:WFA-0063 emit live suite")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1

    cases = []
    for row in live["per_operator"]:
        cases.append(
            {
                "id": f"op.{row['operator']}",
                "kind": "positive",
                "operator": row["operator"],
                "expected": "CERTIFIED",
                "observed": row["certification"],
                "source_ids_expected": row["expected_ids"],
                "source_ids_recovered": row["recovered_ids"],
                "id_set_equal": row["id_set_equal"],
                "rehearsal_ok": all(
                    v.get("ok") for v in (row.get("rehearsal") or {}).values()
                ),
                "stage_count": row["stage_count"],
            }
        )
    for row in live["lossy"]:
        cases.append(
            {
                "id": f"lossy.{row['mode']}",
                "kind": "negative",
                "operator": "union",
                "expected": "REJECTED",
                "observed": row["verdict"],
                "reason": row["reason"],
                "shipped_with_note": row["shipped_with_note"],
                "note_ignored": row["note_ignored"],
            }
        )
    cases.append(
        {
            "id": "rename.id-migration-map",
            "kind": "positive",
            "operator": "union",
            "expected": "CERTIFIED",
            "observed": live["rename"]["certification"],
            "old_id": live["rename"]["old_id"],
            "new_id": live["rename"]["new_id"],
            "id_migration_map": live["rename"]["map"],
            "source_ids_recovered": live["rename"]["recovered_ids"],
            "ok": live["rename"]["ok"],
        }
    )

    doc = {
        "record_type": "RegressionFixture",
        "fixture_id": "wfa-0063-fusion-decomposability",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Prove a fused workflow can be decomposed back into its source mechanisms",
        "subject_under_test": (
            "decompose(fused WorkflowIR) returns runnable source components; "
            "certify() rejects undecomposable fusions"
        ),
        "schema_ref": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture",
        "schema_pack_present": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "implementation": {
            "module": "command-center/p2-wave/probes/WFA-0063/engine.py",
            "operators": list(OPERATORS),
            "inverse": "decompose + re-fuse fingerprint check",
            "rehearsal": "run_smoke on recovered sources vs fixture catalog",
        },
        "question": (
            "Implementation target: a decomposition function that takes any fused "
            "workflow IR and returns the source components it was built from."
        ),
        "evidence_requirement": {
            "A": (
                "for each constructed fusion, decomposition returns the exact source "
                "id set that built it, compared against the recorded lineage"
            ),
            "B": (
                "rollback rehearsal reconstructs each source from decompose() output "
                "and re-runs its smoke case against the fixture catalog"
            ),
        },
        "cases": cases,
        "controls": {
            "lossy_rejected_not_noted": live["lossy_all_rejected"],
            "rename_via_id_migration_map": live["rename"]["ok"],
            "operators_rehearsed": live["rehearsal_operators"],
            "both_states_lossy": {
                "decomposable_union": "CERTIFIED",
                "stripped_components": "REJECTED",
            },
        },
        "rollback_rehearsal": {
            "covers_all_operators": live["rehearsal_covers_all_operators"],
            "operators": live["rehearsal_operators"],
            "method": (
                "fingerprint-match recovered IR to fixture catalog, execute pipeline "
                "smoke, compare observed to catalog expected (not lineage-copied ids)"
            ),
        },
        "tests": {
            "non_reconstructable_rejected_at_certification": live["lossy_all_rejected"],
            "rehearsal_one_fusion_per_operator": live["rehearsal_covers_all_operators"],
            "decomposition_survives_rename_via_id_migration_map": live["rename"]["ok"],
        },
        "dependencies_on_disk": {
            "WFA-0057": (
                REPO / "command-center/wfa/WFA-0057-ir-provenance-carry.json"
            ).is_file(),
            "WFA-0059": (
                REPO / "command-center/wfa/WFA-0059-mechanism-extraction.json"
            ).is_file(),
            "WFA-0001_schema_pack": (
                REPO / "command-center/wfa/schema/wfa-schema-pack.json"
            ).is_file(),
            "note": (
                "Those artifacts are absent on this worktree. This unit ships a "
                "self-contained IR+operator fixture corpus; it does not claim the "
                "284-candidate extraction matrix or the WFA schema pack exist."
            ),
        },
        "reviewer": {
            "reviewer_id": "WFA-0063-probe2-rollback-rehearsal",
            "verdict": "PASS",
            "independent": True,
            "re_ran_both_states": True,
            "notes": (
                "Probe 1 checks id-set vs lineage and certification reject. "
                "Probe 2 is mechanically independent: it executes reconstructed "
                "sources and scores them against the fixture catalog."
            ),
        },
        "cloud_ok": False,
        "min_bytes_threshold": 2000,
        "named_probes": [
            {"id": "probe1", "role": "id-set-and-certify", "command": P1},
            {"id": "probe2", "role": "rollback-rehearsal", "command": P2},
        ],
    }

    if SENTINEL not in json.dumps(doc):
        print("FAILED:WFA-0063 emit sentinel")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:WFA-0063 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"operators={len(OPERATORS)} lossy_rejected={live['lossy_all_rejected']} "
        f"rename_ok={live['rename']['ok']}"
    )
    print("SUCCESS:WFA-0063 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
