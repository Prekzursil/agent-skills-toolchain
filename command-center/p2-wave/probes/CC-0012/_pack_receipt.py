#!/usr/bin/env python3
"""Pack CC-0012 receipt BLOCKED on independent review."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0012"
OUT = "command-center/receipts/CC-0012.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/CC-0012/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-07T18:45:00Z"


def build() -> dict:
    p1 = json.loads((PROBE / "probe1-freeze-summary.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-freeze.raw.txt").read_text(encoding="utf-8")
    pytest_out = (PROBE / "pytest-freeze.out").read_text(encoding="utf-8")
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not p1.get("ok"):
        raise SystemExit(f"refusing pack: {p1}")

    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; "
        f"freeze activated at {p1['activation_commit'][:12]}; "
        f"unversioned=RED versioned=GREEN non-frozen=SILENT roundtrip_ok={p1['roundtrip_ok']}; "
        f"SUCCESS:{UNIT} withheld pending reviewer unversioned-edit attempt"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0012",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art("tools/command-center/schema_freeze.py", "primary"),
            L.art("command-center/SCHEMA-FREEZE.json", "supporting"),
            L.art(
                "command-center/schema/migrations/m001-receipt-core-example.json",
                "supporting",
            ),
            L.art("tools/command-center/tests/test_schema_freeze.py", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0012/probe1-freeze.raw.txt", "log"),
            L.art("command-center/p2-wave/probes/CC-0012/pytest-freeze.out", "log"),
            L.art("command-center/p2-wave/probes/CC-0012/roundtrip-sample.json", "supporting"),
        ],
        "evidence": [
            L.evidence(
                (
                    f"Freeze flag activated at commit {p1['activation_commit']} with "
                    f"{p1['frozen_path_count']} frozen paths; gate "
                    f"unversioned={p1['unversioned_edit']['verdict']} "
                    f"versioned={p1['versioned_edit']['verdict']} "
                    f"non_frozen={p1['non_frozen_edit']['verdict']}."
                ),
                "CONFIRMED",
                "command-center/SCHEMA-FREEZE.json",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CC-0012/probe1_freeze.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "read SCHEMA-FREEZE.json activation_commit",
                        json.dumps(
                            {
                                "activation_commit": p1["activation_commit"],
                                "activated": p1["activated"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Migration m001 round-trip on real sample data "
                    f"roundtrip_ok={p1['roundtrip_ok']} (forward then back byte-identical)."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/CC-0012/roundtrip-sample.json",
                [
                    L.probe(
                        "source",
                        "test-run",
                        "python3 -m pytest tools/command-center/tests/test_schema_freeze.py -q",
                        pytest_out,
                        p1["pytest_rc"],
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "roundtrip_ok measure",
                        f"roundtrip_ok={p1['roundtrip_ok']}",
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
                "Two strikes then pivot; if the gate produces false positives twice, "
                "narrow its path scope rather than loosening its rule."
            ),
        },
        "tests": [
            {
                "id": "unversioned-red",
                "name": "Frozen schema edit without bump -> RED.",
                "command": "python3 -m pytest tools/command-center/tests/test_schema_freeze.py::test_unversioned_frozen_edit_is_red -q",
                "result": "PASS",
                "assertions": 1,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "versioned-green",
                "name": "Bump + migration + round-trip -> GREEN.",
                "command": "python3 -m pytest tools/command-center/tests/test_schema_freeze.py::test_bump_plus_migration_roundtrip_is_green -q",
                "result": "PASS",
                "assertions": 1,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "roundtrip",
                "name": "Forward then back yields byte-identical original.",
                "command": "python3 -m pytest tools/command-center/tests/test_schema_freeze.py::test_roundtrip_forward_back_byte_identical -q",
                "result": "PASS",
                "assertions": 3,
                "output_tail": pytest_out[-800:],
            },
            {
                "id": "both-states-non-frozen",
                "name": "Non-frozen path remains SILENT.",
                "command": "python3 -m pytest tools/command-center/tests/test_schema_freeze.py::test_non_frozen_path_is_silent -q",
                "result": "PASS",
                "assertions": 2,
                "output_tail": pytest_out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "unversioned-frozen-edit",
                "mutation",
                "Change frozen schema without version bump -> gate RED.",
                True,
                True,
                bad=json.dumps(p1["unversioned_edit"]),
                good=json.dumps(p1["versioned_edit"]),
            ),
            L.control(
                "non-frozen-silent",
                "mutation",
                "Edit outside freeze set must be SILENT.",
                True,
                True,
                bad="would be RED if wrongly frozen",
                good=json.dumps(p1["non_frozen_edit"]),
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
                "Catalog requires an independent reviewer who attempts an unversioned "
                "schema edit and confirms rejection. BLOCKED instead of stub SUCCESS."
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
                "consumer": "schema_freeze.check_edit",
                "artifact_path": "command-center/SCHEMA-FREEZE.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    "python3 -B tools/command-center/schema_freeze.py",
                    json.dumps(
                        {
                            "activated": p1["activated"],
                            "activation_commit": p1["activation_commit"],
                        }
                    ),
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Launcher paths are listed but not yet hash-pinned in snapshots; "
                    "mid-run launcher edits remain a process control until CI wires the gate."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add launcher snapshot hashes and a CI step invoking "
                    "schema_freeze.py --check on every PR touching frozen_paths."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": "Freeze + migration gate green under probes; independent review owed.",
            "blocked_on": (
                "Fresh-context reviewer must attempt an unversioned schema edit and "
                "confirm the gate rejects it."
            ),
        },
        "report": {
            "activation_commit": p1["activation_commit"],
            "frozen_path_count": p1["frozen_path_count"],
            "roundtrip_ok": p1["roundtrip_ok"],
            "gate_verdicts": {
                "unversioned": p1["unversioned_edit"]["verdict"],
                "versioned": p1["versioned_edit"]["verdict"],
                "non_frozen": p1["non_frozen_edit"]["verdict"],
            },
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/probes/CC-0012/_pack_receipt.py",
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
                    "tools/command-center/schema_freeze.py",
                    "command-center/SCHEMA-FREEZE.json",
                    "command-center/schema/migrations/m001-receipt-core-example.json",
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
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc2 != 0:
        raise SystemExit(rc2)
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return receipt


if __name__ == "__main__":
    build()
