#!/usr/bin/env python3
"""Probe 1: every claimed validate.py rule is FIRED or DISARMED under the CI argv.

Re-runs the mutation battery live. A rule silent under the bare CI invocation
must be labelled DISARMED with --require-complete. Does not implement the
independent armed-delta recount (probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0076.json"
OUT = HERE / "probe1-ci-invocation.raw.json"
SENTINEL = "SUCCESS:TST-0076"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0076-probe1 {msg}")
    return 1


def main() -> int:
    report = B.run_report()
    errors = B.table_is_sound(report)
    if errors:
        print(json.dumps({"errors": errors}, indent=2))
        return fail("; ".join(errors[:4]))

    rows = report["rows"]
    fired = [r for r in rows if r["status"] == "FIRED"]
    disarmed = [r for r in rows if r["status"] == "DISARMED"]
    vfields = [r for r in rows if r["check"] == "V-FIELDS"]
    if len(fired) < 8:
        return fail(f"too few FIRED rows: {len(fired)}")
    if not vfields:
        return fail("V-FIELDS missing from table")
    if any(r["status"] not in {"FIRED", "DISARMED"} for r in vfields):
        return fail("V-FIELDS not classified")
    for row in disarmed:
        if row.get("arming_flag") != B.ARMING_FLAG:
            return fail(f"{row['id']} DISARMED without {B.ARMING_FLAG}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    art_rows = {
        r.get("id"): r
        for r in B.artifact_mutation_table(doc)
        if isinstance(r, dict)
    }
    if len(art_rows) != len(rows):
        return fail(f"artifact rows={len(art_rows)} live={len(rows)}")
    for row in rows:
        art = art_rows.get(row["id"]) or {}
        if art.get("status") != row["status"]:
            return fail(
                f"{row['id']} artifact status={art.get('status')} live={row['status']}"
            )
        if art.get("ci_exit") != row["ci_exit"]:
            return fail(f"{row['id']} ci_exit artifact={art.get('ci_exit')} live={row['ci_exit']}")

    dd = report["defaults_deleted"]
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    every = tests.get("test_every_validator_rule_fires_under_the_ci_invocation") or {}
    if every.get("result") != "PASS":
        return fail("artifact did not PASS the every-rule survey")
    red = tests.get("test_deleting_the_defaults_block_turns_ci_red") or {}
    if red.get("result") != "PASS":
        return fail(
            f"defaults-turns-ci-red result={red.get('result')} want=PASS "
            "(measurement must run; subject status lives in mutation_table)"
        )
    tail = str(red.get("output_tail") or "")
    if dd["status"] not in tail or str(dd["ci_exit"]) not in tail:
        return fail(
            f"defaults-turns-ci-red output_tail missing live "
            f"status={dd['status']} ci_exit={dd['ci_exit']}"
        )

    raw = {
        "probe": "probe1-ci-invocation",
        "unit_id": "TST-0076",
        "claimed_checks": report["claimed_checks"],
        "n_fired": len(fired),
        "n_disarmed": len(disarmed),
        "defaults_status": dd["status"],
        "defaults_ci_exit": dd["ci_exit"],
        "defaults_armed_exit": dd["armed_exit"],
        "baseline_silent": report["baseline"]["silent_on_good_state"],
        "pass": True,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired={len(fired)} disarmed={len(disarmed)} "
        f"defaults={dd['status']} ci_exit={dd['ci_exit']} "
        f"armed_exit={dd['armed_exit']} baseline_silent=True"
    )
    print("SUCCESS:TST-0076-probe1 every claimed rule FIRED or DISARMED under CI argv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
