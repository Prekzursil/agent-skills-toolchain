#!/usr/bin/env python3
"""Named probe 2: path-only flagship citation is UNPROVEN, not pass.

Mechanically independent of probe 1 (which deletes the test file). This probe
keeps the test path and strips the run receipt. A gate that still reports
PROVEN/flagship is citing a file without a run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import unproven_experiment  # noqa: E402
from gate import gate  # noqa: E402
from runner import execute_from_estate  # noqa: E402

UNIT = "WFA-0135"
ART = REPO / "command-center/foundry/WFA-0135-quality-tier-evidence-gate-40-flagship-end-to-end-vs.json"
ESTATE = HERE / "estate"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0135" not in json.dumps(doc):
        return fail("sentinel absent")

    live = gate(ESTATE, repo=REPO)
    for row in live["rows"]:
        if row["claimed_tier"] == "flagship" and row["outcome"] == "PROVEN":
            if not row.get("e2e_test") or not row.get("run_id"):
                return fail("proven flagship missing test:line or run_id", row)
            cite = row["e2e_test"]
            path = REPO / cite["path"]
            if not path.is_file():
                return fail("cited e2e test missing on disk", cite)
            lines = path.read_text(encoding="utf-8").splitlines()
            line_no = int(cite["line"])
            if line_no < 1 or line_no > len(lines):
                return fail("cited line out of range", cite)
            if "FLAGSHIP_E2E_ANCHOR" not in lines[line_no - 1]:
                return fail("cited line is not the e2e anchor", {
                    "cite": cite,
                    "text": lines[line_no - 1],
                })
        if row["outcome"] == "UNPROVEN" and row.get("run_id"):
            return fail("UNPROVEN row still has run_id", row)

    remainder = [r for r in live["rows"] if r["claimed_tier"] == "remainder"]
    if len(remainder) != 56:
        return fail("remainder count", len(remainder))
    for row in remainder:
        rem = row.get("remainder_evidence") or {}
        if row["outcome"] == "PROVEN":
            if not all(
                [
                    rem.get("executable"),
                    rem.get("schema_valid"),
                    rem.get("documented"),
                    rem.get("smoke_tested"),
                ]
            ):
                return fail("proven remainder missing a remainder bit", row)

    smoke = execute_from_estate(ESTATE, "BP-0041", kind="smoke")
    if not smoke.get("ok"):
        return fail("live remainder smoke", smoke)

    planted = unproven_experiment(ESTATE)
    if not planted.get("ok"):
        return fail("path-without-run was not UNPROVEN", planted)

    recorded = None
    for t in doc.get("tests") or []:
        if t.get("id") == "path-only-is-unproven":
            recorded = t
            break
    if not recorded or recorded.get("result") != "PASS":
        return fail("artifact missing path-only UNPROVEN PASS", recorded)

    contract = doc.get("contract") or {}
    if contract.get("path_without_run") != "UNPROVEN":
        return fail("contract path_without_run", contract)

    out = {
        "pass": True,
        "probe": "probe2-unproven",
        "unit_id": UNIT,
        "unproven": planted,
        "remainder_proven": live["counts"]["proven_remainder"],
        "live_smoke_run_id": smoke["run_id"],
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"unproven_ok={planted['ok']} {planted['blueprint_id']} "
        f"outcome={planted['after_outcome']}"
    )
    print("SUCCESS:WFA-0135-probe2 path-without-run UNPROVEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
