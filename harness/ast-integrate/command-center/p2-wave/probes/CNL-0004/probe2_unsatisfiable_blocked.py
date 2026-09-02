#!/usr/bin/env python3
"""Probe 2: unsatisfiable constraints BLOCK; agree-state is a silent negative.

Catalog tests_required[1]: a constraint that cannot be satisfied yields BLOCKED,
never a quiet relaxation (no final_choice, mandatory human not dropped).
Catalog tests_required[2]: negative control recorded verbatim — the agree
fixture (ceiling above auto spend, unused forbidden class) is COMPOSED with
an empty override_log.

Also re-checks the design artifact: sentinel, precedence claim, and live
engine fingerprints matching the embedded worked instances.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import composer as C  # noqa: E402
import fixtures as F  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0004-owner-constraint-block-and-its-precedence-over-auto-compos.md"
)
OUT = HERE / "probe2-unsatisfiable.raw.json"
SENTINEL = "SUCCESS:CNL-0004"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0004-probe2 {msg}")
    return 1


def main() -> int:
    unsat = C.apply_owner_constraints(F.TASK_UNSAT, F.CONSTRAINTS_UNSAT)
    unsat_errs = C.validate_instance(unsat, "composition_result")
    if unsat_errs:
        print("\n".join(unsat_errs[:8]))
        return fail("unsat result schema errors")
    if unsat["status"] != "BLOCKED":
        return fail(f"expected BLOCKED, got {unsat['status']}")
    if unsat["final_choice"] is not None:
        return fail("BLOCKED result leaked a final_choice")
    blocked = unsat["blocked"] or {}
    if "OC-BUDGET-TIGHT" not in blocked.get("unsatisfied_constraint_ids", []):
        return fail("BLOCKED did not name OC-BUDGET-TIGHT")
    if "mandatory human" not in blocked.get("reason", "").lower() and "human" not in (
        blocked.get("reason") or ""
    ).lower():
        return fail("BLOCKED reason does not mention the human/ceiling clash")

    planted = C.plant_quiet_relaxation(unsat, unsat["auto_choice"])
    planted_unsat = C._unsatisfied(planted["final_choice"], F.CONSTRAINTS_UNSAT)
    if planted["status"] != "COMPOSED" or not planted_unsat:
        return fail("quiet-relaxation plant is not actually unsatisfied")
    if unsat["status"] == "COMPOSED":
        return fail("live unsat quietly composed")

    agree = C.apply_owner_constraints(F.TASK_AGREE, F.CONSTRAINTS_AGREE)
    if agree["status"] != "COMPOSED":
        return fail(f"agree fixture not COMPOSED: {agree['status']}")
    if agree["override_log"]:
        return fail("agree fixture emitted override_log (negative control broken)")
    if C.choice_fingerprint(agree["auto_choice"]) != C.choice_fingerprint(
        agree["final_choice"]
    ):
        return fail("agree fixture mutated the roster")
    if C.silent_win(
        agree["auto_choice"], agree["final_choice"], agree["override_log"]
    ):
        return fail("agree fixture flagged silent-win")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("design artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent from artifact")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    rule = str(doc.get("precedence_rule") or "")
    if "hard-win" not in rule.lower() and "hard wins" not in rule.lower():
        return fail("artifact missing owner hard-win precedence")
    if "override" not in rule.lower():
        return fail("artifact precedence does not mention visible override")

    live_conflict = C.apply_owner_constraints(F.TASK_CONFLICT, F.CONSTRAINTS_CONFLICT)
    embedded = (doc.get("worked_conflict") or {}).get("live_result") or {}
    if not embedded:
        return fail("artifact missing worked_conflict.live_result")
    if C.choice_fingerprint(embedded.get("final_choice")) != C.choice_fingerprint(
        live_conflict["final_choice"]
    ):
        return fail("artifact conflict roster drifted from live engine")
    if {e["constraint_id"] for e in embedded.get("override_log") or []} != {
        e["constraint_id"] for e in live_conflict["override_log"]
    }:
        return fail("artifact override ids drifted from live engine")

    embedded_unsat = (doc.get("unsatisfiable_instance") or {}).get("live_result") or {}
    if embedded_unsat.get("status") != "BLOCKED":
        return fail("artifact unsatisfiable_instance is not BLOCKED")

    payload = {
        "probe": "probe2-unsatisfiable-blocked",
        "unit_id": "CNL-0004",
        "unsat_status": unsat["status"],
        "unsat_final_choice_is_null": unsat["final_choice"] is None,
        "unsat_named_constraints": blocked.get("unsatisfied_constraint_ids"),
        "quiet_relaxation_plant_would_compose": planted["status"] == "COMPOSED",
        "quiet_relaxation_plant_unsatisfied": planted_unsat,
        "agree_status": agree["status"],
        "agree_override_count": len(agree["override_log"]),
        "agree_roster_identical": True,
        "artifact_sentinel": SENTINEL in text,
        "artifact_matches_live_conflict": True,
        "negative_control": (
            "On CONSTRAINTS_AGREE (ceiling 100 USD, forbidden unlicensed-crawl "
            "which auto never uses, no mandatory human) the applicator is "
            "SILENT: status=COMPOSED, override_log=[], auto_choice fingerprint "
            "equals final_choice. The check is meant to reject a mutation "
            "that is not recorded; this state has no mutation, so the check "
            "must not fire."
        ),
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:CNL-0004-probe2 unsatisfiable BLOCKED; agree-state silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
