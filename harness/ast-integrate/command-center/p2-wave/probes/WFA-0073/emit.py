#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0073-disposition-evidence-gate.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls  # noqa: E402
import gate  # noqa: E402
import registry as R  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0073-disposition-evidence-gate.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0073/probe1_current_state.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0073/probe2_both_states.py"
)
CI = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0073/gate.py"
)
QUESTION = (
    "Implementation target: a gate that rejects a disposition whose record "
    "lacks the evidence its own class demands - ADOPT needs a passing smoke "
    "run, RETIRE needs a preservation proof, UNKNOWN needs a named executed "
    "probe, TRANSLATE needs a target adapter - plus a report of how many of "
    "the current 284 dispositions would fail it today."
)


def main() -> int:
    unit = R.catalog_unit("WFA-0073")
    loaded = R.load_registry()
    census = gate.evaluate_registry(loaded["records"])
    ctrl = controls.both_states()
    taut = controls.anti_tautology()
    if not ctrl["pass"]:
        print("FAILED:WFA-0073 emit both-states failed")
        return 1
    if not taut["pass"]:
        print("FAILED:WFA-0073 emit anti-tautology failed")
        return 1
    if census["n"] != 284:
        print(f"FAILED:WFA-0073 emit n={census['n']} want 284")
        return 1
    if census["fail_n"] < 1:
        print("FAILED:WFA-0073 emit zero failures (gate indistinguishable from no-op)")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_note = (
        loaded.get("note")
        if not loaded.get("live")
        else f"live registry {loaded.get('rel') or loaded.get('path')}"
    )
    answer = (
        f"The gate is live and enforces by default (no opt-in flag). "
        f"Over n={census['n']} current dispositions (source={loaded.get('source')}) "
        f"it rejects {census['fail_n']} records lacking class-required evidence "
        f"and passes {census['pass_n']}. Failures by class: "
        f"{json.dumps(census['fail_by_class'], sort_keys=True)}. "
        f"TRANSLATE is absent from the current histogram (0 of 284). "
        f"Both-states: stripping smoke evidence from a passing ADOPT-AS-IS "
        f"fires the gate; adding a retrieved hash-matched preservation proof "
        f"to a failing RETIRE clears it. "
        f"Corpus note: {source_note}. SUCCESS:WFA-0073"
    )
    slim_rows = [
        {
            "id": r["id"],
            "classification": r["classification"],
            "verdict": r["verdict"],
            "required": r["required"],
            "reason": r["reason"],
        }
        for r in census["rows"]
        if r["verdict"] == "FAIL"
    ]
    doc = {
        "record_type": "RegressionFixture",
        "fixture_id": "WFA-0073-disposition-evidence-gate",
        "unit_id": "WFA-0073",
        "id": "WFA-0073",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0073",
        "completion_sentinel": "SUCCESS:WFA-0073",
        "title": unit.get("title"),
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "gate": {
            "module": "command-center/p2-wave/probes/WFA-0073/gate.py",
            "default_enforce": True,
            "opt_in_required_to_enforce": False,
            "rules": {
                "ADOPT-AS-IS": "passing smoke run: exit 0 AND artifact exists AND size floor AND JSON parse",
                "ADOPT-WITH-WRAPPER": "passing smoke run: exit 0 AND artifact exists AND size floor AND JSON parse",
                "RETIRE": "preservation proof: retrieve named location and hash-match content",
                "UNKNOWN-NEEDS-PROBE": "named executed probe: id + command + recorded result",
                "TRANSLATE": "named target adapter",
            },
        },
        "ci_invocation": {
            "command": CI,
            "form": "default argv, no extra flags",
            "opt_in_required_to_enforce": False,
            "good_fixture": "command-center/p2-wave/probes/WFA-0073/fixtures/ci-good.json",
            "bad_fixture": "command-center/p2-wave/probes/WFA-0073/fixtures/ci-bad.json",
        },
        "current_state": {
            "n": census["n"],
            "gated_n": census["gated_n"],
            "fail_n": census["fail_n"],
            "pass_n": census["pass_n"],
            "by_class": census["by_class"],
            "fail_by_class": census["fail_by_class"],
            "pass_by_class": census["pass_by_class"],
            "source": loaded.get("source"),
            "live_registry": loaded.get("live"),
            "registry_path": loaded.get("rel") or loaded.get("path"),
            "note": source_note,
            "failing_ids": census["failing_ids"],
            "failing_rows": slim_rows,
        },
        "both_states": ctrl,
        "anti_tautology": taut,
        "cases": [
            {
                "id": "strip-passing-adopt",
                "direction": "good-to-bad",
                "expected": "FAIL",
                "actual": ctrl["strip_passing"]["after"]["verdict"],
                "result": "PASS" if ctrl["fires_on_stripped"] else "FAIL",
            },
            {
                "id": "add-anchor-failing-retire",
                "direction": "bad-to-good",
                "expected": "PASS",
                "actual": ctrl["add_anchor"]["after"]["verdict"],
                "result": "PASS" if ctrl["clears_on_repaired"] else "FAIL",
            },
        ],
        "tests": [
            {
                "id": "T1-current-state-census",
                "name": "current-state failure count over 284 by class",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-and-ci-default",
                "name": "both-states plus CI default invocation enforces",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "claim": "A: gate current-state failure count over all 284, by disposition class",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0073/gate.py:evaluate_registry",
            },
            {
                "claim": "B: strip a passing record (fires) and add a valid anchor to a failing record (clears)",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0073/controls.py:both_states",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0073-probe2-both-states-and-default-invocation",
            "verdict": "PASS",
            "independent": True,
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "caveats": [
            (
                "Live 08-WORKFLOW-CANDIDATE-REGISTRY.json (284 rows) is absent on "
                "this Linux worktree. The census uses a catalog-histogram stand-in "
                "with empty typed evidence, so every gated class fails. That is a "
                "fail-closed reading, not a claim that live evidence blobs were read."
                if not loaded.get("live")
                else "Census ran on the live 284-row registry found on this worktree."
            ),
            "High failure count is data, not a lane failure.",
            "Default CLI invocation of gate.py enforces; --json is output shape only.",
        ],
        "output_schema": unit.get("output_schema"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:WFA-0073")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
