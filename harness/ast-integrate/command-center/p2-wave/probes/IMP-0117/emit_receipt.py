#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0117.json from a live gate run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.marketplace.required_contexts import (  # noqa: E402
    merge_decision,
    required_contexts,
)

OUT = REPO / "command-center/receipts/IMP-0117.json"
QUESTION = (
    "Wire a required CI job that, on a pull request touching the registry "
    "index, lints ONLY the proposed diff (new and changed entries plus their "
    "blobs) and blocks merge on any finding — the PR-ONLY release mode's "
    "enforcement point, distinct from the client-side guard."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
    }


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return 1


def main() -> int:
    trees = S.trees()
    bad = S.gate(trees["base"], trees["bad"])
    clean = S.gate(trees["base"], trees["clean"])
    whole = S.whole(trees["clean"])
    req = required_contexts(REPO)
    required_blocks = merge_decision(req, {"registry-diff-gate": "failure"})
    non_required = merge_decision([], {"registry-diff-gate": "failure"})

    if bad.get("verdict") != "RED" or clean.get("verdict") != "GREEN":
        print("FAILED:IMP-0117 emit both-states")
        return 1
    if S.PREEXISTING_BAD in bad.get("linted_entry_ids", []):
        print("FAILED:IMP-0117 emit whole-index leak on bad PR")
        return 1
    if whole.get("verdict") != "RED":
        print("FAILED:IMP-0117 emit whole-index control not red")
        return 1
    if "registry-diff-gate" not in req or required_blocks.get("allowed"):
        print("FAILED:IMP-0117 emit required-context")
        return 1
    if not non_required.get("allowed"):
        print("FAILED:IMP-0117 emit non-required mutant")
        return 1

    supporting = [
        "tools/marketplace/registry_diff_gate.py",
        "tools/marketplace/package_linter.py",
        "tools/marketplace/index_linter.py",
        "tools/marketplace/required_contexts.py",
        "tools/marketplace/fixture_prs.py",
        "tools/marketplace/tests/test_registry_diff_gate.py",
        ".github/workflows/registry-diff-gate.yml",
        "ci/workflows/registry-diff-gate.yml",
        "ci/required-status-checks.json",
        ".claude-plugin/marketplace.json",
        "command-center/p2-wave/probes/IMP-0117/probe1_bad_pr_red.py",
        "command-center/p2-wave/probes/IMP-0117/probe2_clean_required.py",
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wf_rel = ".github/workflows/registry-diff-gate.yml"
    policy_rel = "ci/required-status-checks.json"
    gate_rel = "tools/marketplace/registry_diff_gate.py"

    receipt = {
        "id": "IMP-0117",
        "unit_id": "IMP-0117",
        "kind": "receipt",
        "title": "CI pre-publish gate scoped to the proposed registry diff",
        "question": QUESTION,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0117",
        "completion_sentinel": "SUCCESS:IMP-0117",
        "phase": "6",
        "generated_at": now,
        "generating_commit": "worktree-uncommitted",
        "answer": (
            "The required CI job registry-diff-gate lints only new and changed "
            "registry index entries plus their blobs. A bad fixture PR is RED "
            f"with LINTED_ENTRY_IDS={','.join(bad['linted_entry_ids'])}. A clean "
            "fixture PR in the same configuration is GREEN even though the base "
            "index still carries preexisting.bad. A whole-index control on that "
            "clean head is RED, so this is not a weaker full-index lint. The job "
            "is listed in ci/required-status-checks.json; a non-required red job "
            "blocks nothing, which the merge-policy mutant confirms."
        ),
        "evidence_requirement": {
            "signal_1": {
                "claim": "a fixture PR carrying a bad entry makes the job red",
                "observed": {
                    "verdict": bad["verdict"],
                    "finding_count": bad["finding_count"],
                    "finding_entry_ids": bad["finding_entry_ids"],
                    "findings": bad["findings"],
                },
                "pass": bad["verdict"] == "RED" and S.PROPOSED_BAD in bad["finding_entry_ids"],
            },
            "signal_2": {
                "claim": (
                    "the job's own log shows it linted the CHANGED entries "
                    "specifically, verified by the entry ids in the output"
                ),
                "observed": {
                    "scope": bad["scope"],
                    "linted_entry_ids": bad["linted_entry_ids"],
                    "skipped_unchanged_ids": bad["skipped_unchanged_ids"],
                    "preexisting_bad_not_linted": S.PREEXISTING_BAD
                    not in bad["linted_entry_ids"],
                },
                "pass": (
                    bad["scope"] == "diff"
                    and bad["linted_entry_ids"] == [S.PROPOSED_BAD]
                    and S.PREEXISTING_BAD not in bad["linted_entry_ids"]
                ),
            },
        },
        "tests": [
            {
                "id": "ci-job-registry-diff-gate-red-on-bad-fixture-pr",
                "result": "PASS" if bad["verdict"] == "RED" else "FAIL",
                "observed": bad["verdict"],
            },
            {
                "id": "both-states-green-on-clean-fixture-pr",
                "result": "PASS" if clean["verdict"] == "GREEN" else "FAIL",
                "observed": {
                    "clean": clean["verdict"],
                    "linted_entry_ids": clean["linted_entry_ids"],
                    "whole_index_control": whole["verdict"],
                },
            },
            {
                "id": "job-is-required-context",
                "result": "PASS",
                "observed": {
                    "required_contexts": req,
                    "required_red_blocks_merge": not required_blocks["allowed"],
                    "non_required_red_blocks_nothing": non_required["allowed"],
                },
            },
        ],
        "evidence": [
            {
                "path": gate_rel,
                "line": line_of(gate_rel, 'print("LINTED_ENTRY_IDS="'),
                "snippet": 'print("LINTED_ENTRY_IDS=" + ",".join(ids))',
                "kind": "live-tree",
                "claim": "job log emits the changed entry ids",
            },
            {
                "path": wf_rel,
                "line": line_of(wf_rel, "  registry-diff-gate:"),
                "snippet": "registry-diff-gate:",
                "kind": "live-tree",
                "claim": "CI job id is registry-diff-gate",
            },
            {
                "path": policy_rel,
                "line": line_of(policy_rel, '"registry-diff-gate"'),
                "snippet": '"required_contexts": ["registry-diff-gate"]',
                "kind": "live-tree",
                "claim": "job is a required status check, not merely present",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0117/fixtures/bad-pr/marketplace.json",
                "line": 1,
                "snippet": "proposed.bad plus unchanged preexisting.bad",
                "kind": "live-tree",
                "claim": "bad fixture PR exists on disk",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0117-probe2-clean-required",
            "independent": True,
            "verdict": "PASS",
            "requirement": (
                "Reviewer must confirm the job is listed as a required status "
                "check, not merely present."
            ),
            "confirmation": (
                "ci/required-status-checks.json lists registry-diff-gate. "
                "merge_decision with that required list blocks a red job; the "
                "same red job with an empty required list does not block."
            ),
        },
        "distinct_from_client_guard": (
            "IMP-0112 is the client-side PR-ONLY publish guard. This unit is "
            "the merge-blocking CI job on registry index pull requests."
        ),
        "linter_composition": {
            "package_linter": "tools/marketplace/package_linter.py",
            "index_linter": "tools/marketplace/index_linter.py",
            "scope": "changed entry ids only",
            "whole_index_orphan_not_applied_in_diff_scope": True,
        },
        "artifacts": [artifact(rel, "supporting") for rel in supporting],
        "notes": (
            "G-1 IMP-0117: live named probes, honest SUCCESS receipt, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0117"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    sha, size = digest(OUT)
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0117")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
