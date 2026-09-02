#!/usr/bin/env python3
"""Probe 1: status machine.

- No mutation record → UNPROVEN, and UNPROVEN is not coverage.
- Mutation that kills the test → PROTECTING, citing diff + failing output.
- Mutation that SURVIVES → HOLE, not a silent downgrade.
- Refuses a PROTECTING claim without a KILLED mutation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))
sys.path.insert(0, str(HERE))

import test_registry_bind as bind  # noqa: E402
import mutate as M  # noqa: E402

ART = REPO / "command-center/receipts/CC-0014.json"
T_PROT = HERE / "fixtures" / "test_protecting.py"
T_EXPL = HERE / "fixtures" / "test_explicit.py"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0014-probe1 {msg}")
    return 1


def receipt_entries(doc: dict) -> list:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rows = doc.get("entries") or report.get("entries") or []
    return [e for e in rows if isinstance(e, dict)]


def main() -> int:
    # --- no mutation → UNPROVEN ---
    unproven = bind.bind_row(
        test_id="test_empty_list_rejected_at_explicit_one",
        claim_id="CL-CC-0014-UNPROVEN-NOT-COVERAGE",
        unit_id="CC-0014",
    )
    if unproven["status"] != "UNPROVEN":
        return fail(f"no-mutation status={unproven['status']}")
    cov_u = bind.coverage_summary([unproven])
    if cov_u["protected_claims"] != 0 or cov_u["protected_percent"] != 0.0:
        return fail(f"UNPROVEN counted as coverage: {cov_u}")
    if cov_u["unproven_counted_as_coverage"] is not False:
        return fail("unproven_counted_as_coverage flag")

    try:
        bind.classify(
            {
                "test_id": "t",
                "claim_id": "c",
                "unit_id": "CC-0014",
                "status": "PROTECTING",
            }
        )
        return fail("forced PROTECTING without mutation was accepted")
    except bind.RegistryContractError as exc:
        forced_ok = "PROTECTING" in str(exc)
    if not forced_ok:
        return fail("forced-PROTECTING error did not name PROTECTING")

    # --- implementer mutation kills the default-exercising test ---
    killed = M.mutate_and_run(
        M.MUT_IMPL_ZERO, T_PROT, "test_default_floor_rejects_below_minimum"
    )
    if killed["outcome"] != "KILLED":
        return fail(f"expected KILLED on default-floor test, got {killed}")
    if "REQUIRED_MIN = 0" not in killed["diff"]:
        return fail("killed diff missing REQUIRED_MIN = 0")
    if not killed["failing_output"]:
        return fail("KILLED record missing failing_output")
    protecting = bind.bind_row(
        test_id="test_default_floor_rejects_below_minimum",
        claim_id="CL-CC-0014-DEFAULT-FLOOR-ENFORCED",
        unit_id="CC-0014",
        mutation={
            "outcome": killed["outcome"],
            "diff": killed["diff"],
            "failing_output": killed["failing_output"],
            "id": "M-IMPL-DEFAULT-ZERO",
        },
    )
    if protecting["status"] != "PROTECTING":
        return fail(f"killed mutation status={protecting['status']}")

    # --- same mutation survives the explicit-only test → HOLE ---
    survived = M.mutate_and_run(
        M.MUT_IMPL_ZERO, T_EXPL, "test_explicit_minimum_ignores_module_default"
    )
    if survived["outcome"] != "SURVIVED":
        return fail(f"expected SURVIVED on explicit test, got {survived}")
    hole = bind.bind_row(
        test_id="test_explicit_minimum_ignores_module_default",
        claim_id="CL-CC-0014-EXPLICIT-ONLY-IS-HOLE",
        unit_id="CC-0014",
        mutation={
            "outcome": survived["outcome"],
            "diff": survived["diff"],
            "failing_output": survived["failing_output"],
            "id": "M-IMPL-DEFAULT-ZERO",
        },
        extra={"status": "UNPROVEN"},
    )
    if hole["status"] != "HOLE":
        return fail(f"SURVIVED silently downgraded to {hole['status']}")

    # --- receipt must exist, be SUCCESS, and cite mutation evidence ---
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CC-0014" not in text:
        return fail("sentinel absent from receipt")
    entries = receipt_entries(doc)
    statuses = {e["test_id"]: e["status"] for e in entries}
    if statuses.get("test_empty_list_rejected_at_explicit_one") != "UNPROVEN":
        return fail("receipt unproven entry wrong")
    if statuses.get("test_default_floor_rejects_below_minimum") != "PROTECTING":
        return fail("receipt protecting entry wrong")
    if statuses.get("test_explicit_minimum_ignores_module_default") != "HOLE":
        return fail("receipt hole entry wrong")
    prot = next(e for e in entries if e["status"] == "PROTECTING")
    mut = prot.get("mutation") or {}
    if mut.get("outcome") != "KILLED" or not mut.get("diff") or not mut.get(
        "failing_output"
    ):
        return fail("PROTECTING entry missing mutation evidence")

    print(
        json.dumps(
            {
                "unproven": unproven["status"],
                "protecting": protecting["status"],
                "hole": hole["status"],
                "killed_exit": killed["exit_code"],
                "survived_exit": survived["exit_code"],
                "unproven_coverage": cov_u["protected_claims"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0014-probe1 status machine UNPROVEN/PROTECTING/HOLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
