#!/usr/bin/env python3
"""Named probe 2: inject an unagreed action and assert traceability FIRES.

This probe starts from the tests, not from an author's summary: the generator
is guilty if (a) a clean plan is flagged or (b) an injected unagreed action
is silent. Both-states is required.

Signal 1: in-process traceability_check.
Signal 2: CLI `check` exit code (0 clean, 1 injected).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MOD = REPO / "tools" / "council" / "outcomes"
sys.path.insert(0, str(MOD))

import action_plan as ap  # noqa: E402

FIX = HERE / "fixtures"
CLI = [
    sys.executable,
    "-B",
    str(REPO / "tools/council/outcomes/action_plan.py"),
]


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def cli_check(plan_path: Path, decision_path: Path) -> int:
    p = subprocess.run(
        CLI + ["check", str(plan_path), str(decision_path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    return p.returncode


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0340-probe2 {msg}")
    return 1


def write_tmp(name: str, doc: dict) -> Path:
    path = HERE / name
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    decision = load("agreed-decision.json")
    plan = ap.plan_from_decision(decision)

    clean = ap.traceability_check(plan, decision)
    if clean["fired"] or clean["untraceable"]:
        return fail(f"clean plan fired {clean}")
    if clean["traceable_count"] != clean["action_count"] or clean["action_count"] != 3:
        return fail(f"clean counts {clean}")

    # Independent recount: every traces_to is in agreed_elements, none in dissent.
    agreed = ap.agreed_id_set(decision)
    dissent_only = ap.dissent_id_set(decision) - agreed
    traces = {a["traces_to"] for a in plan["actions"]}
    if traces - agreed:
        return fail(f"independent recount extra {traces - agreed}")
    if traces & dissent_only:
        return fail(f"independent recount dissent {traces & dissent_only}")

    injected = ap.inject_unagreed_action(plan)
    dirty = ap.traceability_check(injected, decision)
    if not dirty["fired"]:
        return fail("injected unagreed action did not fire")
    reasons = {row["action_id"]: row["reason"] for row in dirty["untraceable"]}
    if reasons.get("act-injected-unagreed") != "not_in_agreed_set":
        return fail(f"injected reason {reasons}")
    listed = [row["action_id"] for row in dirty["untraceable"]]
    if "act-injected-unagreed" not in listed:
        return fail(f"injected id not listed {dirty['untraceable']}")
    # Generator itself must not have emitted the injected action.
    if any(a["action_id"] == "act-injected-unagreed" for a in plan["actions"]):
        return fail("generator emitted the injected action")

    smuggled = ap.inject_statement_mismatch(plan)
    sm = ap.traceability_check(smuggled, decision)
    if not sm["fired"]:
        return fail("statement mismatch did not fire")
    if not any(row["reason"] == "statement_mismatch" for row in sm["untraceable"]):
        return fail(f"mismatch reasons {sm['untraceable']}")

    # Point traces_to at the dissent-only id.
    dissent_plan = json.loads(json.dumps(plan))
    dissent_plan["actions"][0]["traces_to"] = "el-dissent-crypto"
    dissent_plan["actions"][0]["statement"] = "Also rewrite production cryptography this week."
    drep = ap.traceability_check(dissent_plan, decision)
    if not drep["fired"] or not any(r["reason"] == "traces_to_dissent" for r in drep["untraceable"]):
        return fail(f"dissent traces_to silent {drep}")

    # Both-states via CLI exit codes (signal 2).
    clean_path = write_tmp(".probe2-clean.json", plan)
    dirty_path = write_tmp(".probe2-dirty.json", injected)
    decision_path = FIX / "agreed-decision.json"
    try:
        rc_clean = cli_check(clean_path, decision_path)
        rc_dirty = cli_check(dirty_path, decision_path)
    finally:
        clean_path.unlink(missing_ok=True)
        dirty_path.unlink(missing_ok=True)
    if rc_clean != 0:
        return fail(f"cli check fired on clean rc={rc_clean}")
    if rc_dirty != 1:
        return fail(f"cli check silent on injected rc={rc_dirty}")

    report = {
        "probe": "probe2-unagreed-traceability",
        "unit_id": "IMP-0340",
        "clean_fired": clean["fired"],
        "clean_untraceable": clean["untraceable"],
        "injected_fired": dirty["fired"],
        "injected_untraceable": dirty["untraceable"],
        "mismatch_fired": sm["fired"],
        "dissent_fired": drep["fired"],
        "cli_clean_rc": rc_clean,
        "cli_dirty_rc": rc_dirty,
        "untraceable_listed_explicitly": listed,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "clean_fired=False injected_fired=True "
        "mismatch_fired=True dissent_fired=True "
        f"listed={listed}"
    )
    print("SUCCESS:IMP-0340-probe2 unagreed-action traceability FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
