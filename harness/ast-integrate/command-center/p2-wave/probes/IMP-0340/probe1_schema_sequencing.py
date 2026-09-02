#!/usr/bin/env python3
"""Named probe 1: plan schema and sequencing (IMP-0340).

Signal 1 is the in-process API (plan_from_decision + validate_plan).
Signal 2 is the CLI validate/plan subcommands on the same fixtures.
Disagreement between the two is a failure, not a picked winner.
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


def cli(args: list[str]) -> tuple[int, dict | None, str]:
    p = subprocess.run(
        CLI + args,
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    text = (p.stdout or "") + (p.stderr or "")
    doc = None
    try:
        doc = json.loads(p.stdout)
    except json.JSONDecodeError:
        pass
    return p.returncode, doc, text


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0340-probe1 {msg}")
    return 1


def main() -> int:
    decision = load("agreed-decision.json")
    plan = ap.plan_from_decision(decision)
    errors = ap.validate_plan(plan)
    if errors:
        return fail(f"generated plan invalid {errors}")

    actions = plan["actions"]
    if len(actions) != 3:
        return fail(f"action_count={len(actions)} want=3 (finding must be omitted)")
    order = [a["traces_to"] for a in actions]
    if order != ["el-prep", "el-build", "el-verify"]:
        return fail(f"sequence order {order} (depends_on not respected)")
    if [a["sequence"] for a in actions] != [1, 2, 3]:
        return fail(f"sequences {[a['sequence'] for a in actions]}")
    kinds = {a["traces_to"]: a["type"] for a in actions}
    if kinds != {"el-prep": "implement", "el-build": "enforce", "el-verify": "experiment"}:
        return fail(f"types {kinds}")
    omitted_ids = {o["element_id"] for o in plan["omitted"]}
    if "el-finding" not in omitted_ids:
        return fail(f"finding not omitted {plan['omitted']}")
    if any(a["traces_to"] == "el-dissent-crypto" for a in actions):
        return fail("dissent leaked into actions")
    if any(a["statement"] == "Also rewrite production cryptography this week." for a in actions):
        return fail("dissent statement leaked into actions")

    # Shuffled input (fixture is already reverse-ish); reverse again and re-plan.
    shuffled = json.loads(json.dumps(decision))
    shuffled["agreed_elements"] = list(reversed(list(shuffled["agreed_elements"])))
    plan2 = ap.plan_from_decision(shuffled)
    order2 = [a["traces_to"] for a in plan2["actions"]]
    if order2 != order:
        return fail(f"shuffle changed order {order2} vs {order}")

    # Missing owner is omitted, not emitted as a schema-invalid action.
    unowned = ap.plan_from_decision(load("missing-owner.json"))
    if [a["traces_to"] for a in unowned["actions"]] != ["el-owned"]:
        return fail(f"missing-owner plan {unowned}")
    if not any(o["element_id"] == "el-unowned" and o["reason"] == "missing_owner" for o in unowned["omitted"]):
        return fail(f"unowned not listed omitted {unowned['omitted']}")
    if ap.validate_plan(unowned):
        return fail(f"unowned-omitted plan still invalid {ap.validate_plan(unowned)}")

    # NO-DECISION must not plan the commitment.
    none = ap.plan_from_decision(load("no-decision.json"))
    if none["actions"]:
        return fail(f"NO-DECISION produced actions {none['actions']}")

    # CONDITIONAL copies the condition onto the precondition.
    cond = ap.plan_from_decision(load("conditional-decision.json"))
    if len(cond["actions"]) != 1 or cond["actions"][0]["type"] != "mitigate":
        return fail(f"conditional plan {cond}")
    pre = cond["actions"][0]["precondition"]
    if "owner-approval recorded for budget ceiling" not in (pre.get("conditions") or []):
        return fail(f"conditional precondition missing condition {pre}")
    if ap.validate_plan(cond):
        return fail(f"conditional plan invalid {ap.validate_plan(cond)}")

    # Per-action schema: strip required fields from a generated action.
    for field in ("owner", "precondition", "verification"):
        bad = json.loads(json.dumps(actions[0]))
        bad.pop(field, None)
        verr = ap.validate_action(bad)
        if not verr:
            return fail(f"validate_action silent after dropping {field}")

    empty_owner = json.loads(json.dumps(actions[0]))
    empty_owner["owner"] = "   "
    if not ap.validate_action(empty_owner):
        return fail("empty owner accepted")

    # Sequencing: reverse list order, keep sequence numbers → must fail.
    reversed_plan = json.loads(json.dumps(plan))
    reversed_plan["actions"] = list(reversed(reversed_plan["actions"]))
    seq_err = ap.validate_plan(reversed_plan)
    if not any("not ordered by sequence" in e for e in seq_err):
        return fail(f"reversed list did not fail sequencing {seq_err}")

    # Cyclic depends_on must raise, not silently drop.
    cyclic = json.loads(json.dumps(decision))
    for el in cyclic["agreed_elements"]:
        if el.get("element_id") == "el-prep":
            el["precondition"] = {"type": "depends_on", "element_ids": ["el-verify"]}
            el["kind"] = "commitment"
    try:
        ap.plan_from_decision(cyclic)
        return fail("cyclic depends_on did not raise")
    except ap.PlanError as exc:
        if "cyclic" not in str(exc):
            return fail(f"cyclic error mismatch {exc}")

    # Signal 2: CLI plan + validate on the same fixture.
    rc_plan, cli_plan, tail = cli(["plan", str(FIX / "agreed-decision.json")])
    if rc_plan != 0 or not isinstance(cli_plan, dict):
        return fail(f"cli plan rc={rc_plan} {tail[-500:]}")
    if [a["traces_to"] for a in cli_plan.get("actions") or []] != order:
        return fail(f"cli plan order diverged from API {[a.get('traces_to') for a in cli_plan.get('actions') or []]}")
    tmp = HERE / ".probe1-plan.json"
    tmp.write_text(json.dumps(plan), encoding="utf-8")
    try:
        rc_val, cli_val, tail_v = cli(["validate", str(tmp)])
    finally:
        tmp.unlink(missing_ok=True)
    if rc_val != 0 or not (isinstance(cli_val, dict) and cli_val.get("ok") is True):
        return fail(f"cli validate rc={rc_val} {cli_val} {tail_v[-400:]}")

    report = {
        "probe": "probe1-schema-sequencing",
        "unit_id": "IMP-0340",
        "action_count": len(actions),
        "order": order,
        "omitted": plan["omitted"],
        "schema_errors_on_generated": errors,
        "shuffle_stable": True,
        "missing_owner_omitted": True,
        "no_decision_empty": True,
        "conditional_condition_copied": True,
        "field_drop_fires": ["owner", "precondition", "verification"],
        "cli_plan_matches_api": True,
        "cli_validate_ok": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "order="
        + ",".join(order)
        + " omitted_finding=True dissent_leaked=False "
        + "schema_ok=True shuffle_stable=True"
    )
    print("SUCCESS:IMP-0340-probe1 plan schema and sequencing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
