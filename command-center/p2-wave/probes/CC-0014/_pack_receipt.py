#!/usr/bin/env python3
"""Pack CC-0014 as test-registry-entry receipt, state=BLOCKED."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0014"
OUT = "command-center/receipts/CC-0014.json"
SCHEMA = "command-center/schema/test-registry-entry.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/CC-0014/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-07T18:40:00Z"


def build() -> dict:
    p1 = json.loads((PROBE / "probe1-bind-summary.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-bind.raw.txt").read_text(encoding="utf-8")
    pytest_out = (PROBE / "pytest-bind.out").read_text(encoding="utf-8")
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not p1.get("ok"):
        raise SystemExit(f"refusing pack: {p1}")

    ctrl = p1["controls"]
    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; "
        f"binder assigns UNPROVEN/PROTECTING/HOLE; "
        f"aggregation all-UNPROVEN protected={ctrl['aggregation_all_unproven_protected']}; "
        f"SUCCESS:{UNIT} withheld pending independent mutation review"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0014",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art("tools/command-center/test_registry_bind.py", "primary"),
            L.art("tools/command-center/tests/test_test_registry_bind.py", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0014/bindings-measured.json", "supporting"),
            L.art("command-center/TEST-REGISTRY.json", "supporting"),
            L.art("command-center/CLAIM-REGISTRY.json", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0014/probe1-bind.raw.txt", "log"),
            L.art("command-center/p2-wave/probes/CC-0014/pytest-bind.out", "log"),
        ],
        "evidence": [
            L.evidence(
                (
                    f"Binder controls: no-mutation→{ctrl['no_mutation_status']}, "
                    f"FAILED-mutation→{ctrl['failed_mutation_status']}, "
                    f"SURVIVED→{ctrl['survived_status']} hole_count={ctrl['hole_count']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/CC-0014/probe1-bind.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CC-0014/probe1_bind.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "read probe1-bind-summary.json",
                        json.dumps(ctrl, sort_keys=True),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Aggregation control: all-UNPROVEN registry reports "
                    f"protected_claim_count={ctrl['aggregation_all_unproven_protected']} "
                    "(never 100%)."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/CC-0014/probe1-bind-summary.json",
                [
                    L.probe(
                        "source",
                        "test-run",
                        "python3 -m pytest tools/command-center/tests/test_test_registry_bind.py -q",
                        pytest_out,
                        p1["pytest_rc"],
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "coverage_summary all-UNPROVEN",
                        f"protected={ctrl['aggregation_all_unproven_protected']}",
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "Two strikes then pivot; never relax the mutation requirement.",
        },
        "tests": [
            {
                "id": "unproven-without-mutation",
                "name": "No mutation_record => UNPROVEN; not coverage.",
                "command": "python3 -m pytest tools/command-center/tests/test_test_registry_bind.py::test_no_mutation_is_unproven_and_not_coverage -q",
                "result": "PASS",
                "assertions": 3,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "protecting-on-failed-mutation",
                "name": "FAILED mutation with evidence refs => PROTECTING.",
                "command": "python3 -m pytest tools/command-center/tests/test_test_registry_bind.py::test_mutation_failed_is_protecting -q",
                "result": "PASS",
                "assertions": 2,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "survived-is-hole",
                "name": "SURVIVED mutation surfaces HOLE, not silent downgrade.",
                "command": "python3 -m pytest tools/command-center/tests/test_test_registry_bind.py::test_survived_mutation_is_hole_not_silent_downgrade -q",
                "result": "PASS",
                "assertions": 3,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "aggregation-zero",
                "name": "All-UNPROVEN coverage summary reports 0 protected claims.",
                "command": "python3 -m pytest tools/command-center/tests/test_test_registry_bind.py::test_aggregation_all_unproven_reports_zero_protected -q",
                "result": "PASS",
                "assertions": 4,
                "output_tail": pytest_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "no-mutation-unproven",
                "mutation",
                "Register without mutation_record must be UNPROVEN.",
                True,
                True,
                bad="status=UNPROVEN protected=0",
                good="PROTECTING only after FAILED mutation with refs",
            ),
            L.control(
                "survived-hole",
                "mutation",
                "SURVIVED mutation must surface a hole.",
                True,
                True,
                bad="status=HOLE hole_count>=1",
                good="no hole when outcome=FAILED",
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-fresh-context",
            "verdict": "FAIL",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Catalog requires an independent reviewer who authors a mutation the "
                "implementer did not write. BLOCKED instead of stub SUCCESS."
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
                "consumer": "test_registry_bind.coverage_summary",
                "artifact_path": "command-center/p2-wave/probes/CC-0014/bindings-measured.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    "python3 -B tools/command-center/test_registry_bind.py --summary",
                    json.dumps(p1["coverage_summary"], sort_keys=True)[:2000],
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Live TEST-REGISTRY.json narrative suites are not yet fully rewritten "
                    "as bindings with mutation_records for every named test."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Migrate each suite/invariant row into bindings with recorded mutations; "
                    "re-run coverage_summary and require protecting_only_counts."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": "Binder + both-states tests green; independent mutation review owed.",
            "blocked_on": (
                "Fresh-context reviewer must author an independent mutation and confirm "
                "PROTECTING/HOLE classification."
            ),
        },
        "report": {
            "kind": "test-registry-entry",
            "observations": [
                {
                    "name": "no_mutation_status",
                    "measured": ctrl["no_mutation_status"],
                    "method": "test_registry_bind.normalize_entry",
                    "anchor": "command-center/p2-wave/probes/CC-0014/probe1-bind.raw.txt",
                },
                {
                    "name": "failed_mutation_status",
                    "measured": ctrl["failed_mutation_status"],
                    "method": "test_registry_bind.normalize_entry",
                    "anchor": "command-center/p2-wave/probes/CC-0014/probe1-bind.raw.txt",
                },
                {
                    "name": "survived_hole_count",
                    "measured": ctrl["hole_count"],
                    "method": "test_registry_bind.coverage_summary",
                    "anchor": "command-center/p2-wave/probes/CC-0014/probe1-bind-summary.json",
                },
                {
                    "name": "aggregation_all_unproven_protected_claims",
                    "measured": ctrl["aggregation_all_unproven_protected"],
                    "method": "coverage_summary on all-UNPROVEN bindings",
                    "anchor": "command-center/p2-wave/probes/CC-0014/probe1-bind-summary.json",
                },
            ],
            "control_ids": ["no-mutation-unproven", "survived-hole"],
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/probes/CC-0014/_pack_receipt.py",
            "anti_false_green": "BLOCKED-with-real-probes",
        },
    }

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": [
                    OUT,
                    "tools/command-center/test_registry_bind.py",
                    "tools/command-center/tests/test_test_registry_bind.py",
                ],
                "state": "BLOCKED",
                "registered_at": ended,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    rc = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc != 0:
        raise SystemExit(rc)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    # Re-validate after primary artifact refresh
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc2 != 0:
        raise SystemExit(rc2)
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return receipt


if __name__ == "__main__":
    build()
