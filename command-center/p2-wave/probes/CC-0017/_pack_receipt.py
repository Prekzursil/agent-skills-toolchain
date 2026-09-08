#!/usr/bin/env python3
"""Pack CC-0017 receipt as honest BLOCKED pending dual independent reviewers.

Never invents SUCCESS or independent-review.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0017"
OUT = "command-center/receipts/CC-0017.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/CC-0017/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-08T03:10:00Z"

# Dual reviewers owed by catalog reviewer_requirement — never stubbed.
BLOCKED_ON = (
    "TWO independent reviewers owed and absent: "
    "(1) cross-vendor reviewer on the provisional claim-record schema; "
    "(2) independent reviewer who re-derives whether the 1->2 edge really "
    "becomes SOFT rather than accepting the author's schedule claim "
    "(224 units / critical path 11->10). "
    "Neither independent-review.json nor SUCCESS:CC-0017 was invented."
)


def build() -> dict:
    p1 = json.loads((PROBE / "probe1-claim-record-summary.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-claim-record.raw.txt").read_text(encoding="utf-8")
    pytest_out = (PROBE / "pytest-claim-record.out").read_text(encoding="utf-8")
    schedule = json.loads((PROBE / "schedule-recompute.json").read_text(encoding="utf-8"))
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not p1.get("ok"):
        raise SystemExit(f"refusing pack: probe not ok: {p1}")

    # Refuse packing SUCCESS — dual reviews are missing by construction.
    review_path = PROBE / "independent-review.json"
    if review_path.is_file():
        raise SystemExit(
            "refusing pack: independent-review.json unexpectedly present; "
            "this implementer lane must not invent dual reviews"
        )

    sched = schedule["schedule_claim_recomputed"]
    sentinel = (
        f"FAILED:{UNIT} blocked-on-dual-independent-reviewers; "
        f"PROVISIONAL schema supersedes_by=ARC-0085; "
        f"schedule recomputed units={sched['units_released']} "
        f"critpath {sched['critical_path_before']}->{sched['critical_path_after']}; "
        f"SUCCESS:{UNIT} withheld (success_invented=false)"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0017",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent-worktree",
        },
        "artifacts": [
            L.art(
                "command-center/schema/claim-record.provisional.v1.schema.json",
                "primary",
            ),
            L.art("command-center/schema/CLAIM-RECORD-PROVISIONAL.md", "supporting"),
            L.art("tools/command-center/claim_record.py", "primary"),
            L.art("tools/command-center/tests/test_claim_record.py", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0017/probe1-claim-record.raw.txt", "log"),
            L.art("command-center/p2-wave/probes/CC-0017/pytest-claim-record.out", "log"),
            L.art("command-center/p2-wave/probes/CC-0017/schedule-recompute.json", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0017/migrated-three.json", "supporting"),
            L.art("command-center/receipts/CC-0012.json", "supporting"),
        ],
        "evidence": [
            L.evidence(
                (
                    "PROVISIONAL Phase-1 claim-record schema authored at "
                    "claim-record.provisional.v1.schema.json; explicitly PROVISIONAL "
                    "and superseded by Phase-4 unit ARC-0085."
                ),
                "CONFIRMED",
                "command-center/schema/claim-record.provisional.v1.schema.json",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B tools/command-center/claim_record.py meta",
                        json.dumps(
                            {
                                "schema_status": "PROVISIONAL",
                                "superseded_by_unit": "ARC-0085",
                            }
                        ),
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "read x-provisional + x-superseded-by-unit",
                        "x-provisional=true x-superseded-by-unit=ARC-0085",
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Schedule claim recomputed from PHASE-GRAPH edges[] after in-memory "
                    f"1->2 HARD->SOFT: units_released={sched['units_released']}, "
                    f"critical_path {sched['critical_path_before']}->"
                    f"{sched['critical_path_after']} "
                    f"(path={schedule['after']['critical_path']}). "
                    "Not restated from prior phase-graph prose."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/CC-0017/schedule-recompute.json",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B tools/command-center/claim_record.py schedule",
                        json.dumps(sched),
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CC-0017/probe1_claim_record.py",
                        raw1,
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Dependency CC-0012 verified SUCCESS before packing "
                    "(freeze/migration rules in force)."
                ),
                "CONFIRMED",
                "command-center/receipts/CC-0012.json",
                [
                    L.probe(
                        "source",
                        "file-read",
                        "read command-center/receipts/CC-0012.json state",
                        "state=SUCCESS",
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "sentinel contains SUCCESS:CC-0012",
                        "SUCCESS:CC-0012 present",
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Planted controls green: missing settling_probe rejected; "
                    "duplicate_of cycle rejected; contradiction to nonexistent id "
                    "rejected; three CLAIM-REGISTRY rows migrated with zero field loss."
                ),
                "CONFIRMED",
                "tools/command-center/tests/test_claim_record.py",
                [
                    L.probe(
                        "source",
                        "test-run",
                        "python3 -m pytest tools/command-center/tests/test_claim_record.py -q",
                        pytest_out,
                        p1["pytest_rc"],
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "probe1 controls object",
                        json.dumps(p1["controls"]),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot to a minimal record with explicit extension "
                "points; do not grow the schema a third time to accommodate an outlier."
            ),
        },
        "tests": [
            {
                "id": "no-settling-probe",
                "name": "Claim with no settling probe rejected.",
                "command": "python3 -m pytest tools/command-center/tests/test_claim_record.py::test_missing_settling_probe_is_rejected -q",
                "result": "PASS",
                "assertions": 2,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "duplicate-of-cycle",
                "name": "Duplicate-of cycle rejected.",
                "command": "python3 -m pytest tools/command-center/tests/test_claim_record.py::test_duplicate_of_cycle_is_rejected -q",
                "result": "PASS",
                "assertions": 2,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "ghost-contradiction",
                "name": "Contradiction edge to nonexistent claim id rejected.",
                "command": "python3 -m pytest tools/command-center/tests/test_claim_record.py::test_contradiction_to_nonexistent_claim_id_is_rejected -q",
                "result": "PASS",
                "assertions": 2,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "migrate-roundtrip",
                "name": "Migrate three real CLAIM-REGISTRY records with no field loss.",
                "command": "python3 -m pytest tools/command-center/tests/test_claim_record.py::test_roundtrip_migrate_three_real_registry_records_no_field_loss -q",
                "result": "PASS",
                "assertions": 4,
                "output_tail": pytest_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "no-settling-probe",
                "mutation",
                "Omit/blank settling_probe -> validator rejects.",
                True,
                True,
                bad="settling_probe missing/blank",
                good="settling_probe non-empty",
            ),
            L.control(
                "duplicate-of-cycle",
                "mutation",
                "A->B->A duplicate_of cycle -> registry reject.",
                True,
                True,
                bad="cycle A->B->A",
                good="acyclic duplicate_of DAG",
            ),
            L.control(
                "ghost-contradiction",
                "mutation",
                "contradicts nonexistent id -> reject.",
                True,
                True,
                bad="contradicts GHOST",
                good="contradicts only known ids",
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-dual-fresh-context",
            "verdict": "FAIL",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Catalog requires TWO reviewers: (1) cross-vendor on the schema, "
                "(2) independent re-derivation that 1->2 becomes SOFT. "
                "Implementer lane emits BLOCKED; does not invent reviews or SUCCESS."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "claim_record.validate_registry",
                "artifact_path": "command-center/p2-wave/probes/CC-0017/migrated-three.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    "python3 -B tools/command-center/claim_record.py validate-file "
                    "command-center/p2-wave/probes/CC-0017/migrated-three.json",
                    "VALID claims=3",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Whether 1->2 is truly SOFT after provisional schema authorship "
                    "remains CONTESTED until an independent reviewer re-derives it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer re-runs schedule recompute from edges[] "
                    "and argues SOFT/HARD from first principles without reading the "
                    "author's schedule claim text."
                ),
            },
            {
                "claim": (
                    "Cross-vendor schema fitness (field necessity vs ARC-0085 formal "
                    "contract) is unchecked in this lane."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Non-anthropic reviewer critiques provisional schema field-by-field "
                    "against a named Phase-2 consumer."
                ),
            },
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review", "dependency-blocked"],
            "reason": (
                "Implementation + planted controls green, but catalog dual-reviewer "
                "requirement is unmet. SUCCESS not invented."
            ),
            "blocked_on": BLOCKED_ON,
        },
        "report": {
            "kind": "claim-record",
            "schema_status": "PROVISIONAL",
            "superseded_by_unit": "ARC-0085",
            "phase4_formalization_unit": "ARC-0085",
            "provisional_schema_path": (
                "command-center/schema/claim-record.provisional.v1.schema.json"
            ),
            "schedule_claim_recomputed": sched,
            "schedule_after_critical_path": schedule["after"]["critical_path"],
            "cc0012_dependency_state": "SUCCESS",
            "success_invented": False,
            "independent_review_invented": False,
            "dual_reviewers_owed": [
                "cross-vendor-schema-reviewer",
                "independent-1-to-2-soft-rederiver",
            ],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-pending-dual-independent-reviewers",
            "builder": "command-center/p2-wave/probes/CC-0017/_pack_receipt.py",
            "success_invented": False,
            "independent_review_invented": False,
        },
    }
    return receipt


def main() -> int:
    receipt = build()
    # Write manifest before final art measurement of receipt itself.
    manifest = {
        "schema_version": 1,
        "unit_id": UNIT,
        "entry_id": UNIT,
        "state": "BLOCKED",
        "artifacts": [a["path"] for a in receipt["artifacts"]],
        "receipt_path": OUT,
        "success_invented": False,
        "independent_review_invented": False,
        "blocked_on": receipt["failure"]["blocked_on"],
    }
    man_path = L.REPO / MANIFEST
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc != 0:
        return rc
    # Re-measure receipt bytes into a second write so self-artifact hash matches disk.
    receipt["artifacts"] = [
        L.art(OUT, "primary"),
        *[a for a in receipt["artifacts"] if a["path"] != OUT],
    ]
    # Keep first primary schema arts — rebuild list cleanly:
    receipt["artifacts"] = [
        L.art(OUT, "primary"),
        L.art(
            "command-center/schema/claim-record.provisional.v1.schema.json",
            "primary",
        ),
        L.art("command-center/schema/CLAIM-RECORD-PROVISIONAL.md", "supporting"),
        L.art("tools/command-center/claim_record.py", "primary"),
        L.art("tools/command-center/tests/test_claim_record.py", "supporting"),
        L.art("command-center/p2-wave/probes/CC-0017/probe1-claim-record.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/CC-0017/pytest-claim-record.out", "log"),
        L.art("command-center/p2-wave/probes/CC-0017/schedule-recompute.json", "supporting"),
        L.art("command-center/p2-wave/probes/CC-0017/migrated-three.json", "supporting"),
        L.art("command-center/receipts/CC-0012.json", "supporting"),
        L.art(MANIFEST, "supporting"),
    ]
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    print(f"state=BLOCKED success_invented=false blocked_on_set=true rc={rc2}")
    return rc2


if __name__ == "__main__":
    raise SystemExit(main())
