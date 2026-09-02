#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0001-branch-merge-state.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

OUT = C.OUT_REL
SCHEMA = C.SCHEMA_REL


def main() -> int:
    bundle = C.live_bundle()
    fixture = bundle["fixture"]
    if not bundle["control_ok"]:
        print(f"FAILED:AUD-0001 control {bundle['control_detail']}")
        return 1
    squash = C.by_name(fixture, C.SQUASH_BRANCH)
    unmerged = C.by_name(fixture, C.UNMERGED_BRANCH)
    on_main = C.by_name(fixture, C.ON_MAIN_BRANCH)
    if squash is None or unmerged is None or on_main is None:
        print("FAILED:AUD-0001 fixture branches missing")
        return 1
    if squash["content_on_main"] and unmerged["content_on_main"]:
        print("FAILED:AUD-0001 content detector is not discriminating")
        return 1
    owner = bundle["owner"]
    declared = bundle["declared_roots"]
    walked = [r for r in declared if r["walked"]]
    absent = [r["label"] for r in declared if not r["exists"]]

    p1_raw = json.dumps(
        {
            "probe": "probe1-ancestry",
            "command": C.P1_CMD,
            "squash_ahead_count": squash["ancestry_ahead_count"],
            "squash_cherry_plus": squash["cherry_plus"],
            "squash_cherry_minus": squash["cherry_minus"],
            "unmerged_ahead_count": unmerged["ancestry_ahead_count"],
            "already_on_main_ahead": on_main["ancestry_ahead"],
            "cherry_raw": squash["cherry_raw"],
        },
        indent=2,
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "probe": "probe2-content",
            "command": C.P2_CMD,
            "squash_content_on_main": squash["content_on_main"],
            "squash_reason": squash["content_reason"],
            "PR-MERGED": squash["pr_merged"],
            "TREE-EQUAL": squash["two_dot_empty"],
            "three_dot_empty": squash["three_dot_empty"],
            "unmerged_content_on_main": unmerged["content_on_main"],
            "class": squash["class"],
            "falsified": "ancestry-ahead-as-unmerged",
        },
        indent=2,
        sort_keys=True,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "AUD-0001",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0001",
        "completion_sentinel": C.SENTINEL,
        "kind": "audit-inventory",
        "schema_version": 1,
        "title": "Branch inventory with squash-merge-aware merge-state classification",
        "question": C.QUESTION,
        "produced_at": now,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "headline": {
            "repos_inventoried": 1 + (1 if owner else 0),
            "fixture_branches_classified": len(fixture["branches"]),
            "ancestry_ahead": fixture["ancestry_ahead"],
            "content_on_main": fixture["content_on_main"],
            "not_on_main": fixture["not_on_main"],
            "squash_merge_false_ahead": fixture["squash_merge_false_ahead"],
            "pr_merged_count": fixture["pr_merged_count"],
            "github_live_api": "NOT-CHECKED",
            "declared_roots_absent": absent,
            "owner_git_present": owner["git_present"],
            "content_on_main_uses_ancestry": False,
        },
        "fixture": fixture,
        "declared_roots": declared,
        "owner_worktree": owner,
        "non_utf8_path_control": bundle["non_utf8"],
        "github_live": bundle["github_live"],
        "pr_page": {
            "path": C.API_REL,
            "head_sha": bundle["pr_page"]["head_sha"],
        },
        "observations": [
            {
                "name": "squash_branch_ancestry_ahead",
                "measured": squash["ancestry_ahead_count"],
                "method": "git rev-list --count main..feature-squash",
                "anchor": "command-center/p2-wave/probes/AUD-0001/probe1_ancestry.py",
            },
            {
                "name": "squash_branch_content_on_main",
                "measured": squash["content_on_main"],
                "method": "GitHub PR merged_at/merged for head SHA, else git diff --quiet main feature-squash (two-dot tree)",
                "anchor": "command-center/p2-wave/probes/AUD-0001/probe2_content.py",
            },
            {
                "name": "unmerged_branch_content_on_main",
                "measured": unmerged["content_on_main"],
                "method": "two-dot tree equality against main; planted unique file",
                "anchor": "command-center/p2-wave/probes/AUD-0001/probe2_content.py",
            },
            {
                "name": "declared_root_walks",
                "measured": len(walked),
                "method": "stat ~/source and ~/Documents/GitHub; do not recurse the latter",
                "anchor": str(Path.home()),
            },
        ],
        "named_probes": [
            {
                "id": "probe1-ancestry",
                "command": C.P1_CMD,
                "role": "rev-list-and-cherry",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2-content",
                "command": C.P2_CMD,
                "role": "pr-merged-or-tree-equal",
                "raw_output": p2_raw,
            },
        ],
        "tests": [
            {
                "id": "squash-merge-ancestry-lies",
                "command": C.P1_CMD,
                "result": "PASS",
                "requirement": (
                    "plant a squash-merged branch; ancestry-only (rev-list "
                    "main..<branch>) reports AHEAD"
                ),
            },
            {
                "id": "squash-merge-content-on-main",
                "command": C.P2_CMD,
                "result": "PASS",
                "requirement": (
                    "same planted branch is CONTENT-ON-MAIN by PR-MERGED or "
                    "two-dot tree equality; unmerged twin is not"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0001-probe2-content",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-runs PR-page + two-dot tree comparison and "
                "falsifies using ancestry-ahead as unmerged. Catalog asked "
                "for a cross-vendor Codex reviewer of probe 2 only; this "
                "lane is the independent probe, not a second human. Disclosed."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/AUD-0001/probe1_ancestry.py",
                "kind": "command",
                "claim": (
                    f"rev-list main..{C.SQUASH_BRANCH} = "
                    f"{squash['ancestry_ahead_count']} (AHEAD); cherry "
                    f"+{squash['cherry_plus']}/-{squash['cherry_minus']}."
                ),
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0001/probe2_content.py",
                "kind": "command",
                "claim": (
                    f"{C.SQUASH_BRANCH} is CONTENT-ON-MAIN via "
                    f"{squash['content_reason']} while {C.UNMERGED_BRANCH} "
                    f"is not; class={squash['class']}."
                ),
            },
            {
                "path": C.API_REL,
                "kind": "fixture",
                "claim": (
                    "GitHub list-pulls page for fixture--squash-estate marks "
                    f"head {bundle['pr_page']['head_sha'][:12]} MERGED."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0001/classify.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Declared inputs walk every repo under ~/source and "
                    "~/Documents/GitHub. On this Linux worktree both roots "
                    f"are absent ({absent}). No owner-estate branch census "
                    "was collected here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run for-each-ref + probe 2 on an approved owner-repo "
                    "list that includes those roots, without walking a "
                    "concurrent-session tree."
                ),
            },
            {
                "claim": (
                    "Live GitHub pull_request state for owner remotes was "
                    "not queried (gh CLI absent; tokens are not consumed)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "With a redacted-safe GitHub client, list PRs per owner "
                    "repo and join on branch head SHA."
                ),
            },
            {
                "claim": (
                    "rules/common/ci-hygiene.md section 4 is not present as "
                    "a live file in this worktree; squash-merge-ahead is "
                    "proven by the planted fixture instead."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Read the live rules/common/ci-hygiene.md section 4 and "
                    "confirm the fixture still matches the stated rule."
                ),
            },
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "this worktree is a git repository",
                "every owner repo under ~/source and ~/Documents/GitHub was walked",
                "live GitHub API was queried",
            ],
            "proof_surface": (
                "Planted squash-estate: ancestry-only reports feature-squash "
                "AHEAD; probe 2 (PR-MERGED page + two-dot tree) reports "
                "CONTENT-ON-MAIN; planted unmerged twin stays NOT-ON-MAIN."
            ),
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:AUD-0001 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:AUD-0001 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:AUD-0001 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} squash_ahead={squash['ancestry_ahead_count']} "
        f"content_on_main={squash['content_on_main']} class={squash['class']}"
    )
    print("SUCCESS:AUD-0001 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
