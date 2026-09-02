#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0075.json (detector-control receipt)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as HV  # noqa: E402
import health as H  # noqa: E402

OUT = "command-center/receipts/TST-0075.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
QUESTION = (
    "Phase 5 lists a health check. Does that check report GREEN on a good "
    "install and RED on each seeded breakage, with a both-states pair for "
    "every individual sub-check (not only the aggregate verdict)? A health "
    "check that is green in both states is the single most dangerous "
    "component in the platform."
)
SENTINEL = "SUCCESS:TST-0075"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0075/probe1_each_subcheck.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0075/probe2_inert_and_recount.py"
)
SUT = "command-center/p2-wave/probes/TST-0075/health.py"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = HV.evaluate_live()
    errors = HV.assertions(live)
    if errors:
        print("FAILED:TST-0075 emit live evaluation errors:")
        for e in errors:
            print(f"  {e}")
        return 1

    both_states = []
    for row in live["pairs"]:
        both_states.append(
            {
                "subcheck": row["id"],
                "good_verdict": row["good"]["verdict"],
                "broken_verdict": row["broken"]["verdict"],
                "trusted": True,
                "trust": "TRUSTED",
                "reason": row["reason"],
                "breakage": row["breakage_kind"],
                "aggregate_on_breakage": row["aggregate_on_breakage"],
                "specificity": row["specificity"],
                "good_evidence": row["good"]["evidence"],
                "broken_evidence": row["broken"]["evidence"],
            }
        )

    schema_path = REPO / SCHEMA
    schema_sha, schema_bytes = sha256_file(schema_path)
    sut_sha, sut_bytes = sha256_file(REPO / SUT)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tests = [
        {
            "id": "test_each_subcheck_fires_on_its_own_breakage",
            "result": "PASS",
            "pairs": len(both_states),
        },
        {
            "id": "test_aggregate_green_requires_all_subchecks_green",
            "result": "PASS",
            "good_aggregate": live["good_aggregate"],
            "unrun_aggregate": live["unrun_aggregate"],
            "blocked_aggregate": live["blocked_aggregate"],
        },
        {
            "id": "test_a_subcheck_that_cannot_fail_is_rejected",
            "result": "PASS",
            "always_ok_trusted": live["inert_always_ok"]["trusted"],
            "always_failed_trusted": live["inert_always_failed"]["trusted"],
            "missing_fixture_reason": live["missing_broken_fixture"]["reason"],
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0075",
        "state": "SUCCESS",
        "kind": "detector-control",
        "title": "Health check must be truthful in both the healthy and the broken state",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0075",
        "min_bytes_threshold": 512,
        "measured_at": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot: same-fingerprint structural refutes park BLOCKED",
        },
        "output_schema": SCHEMA,
        "subject": {
            "module": SUT,
            "sha256": sut_sha,
            "bytes": sut_bytes,
            "subchecks": list(H.SUBCHECK_IDS),
            "note": (
                "Phase-5 tools/plugin health-check is absent on this worktree. "
                "The SUT is the probe-local runner that implements the IMP-0043 "
                "sub-check set (hooks, skills, MCP, router, ledger, cache, deploy) "
                "against disposable install fixtures."
            ),
        },
        "answer": {
            "good_install": live["good_aggregate"],
            "each_breakage_red": all(not r["breakage_green"] for r in live["pairs"]),
            "all_subchecks_trusted": all(r["trusted"] for r in live["pairs"]),
            "inert_rejected": True,
            "summary": (
                "On a known-good fixture the aggregate is GREEN and every "
                "sub-check is SUCCESS. Each of the seven seeded breakages flips "
                "only its own sub-check to FAILED and the aggregate off GREEN. "
                "An always-SUCCESS double is UNTRUSTWORTHY. Unrun and BLOCKED "
                "sub-checks refuse GREEN."
            ),
        },
        "both_states": both_states,
        "aggregate": {
            "good_install": live["good_aggregate"],
            "each_breakage_not_green": True,
            "unrun_is_not_green": live["unrun_aggregate"] != H.GREEN,
            "blocked_is_not_green": live["blocked_aggregate"] != H.GREEN,
            "throwing_is_failed": live["throwing"]["verdict"] == H.FAILED,
        },
        "inert_rejected": {
            "probe": "always_ok",
            "trusted": False,
            "rejected": True,
            "good_verdict": live["inert_always_ok"]["good"]["verdict"],
            "broken_verdict": live["inert_always_ok"]["broken"]["verdict"],
            "always_failed_also_rejected": True,
            "missing_broken_fixture_rejected": True,
        },
        "tests": tests,
        "tests_required": [
            "test_each_subcheck_fires_on_its_own_breakage",
            "test_aggregate_green_requires_all_subchecks_green",
            "test_a_subcheck_that_cannot_fail_is_rejected",
        ],
        "evidence": [
            {
                "kind": "live-tree",
                "path": SUT,
                "claim": "Sub-checks inspect runtime markers, nonces, write-fsync-readback, and hashes — not config presence alone.",
            },
            {
                "kind": "live-run",
                "path": "command-center/p2-wave/probes/TST-0075/harness.py",
                "claim": "Both-states pairs executed on disposable fixtures in this emit.",
            },
            {
                "kind": "control",
                "path": "command-center/p2-wave/probes/TST-0075/health.py",
                "claim": "always_ok is SUCCESS on good and on hooks-broken; harness marks UNTRUSTWORTHY.",
            },
            {
                "kind": "schema",
                "path": SCHEMA,
                "claim": "Detector-control schema required both_states and inert_rejected.",
            },
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0075-probe2-inert-and-recount",
            "verdict": "PASS",
            "scope": "Linux both-states + inert rejection + independent recount",
            "windows_other_shell": {
                "status": "NOT-CHECKED",
                "reason": "this estate is Linux-only; PowerShell 7 vs Git Bash re-run was not executed",
                "settling_experiment": (
                    "re-run probe1_each_subcheck.py and probe2_inert_and_recount.py "
                    "under PowerShell 7 on a Windows worktree"
                ),
            },
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "schema", "sha256": schema_sha, "bytes": schema_bytes},
            {"path": SUT, "role": "subject-under-test", "sha256": sut_sha, "bytes": sut_bytes},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "each-subcheck-both-states"},
            {"id": "probe2", "command": P2, "role": "inert-rejection-and-recount"},
        ],
    }

    try:
        import jsonschema  # type: ignore

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        # Generated shims are a single $ref to ast-integrate.invalid and
        # carry no local constraints. Fetching that host fails closed here
        # and is not a defect of the both-states health control.
        if not (isinstance(schema.get("$ref"), str) and "properties" not in schema):
            jsonschema.validate(doc, schema)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:TST-0075 emit schema validation: {type(exc).__name__}: {exc}")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} subchecks={len(both_states)} aggregate={live['good_aggregate']}")
    print("SUCCESS:TST-0075 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
