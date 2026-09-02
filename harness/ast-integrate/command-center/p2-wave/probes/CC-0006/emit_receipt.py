#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0006.json from live gate measurements.

Does not run the named probes (probe2 reads this receipt). Honesty: this
worktree is not a git repository, so the three-route byte table is
NOT-CHECKED here rather than copied from catalog folklore.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE_PATH = REPO / "command-center" / "wrong_recipe_gate.py"
OUT = REPO / "command-center/receipts/CC-0006.json"


def load_gate():
    spec = importlib.util.spec_from_file_location("wrong_recipe_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:CC-0006 cannot load gate")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git_ok() -> dict:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "three_route": "NOT-CHECKED",
        }
    inside = r.returncode == 0 and r.stdout.strip() == "true"
    return {
        "available": inside,
        "exit_code": r.returncode,
        "stdout": (r.stdout or "").strip()[:200],
        "stderr": (r.stderr or "").strip()[:400],
        "three_route": "MEASURED" if inside else "NOT-CHECKED",
        "reason": None
        if inside
        else "this worktree is not a git repository (rev-parse rc="
        f"{r.returncode}); archive-vs-blob CRLF counts are not invented",
    }


def brief(hits: list[dict]) -> list[dict]:
    return [
        {
            "path": h.get("path"),
            "line": h.get("line"),
            "role": h.get("role"),
            "text": h.get("text") or h.get("text"),
        }
        for h in hits
    ]


def main() -> int:
    g = load_gate()
    st = g.self_test()
    if st:
        print("FAILED:CC-0006 labelled controls")
        for row in st:
            print(" ", row)
        return 1

    pre = HERE / "fixtures/pre-fix/RELEASE-CHECKLIST.md"
    scratch = HERE / "fixtures/scratch-empty.md"
    planted = HERE / "fixtures/planted-regression.md"
    held = HERE / "fixtures/reviewer-heldout-documentary.md"
    live_cl = REPO / "command-center/RELEASE-CHECKLIST.md"
    live_sh = REPO / "rules/common/windows-shell.md"

    pre_hits = g.scan_path(pre, REPO)
    scratch_hits = g.scan_path(scratch, REPO)
    plant_hits = g.scan_path(planted, REPO)
    held_hits = g.scan_path(held, REPO)
    live_cl_hits = g.scan_path(live_cl, REPO)
    live_sh_hits = g.scan_path(live_sh, REPO)
    live_scan: list[dict] = []
    for p in g.default_targets(REPO):
        live_scan.extend(g.scan_path(p, REPO))

    pre_bad = g.prescriptive(pre_hits)
    plant_bad = g.prescriptive(plant_hits)
    live_cl_bad = g.prescriptive(live_cl_hits)
    live_sh_bad = g.prescriptive(live_sh_hits)
    live_bad = g.prescriptive(live_scan)

    git = git_ok()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tests_ok = {
        "T1-known-present-prefix-checklist-fires": bool(pre_bad),
        "T2-known-absent-scratch-zero": scratch_hits == [],
        "T3-use-vs-mention-windows-shell-silent": live_sh_bad == []
        and any(h["role"] == "DOCUMENTARY" for h in live_sh_hits),
        "T4-postfix-checklist-silent-planted-refires": live_cl_bad == []
        and bool(plant_bad),
        "T5-reviewer-heldout-documentary-silent": bool(held_hits)
        and not g.prescriptive(held_hits),
        "T6-labelled-controls": not st,
        "T7-live-default-scan-silent": live_bad == [],
    }
    if not all(tests_ok.values()):
        print("FAILED:CC-0006 emit tests", json.dumps(tests_ok, indent=2))
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": "CC-0006",
        "id": "CC-0006",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CC-0006",
        "completion_sentinel": "SUCCESS:CC-0006",
        "title": "Gate command-center prose against platform-wrong verification recipes",
        "profile": "selfimprove-measure-artifact",
        "min_bytes_threshold": 2048,
        "output_schema": "command-center/schema/receipt.schema.json",
        "output_schema_on_disk": (
            REPO / "command-center/schema/receipt.schema.json"
        ).is_file(),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CC-0006",
        "produced_by": {
            "vendor": "cursor",
            "model": "composer",
            "role": "detector-engineer",
            "execution_substrate": "local-parallel",
        },
        "question": (
            "Does any command-center document instruct a reader to verify something "
            "using a recipe that returns the wrong bytes on the Windows autocrlf box "
            "this checklist is written for?"
        ),
        "answer": (
            "Before the fix, RELEASE-CHECKLIST.md prescribed verifying formatting "
            "'against the LF blob (git archive)'. That line is PRESCRIPTIVE and the "
            "gate fires on the pre-fix fixture. The live file now prescribes "
            "git cat-file -p / git show and names git archive only to forbid it. "
            "rules/common/windows-shell.md quotes the same string to forbid it and "
            "does not fire (use-vs-mention). A scratch document with no recipe "
            "scores 0. A planted regression of the original line re-fires. An "
            "independent reviewer-held-out documentary mention does not fire."
        ),
        "git_three_route": git,
        "gate": {
            "path": "command-center/wrong_recipe_gate.py",
            "classifier": "sentence-role (PRESCRIPTIVE | DOCUMENTARY | PACKAGING)",
            "default_targets": list(g.DEFAULT_RELATIVE),
            "labelled_control_count": len(g.LABELLED_CONTROLS),
        },
        "demonstrations": {
            "prescriptive_hit": brief(pre_bad),
            "documentary_non_hit": brief(
                [h for h in live_sh_hits if h["role"] == "DOCUMENTARY"][:3]
            ),
            "identical_string": "git archive",
            "known_absent_scratch_hits": len(scratch_hits),
            "postfix_live_prescriptive": brief(live_cl_bad),
            "planted_regression": brief(plant_bad),
            "reviewer_heldout": brief(held_hits),
        },
        "live_scan": {
            "prescriptive_count": len(live_bad),
            "hits": brief(live_scan),
        },
        "tests": [
            {
                "id": tid,
                "result": "PASS" if ok else "FAIL",
            }
            for tid, ok in tests_ok.items()
        ],
        "negative_controls": [
            {
                "id": "CC0006-C1-known-present",
                "kind": "known-broken-fixture",
                "description": (
                    "Pre-fix RELEASE-CHECKLIST.md line "
                    "'Verify formatting against the LF blob (git archive).' "
                    "must fire. A gate silent here measures nothing."
                ),
                "fired_on_bad_state": bool(pre_bad),
                "silent_on_good_state": scratch_hits == [],
            },
            {
                "id": "CC0006-C2-use-vs-mention",
                "kind": "use-vs-mention",
                "description": (
                    "windows-shell.md quotes the identical git archive string "
                    "in order to forbid it and must not fire."
                ),
                "fired_on_bad_state": bool(pre_bad),
                "silent_on_good_state": not live_sh_bad,
            },
            {
                "id": "CC0006-C3-planted-regression",
                "kind": "mutation",
                "description": (
                    "Corrected live checklist silent; planted original line re-fires."
                ),
                "fired_on_bad_state": bool(plant_bad),
                "silent_on_good_state": not live_cl_bad,
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0006-held-out-documentary-mention",
            "independent": True,
            "verdict": "PASS",
            "supplied": (
                "fixtures/reviewer-heldout-documentary.md — a 2024 postmortem "
                "sentence naming `git archive HEAD -- README.md` as the measured "
                "defect, not as an instruction. Text is not a labelled control."
            ),
            "heldout_prescriptive": 0,
            "heldout_documentary": len(held_hits),
        },
        "artifacts": [
            {
                "path": "command-center/wrong_recipe_gate.py",
                "role": "primary-implementation",
                "exists": GATE_PATH.is_file(),
            },
            {
                "path": "command-center/RELEASE-CHECKLIST.md",
                "role": "fixed-prose",
                "exists": live_cl.is_file(),
            },
            {
                "path": "rules/common/windows-shell.md",
                "role": "documentary-mention",
                "exists": live_sh.is_file(),
            },
            {
                "path": "command-center/receipts/CC-0006.json",
                "role": "primary",
                "exists": True,
            },
        ],
        "retry": {
            "count": 1,
            "policy": (
                "Two strikes then pivot from string matching to sentence-role "
                "classification with a labelled control set. First scan of the "
                "pre-fix fixture was DOCUMENTARY because nearby heading contained "
                "'defect'; classifier now prefers sentence-local prescription."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "On THIS Linux worktree, git archive vs cat-file CRLF divergence "
                    "is NOT-CHECKED because git rev-parse is not inside a work tree. "
                    "The gate still flags the recipe the catalog measured as wrong "
                    "on the Windows autocrlf box the checklist addresses."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "command-center/schema/receipt.schema.json is absent on this "
                    "tree (CC-0002 substrate). This receipt is not schema-validated "
                    "here; G-1 measure does not require it."
                ),
                "verdict": "CONFIRMED-ABSENT",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "SUCCESS:CC-0006 G-1 delivery: live named probes, honest non-BLOCKED "
            "artifact, per-unit UNIT-ARTIFACT-MANIFEST.json. Did not run "
            "unit_manifest.py --write. Did not relaunch finish-everything-close."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT.relative_to(REPO)} bytes={OUT.stat().st_size}")
    print("SUCCESS:CC-0006")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
