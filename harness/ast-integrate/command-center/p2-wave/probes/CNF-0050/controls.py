"""Detector controls for CNF-0050. Both-states: unexecuted is refused; known-good records."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from measure import completeness, measure_layout
from paths import HERE, PAYLOAD

NAMED = ["ROLLBACK-MANIFEST.md", "RUNBOOK.md"]


def materialize(kind: str, dest: Path) -> Path:
    src = HERE / "fixtures" / kind
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    sandbox = dest / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    if kind != "ambiguous":
        (sandbox / "payload.bin").write_bytes(PAYLOAD)
    return dest


def measure_fixture(kind: str, dest: Path) -> dict[str, Any]:
    root = materialize(kind, dest)
    return measure_layout(
        guide_root=root,
        named=NAMED,
        sandbox=root / "sandbox",
        include_catalog_coverage=False,
        runbook_requires_section=True,
    )


def control_known_good(dest: Path) -> dict[str, Any]:
    report = measure_fixture("known-good", dest)
    ok, problems = completeness(report["steps"])
    executed = [s for s in report["steps"] if s.get("status") == "executed"]
    nonzero = [s for s in executed if s.get("exit_code") not in (0,)]
    followable = report["guide_followable"] is True
    passed = (
        ok
        and not nonzero
        and followable
        and report["extracted_count"] >= 3
        and report["unexecuted_count"] == 0
    )
    return {
        "id": "known-good-records",
        "pass": passed,
        "fired_on_bad": True,
        "silent_on_good": passed,
        "completeness_ok": ok,
        "problems": problems,
        "guide_followable": report["guide_followable"],
        "extracted_count": report["extracted_count"],
        "nonzero": [s.get("id") for s in nonzero],
        "unexecuted_count": report["unexecuted_count"],
    }


def control_unexecuted_refused(dest: Path) -> dict[str, Any]:
    report = measure_fixture("known-good", dest)
    mutant = [dict(s) for s in report["steps"]]
    if len(mutant) < 3:
        return {
            "id": "unexecuted-refused",
            "pass": False,
            "reason": "known-good produced too few steps to mutate",
            "fired_on_bad": False,
            "silent_on_good": True,
        }
    target = None
    for s in mutant:
        if s.get("status") == "executed" and not s.get("command", "").startswith(
            "test -f "
        ):
            target = s
            break
    if target is None:
        target = mutant[-1]
    target.pop("exit_code", None)
    target.pop("deviation", None)
    target["status"] = "unexecuted"
    bad_ok, bad_problems = completeness(mutant)
    good_ok, _ = completeness(report["steps"])
    fired = (not bad_ok) and any(
        "unexecuted" in p or "unrecorded" in p for p in bad_problems
    )
    return {
        "id": "unexecuted-refused",
        "pass": fired and good_ok,
        "fired_on_bad": fired,
        "silent_on_good": good_ok,
        "bad_problems": bad_problems,
        "mutated_id": target.get("id"),
    }


def control_wrong_recipe_filed(dest: Path) -> dict[str, Any]:
    report = measure_fixture("wrong-recipe", dest)
    filed = [
        d
        for d in report["defects"]
        if d.get("classification") == "wrong-recipe"
        and "git cat-file" in str(d.get("corrected_recipe") or d.get("detail") or "")
    ]
    steps_marked = [
        s for s in report["steps"] if s.get("classification") == "wrong-recipe"
    ]
    return {
        "id": "wrong-recipe-filed",
        "pass": bool(filed) and bool(steps_marked),
        "fired_on_bad": bool(filed),
        "silent_on_good": True,
        "defect_ids": [d["id"] for d in filed],
        "step_ids": [s.get("id") for s in steps_marked],
    }


def control_mention_not_flagged(dest: Path) -> dict[str, Any]:
    report = measure_fixture("mention-only", dest)
    wrong = [
        d for d in report["defects"] if d.get("classification") == "wrong-recipe"
    ]
    return {
        "id": "use-vs-mention",
        "pass": not wrong,
        "fired_on_bad": True,
        "silent_on_good": not wrong,
        "wrong_defects": [d["id"] for d in wrong],
        "extracted_count": report["extracted_count"],
    }


def control_ambiguous_not_improvised(dest: Path) -> dict[str, Any]:
    report = measure_fixture("ambiguous", dest)
    amb = [
        s for s in report["steps"] if s.get("classification") == "ambiguous-step"
    ]
    improvised = [s for s in report["steps"] if s.get("improvised") is True]
    executed_placeholder = [
        s
        for s in report["steps"]
        if "<VERSION>" in str(s.get("command") or "")
        and s.get("status") == "executed"
    ]
    return {
        "id": "ambiguous-not-improvised",
        "pass": bool(amb) and not improvised and not executed_placeholder,
        "fired_on_bad": bool(amb),
        "silent_on_good": True,
        "ambiguous_ids": [s.get("id") for s in amb],
        "improvised": bool(improvised),
    }


def run_all_controls(scratch: Path) -> list[dict[str, Any]]:
    return [
        control_known_good(scratch / "known-good"),
        control_unexecuted_refused(scratch / "unexecuted"),
        control_wrong_recipe_filed(scratch / "wrong-recipe"),
        control_mention_not_flagged(scratch / "mention-only"),
        control_ambiguous_not_improvised(scratch / "ambiguous"),
    ]
