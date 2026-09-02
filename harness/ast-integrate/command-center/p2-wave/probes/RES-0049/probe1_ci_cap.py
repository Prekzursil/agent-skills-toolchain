#!/usr/bin/env python3
"""Probe 1: live CI census vs artifact, file:line anchors, L2-mutant red.

Mechanically independent of probe 2 (does not read HTTP spec captures or
grade two-rail evidence).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/research/RES-0049.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0049-probe1 {msg}")
    return 1


def resolve(path: str, line: int, snippet: str) -> tuple[bool, str]:
    p = REPO / path
    if not p.is_file():
        return False, f"missing:{path}"
    lines = p.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{path}:{line}"
    got = lines[line - 1]
    if snippet.strip() not in got:
        return False, f"snippet-miss:{path}:{line}"
    return True, f"{path}:{line}"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "RES-0049":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:RES-0049" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = C.run_census(REPO)
    rec = doc.get("ci_census") or {}
    for key in (
        "github_workflows_dir_present",
        "inventory_workflow_count",
        "inventory_job_count",
        "inventory_step_count",
        "inventory_workflow_files",
        "uses_actions",
        "measured_build_level",
        "max_without_hosted_builder",
    ):
        if rec.get(key) != live.get(key):
            return fail(f"census-drift:{key} rec={rec.get(key)!r} live={live.get(key)!r}")
    if live.get("attestation_generator_hits"):
        return fail(f"unexpected-generator-hits {live['attestation_generator_hits']}")
    if rec.get("attestation_generator_hits"):
        return fail("artifact-claims-generator-hits")
    if live.get("github_workflows_dir_present") is True and not live.get("worktree_workflow_files"):
        return fail("workflows-dir-present-but-empty-unexplained")
    if live.get("inventory_workflow_count") != 7:
        return fail(f"workflow-count {live.get('inventory_workflow_count')}")
    if live.get("measured_build_level") != "L0":
        return fail("census-not-L0")

    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        return fail(f"overclaim:{why}")
    mutant = copy.deepcopy(doc)
    mutant["level_verdict"]["achievable_without_hosted_builder"] = "SLSA Build L2"
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_l2_ok={mok} {mwhy}")
    if mok:
        return fail("L2-mutant-was-accepted")

    for i, row in enumerate(doc.get("evidence") or []):
        rok, rwhy = resolve(str(row.get("path") or ""), int(row.get("line") or 0), str(row.get("snippet") or ""))
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            return fail(f"unresolved-anchor:{rwhy}")

    lv = doc.get("level_verdict") or {}
    cite = str(lv.get("ci_file_line") or "")
    if "probe1-yaml-inventory.json:" not in cite:
        return fail("level-verdict-missing-ci-file-line")
    print(
        json.dumps(
            {
                "probe": "probe1-ci-cap",
                "workflows": live["inventory_workflow_count"],
                "generator_hits": 0,
                "measured": live["measured_build_level"],
                "max_without_hosted": live["max_without_hosted_builder"],
                "github_dir": live["github_workflows_dir_present"],
                "ci_file_line": cite,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0049-probe1 CI census file:line L2-mutant-red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
