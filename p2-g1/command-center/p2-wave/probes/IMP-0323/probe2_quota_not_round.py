#!/usr/bin/env python3
"""Probe 2: the distinction is quota attainment, not round count.

Mechanically independent of probe 1 (which checks FPR and the 20-run table).
This probe (1) AST-checks that detect()/_fire_decision do not read round
index, label, or question class for the verdict, (2) compares a round-count
mutant on the same fixtures, (3) perturbs round_index vs quota attainment.
"""
from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.antifail.premature import detect  # noqa: E402
import fixtures as F  # noqa: E402

RAW = HERE / "probe2-quota-not-round.raw.json"
SRC = REPO / "tools" / "council" / "antifail" / "premature.py"
FORBIDDEN_NAMES = frozenset(
    {"round_index", "label", "question_class", "question", "difficulty"}
)


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0323-probe2 {msg}")
    return 1


def round_count_mutant(run: dict) -> bool:
    """Known-wrong rule: flag any convergence at round <= 1."""
    return bool(run.get("converged")) and int(run.get("round_index") or 0) <= 1


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def names_in(fn: ast.FunctionDef) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_NAMES:
                found.add(node.value)
    return found


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fire_fn = _fn(tree, "_fire_decision")
    detect_fn = _fn(tree, "detect")
    if fire_fn is None or detect_fn is None:
        return _fail("detect/_fire_decision missing from premature.py")

    fire_args = [a.arg for a in fire_fn.args.args] + [
        a.arg for a in fire_fn.args.kwonlyargs
    ]
    if "round_index" in fire_args or any(a in FORBIDDEN_NAMES for a in fire_args):
        return _fail(f"_fire_decision args include a forbidden name: {fire_args}")
    required = {"converged", "ideas_met", "objections_met"}
    if not required.issubset(set(fire_args)):
        return _fail(f"_fire_decision args {fire_args} missing {required}")

    fire_names = names_in(fire_fn)
    if fire_names & FORBIDDEN_NAMES:
        return _fail(f"_fire_decision references {fire_names & FORBIDDEN_NAMES}")

    # detect() may copy round_index onto the report via quota_snapshot, but
    # the fired assignment must go through _fire_decision.
    called = {
        node.func.id
        for node in ast.walk(detect_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if "_fire_decision" not in called:
        return _fail("detect() does not call _fire_decision")

    assigned_fired = []
    for node in ast.walk(detect_fn):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "fired" in targets:
                assigned_fired.append(node)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "fired":
                assigned_fired.append(node)
    if not assigned_fired:
        return _fail("detect() never assigns fired")
    for node in assigned_fired:
        value = node.value if isinstance(node, ast.AnnAssign) else node.value
        rhs_names = set()
        if value is not None:
            for child in ast.walk(value):
                if isinstance(child, ast.Name):
                    rhs_names.add(child.id)
                elif isinstance(child, ast.Attribute):
                    rhs_names.add(child.attr)
        if rhs_names & FORBIDDEN_NAMES:
            return _fail(f"fired assigned from forbidden names {rhs_names}")
        if "_fire_decision" not in rhs_names:
            return _fail(f"fired not assigned from _fire_decision: {rhs_names}")

    easy = F.easy_control_set()[0]
    hard_early = F.hard_round1()
    hard_late_unmet = next(r for r in F.twenty_runs() if r["id"] == "hard-late-unmet-1")
    hard_late_ok = next(r for r in F.twenty_runs() if r["id"] == "hard-ok-1")

    matrix = []
    for name, run in (
        ("easy-round1-quotas-met", easy),
        ("hard-round1-quotas-unmet", hard_early),
        ("hard-late-quotas-unmet", hard_late_unmet),
        ("hard-late-quotas-met", hard_late_ok),
    ):
        quota_fired = bool(detect(run)["fired"])
        round_fired = bool(round_count_mutant(run))
        matrix.append(
            {
                "case": name,
                "id": run["id"],
                "round_index": run["round_index"],
                "quota_fired": quota_fired,
                "round_mutant_fired": round_fired,
            }
        )
        print(
            f"{name} round={run['round_index']} quota_fired={quota_fired} "
            f"round_mutant_fired={round_fired}"
        )

    by = {row["case"]: row for row in matrix}
    if by["easy-round1-quotas-met"]["quota_fired"]:
        return _fail("quota detector flagged easy round-1")
    if not by["easy-round1-quotas-met"]["round_mutant_fired"]:
        return _fail("round-count mutant did not FP on easy round-1")
    if not by["hard-round1-quotas-unmet"]["quota_fired"]:
        return _fail("quota detector missed hard round-1")
    if not by["hard-late-quotas-unmet"]["quota_fired"]:
        return _fail("quota detector missed late unmet quotas")
    if by["hard-late-quotas-unmet"]["round_mutant_fired"]:
        return _fail("round-count mutant should miss late unmet (FN)")
    if by["hard-late-quotas-met"]["quota_fired"]:
        return _fail("quota detector flagged late quotas-met")

    perturbed_round = copy.deepcopy(easy)
    perturbed_round["round_index"] = 9
    if detect(perturbed_round)["fired"] or detect(easy)["fired"]:
        return _fail("changing round_index on an easy run changed the verdict")
    if detect(perturbed_round)["status"] != detect(easy)["status"]:
        return _fail("round_index perturbation changed status")

    drop_idea = copy.deepcopy(easy)
    drop_idea["ideas"] = drop_idea["ideas"][:1]
    if not detect(drop_idea)["fired"]:
        return _fail("dropping an idea below quota did not FIRE")
    drop_obj = copy.deepcopy(easy)
    drop_obj["objections"] = []
    if not detect(drop_obj)["fired"]:
        return _fail("dropping objections below quota did not FIRE")

    same_round_easy = copy.deepcopy(easy)
    same_round_hard = copy.deepcopy(hard_early)
    same_round_easy["round_index"] = 1
    same_round_hard["round_index"] = 1
    if detect(same_round_easy)["fired"] or not detect(same_round_hard)["fired"]:
        return _fail("same round_index did not discriminate easy vs hard")

    doc = {
        "ast_fire_decision_args": fire_args,
        "ast_forbidden_in_fire_decision": False,
        "fired_assigned_from_fire_decision": True,
        "matrix": matrix,
        "pass": True,
        "round_index_perturbation_silent": True,
        "quota_drop_fires": True,
        "same_round_discriminates": True,
        "round_mutant_false_positive_on_easy": True,
        "round_mutant_false_negative_on_late_unmet": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "ast_ok=True mutant_fp_easy=True mutant_fn_late_unmet=True "
        "round_perturbation_noop=True quota_drop_fires=True"
    )
    print("SUCCESS:IMP-0323-probe2 quota-not-round")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
