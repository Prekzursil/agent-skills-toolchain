#!/usr/bin/env python3
"""CC-0014 probe: run binder tests + live controls; write summaries."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import test_registry_bind as trb  # noqa: E402


def main() -> int:
    PROBE.mkdir(parents=True, exist_ok=True)
    fixtures = PROBE / "fixtures"
    fixtures.mkdir(exist_ok=True)
    (fixtures / "mut.diff").write_text("-CONST=1\n+CONST=0\n", encoding="utf-8")
    (fixtures / "mut-fail.out").write_text(
        "FAILED test_example_can_go_red\nAssertionError\n", encoding="utf-8"
    )
    (fixtures / "survived.diff").write_text("-x=1\n+x=2\n", encoding="utf-8")
    (fixtures / "still-green.out").write_text("1 passed\n", encoding="utf-8")

    tests = REPO / "tools/command-center/tests/test_test_registry_bind.py"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests), "-q", "--tb=line"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    pytest_out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE / "pytest-bind.out").write_text(pytest_out, encoding="utf-8")

    # Live controls against an in-memory registry (does not rewrite TEST-REGISTRY.json
    # narrative suites; bindings live beside them via ensure_bindings_scaffold).
    live = trb.ensure_bindings_scaffold(
        json.loads(
            (REPO / "command-center/TEST-REGISTRY.json").read_text(encoding="utf-8")
        )
    )
    # Control 1: no mutation -> UNPROVEN
    e1 = trb.register_entry(
        live,
        {
            "id": "CTRL-NO-MUT",
            "test_id": "test_ctrl_no_mut",
            "claim_ids": ["CC-2"],
            "unit_ids": ["CC-0014"],
            "mutation_record": None,
        },
    )
    # Control 2: FAILED mutation -> PROTECTING
    e2 = trb.register_entry(
        live,
        {
            "id": "CTRL-KILL",
            "test_id": "test_ctrl_kill",
            "claim_ids": ["CC-2"],
            "unit_ids": ["CC-0014"],
            "mutation_record": {
                "outcome": "FAILED",
                "diff_ref": "command-center/p2-wave/probes/CC-0014/fixtures/mut.diff",
                "failing_output_ref": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/mut-fail.out"
                ),
            },
        },
    )
    # Control 3: SURVIVED -> HOLE
    e3 = trb.register_entry(
        live,
        {
            "id": "CTRL-SURVIVE",
            "test_id": "test_ctrl_survive",
            "claim_ids": ["CC-8"],
            "unit_ids": ["CC-0014"],
            "mutation_record": {
                "outcome": "SURVIVED",
                "diff_ref": "command-center/p2-wave/probes/CC-0014/fixtures/survived.diff",
                "failing_output_ref": (
                    "command-center/p2-wave/probes/CC-0014/fixtures/still-green.out"
                ),
            },
        },
    )
    # Persist the measured binding set used for the probe (not the narrative file).
    bind_path = PROBE / "bindings-measured.json"
    trb.save_registry(live, bind_path)
    summary = trb.coverage_summary(live)

    # Aggregation control: all-UNPROVEN registry reports 0 protected
    all_u = {
        "bindings": [
            trb.normalize_entry(
                {
                    "id": f"U-{i}",
                    "test_id": f"t{i}",
                    "claim_ids": [f"C{i}"],
                    "unit_ids": ["CC-0014"],
                }
            )
            for i in range(4)
        ]
    }
    agg = trb.coverage_summary(all_u)

    result = {
        "probe": "CC-0014-bind",
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pytest_rc": proc.returncode,
        "controls": {
            "no_mutation_status": e1["status"],
            "failed_mutation_status": e2["status"],
            "survived_status": e3["status"],
            "hole_count": summary["hole_count"],
            "protected_claim_count": summary["protected_claim_count"],
            "aggregation_all_unproven_protected": agg["protected_claim_count"],
        },
        "coverage_summary": summary,
        "ok": (
            proc.returncode == 0
            and e1["status"] == "UNPROVEN"
            and e2["status"] == "PROTECTING"
            and e3["status"] == "HOLE"
            and summary["hole_count"] == 1
            and agg["protected_claim_count"] == 0
        ),
    }
    (PROBE / "probe1-bind-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = (
        f"PROBE=CC-0014-bind\n"
        f"PYTEST_RC={proc.returncode}\n"
        f"NO_MUT={e1['status']}\n"
        f"FAILED_MUT={e2['status']}\n"
        f"SURVIVED={e3['status']}\n"
        f"HOLES={summary['hole_count']}\n"
        f"PROTECTED_CLAIMS={summary['protected_claim_count']}\n"
        f"AGG_ALL_UNPROVEN_PROTECTED={agg['protected_claim_count']}\n"
        f"PYTEST_TAIL=\n{pytest_out[-3000:]}\n"
        f"VERDICT={'PASS' if result['ok'] else 'FAIL'}\n"
    )
    (PROBE / "probe1-bind.raw.txt").write_text(raw, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
