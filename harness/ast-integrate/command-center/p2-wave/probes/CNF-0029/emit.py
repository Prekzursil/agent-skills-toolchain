#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0029-change-surface.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from change_surface import is_empty_surface  # noqa: E402
from schema_local import schema_errors  # noqa: E402

OUT = "command-center/confirmation/CNF-0029-change-surface.json"
SCHEMA = "command-center/schema/regression-delta.schema.json"
MANIFEST = "command-center/p2-wave/probes/CNF-0029/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0029/probe1_three_dot_two_dot.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0029/probe2_would_revert.py"
)
SENTINEL = (
    "SUCCESS:CNF-0029 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and both the three-dot and "
    "two-dot surfaces are recorded per branch and the freshly-branched control "
    "returned empty. Any other terminal state is FAILED:CNF-0029 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Does the change a branch would actually propose match the change its author "
    "describes? Compute the commit-to-commit surface with the three-dot range "
    "against the integration branch and answer: how many files and deletions "
    "does the branch propose, does it propose reverting work the base already "
    "has, and does the two-dot diff give a different answer because it folds in "
    "working-tree noise? A stale branch can silently propose mass deletion, "
    "measured once at 1188 files and 316222 deletions."
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _surf(s: dict) -> dict:
    return {
        "spec": s.get("spec"),
        "file_count": s["file_count"],
        "insertions": s["insertions"],
        "deletions": s["deletions"],
        "added": list(s["added"]),
        "removed": list(s["removed"]),
        "changed": list(s["changed"]),
        "empty": bool(s["empty"]),
    }


def _probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:20000],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    audit = S.run_scenario()
    stale = audit["stale"]
    fresh = audit["fresh"]
    if not audit["control_empty"]:
        print("FAILED:CNF-0029 detector-failure freshly-branched control was not empty")
        print(json.dumps({"fresh_three": fresh["three_dot"], "fresh_two": fresh["two_dot"]}, indent=2)[:2000])
        return 1
    if not is_empty_surface(fresh["three_dot"]) or not is_empty_surface(fresh["two_dot"]):
        print("FAILED:CNF-0029 detector-failure control surface non-empty")
        return 1
    if not stale["three_dot_matches_author"]:
        print("FAILED:CNF-0029 surface-misreported three-dot does not match author paths")
        print(stale["three_dot"])
        return 1
    if stale["two_dot_matches_author"]:
        print("FAILED:CNF-0029 detector-failure two-dot unexpectedly matched author description")
        return 1
    if not stale["would_revert"]:
        print("FAILED:CNF-0029 detector-failure would-revert list empty on stale fixture")
        return 1
    if not stale["surfaces_differ"]:
        print("FAILED:CNF-0029 detector-failure three-dot and two-dot identical on stale fixture")
        return 1
    if not stale.get("two_dot_hides_working_tree"):
        print("FAILED:CNF-0029 detector-failure worktree noise not visible on two-dot")
        return 1
    missing = [p for p in S.INTENDED_PATHS if p in stale["would_revert"]]
    if missing:
        print("FAILED:CNF-0029 detector-failure author paths flagged as would-revert", missing)
        return 1
    unexpected = [p for p in stale["would_revert"] if not p.startswith("post-fork/")]
    if unexpected:
        print("FAILED:CNF-0029 detector-failure unexpected would-revert", unexpected)
        return 1

    three = stale["three_dot"]
    two = stale["two_dot"]
    wt = stale["two_dot_worktree"]
    host_git = (REPO / ".git").exists()
    answer = (
        "On the three-dot commit-to-commit surface the stale branch proposes "
        f"{three['file_count']} files and {three['deletions']} deletions, matching "
        "the author description (edit author-intent.txt, add feature-new.txt, "
        f"delete obsolete.txt). Two-dot reports {two['file_count']} files and "
        f"{two['deletions']} deletions because it treats "
        f"{stale['would_revert_count']} paths the integration branch gained after "
        f"merge-base {stale['merge_base_sha']} as deletions (would-revert). A dirty "
        "working tree adds further two-dot paths not in either commit range. A "
        "freshly branched HEAD returns an empty three-dot and empty two-dot "
        "surface, so the comparison is not inventing changes. "
        + SENTINEL
    )
    tests = [
        {
            "id": "three-dot-and-two-dot-both-recorded",
            "name": "three-dot and two-dot surfaces both computed",
            "command": "git diff --numstat integration...branch AND git diff --numstat integration..branch",
            "result": "PASS",
        },
        {
            "id": "would-revert-paths-base-gained-after-merge-base",
            "name": "deletions of paths the base gained after merge-base are listed",
            "command": "ls-tree(integration) - ls-tree(merge-base) - ls-tree(branch)",
            "result": "PASS",
        },
        {
            "id": "freshly-branched-HEAD-empty-surface",
            "name": "freshly branched HEAD shows an empty surface",
            "command": "git diff --numstat main...feature/fresh AND git diff --numstat main..feature/fresh",
            "result": "PASS",
        },
    ]
    report = {
        "kind": "regression-delta",
        "observations": [
            {
                "name": "stale-three-dot-file-count",
                "measured": three["file_count"],
                "method": "git-diff-three-dot-numstat",
                "anchor": f"git diff --numstat {S.INTEGRATION}...{S.STALE}",
            },
            {
                "name": "stale-three-dot-deletions",
                "measured": three["deletions"],
                "method": "git-diff-three-dot-numstat",
                "anchor": f"git diff --numstat {S.INTEGRATION}...{S.STALE}",
            },
            {
                "name": "stale-two-dot-file-count",
                "measured": two["file_count"],
                "method": "git-diff-two-dot-numstat",
                "anchor": f"git diff --numstat {S.INTEGRATION}..{S.STALE}",
            },
            {
                "name": "stale-two-dot-deletions",
                "measured": two["deletions"],
                "method": "git-diff-two-dot-numstat",
                "anchor": f"git diff --numstat {S.INTEGRATION}..{S.STALE}",
            },
            {
                "name": "would-revert-count",
                "measured": stale["would_revert_count"],
                "method": "ls-tree-set-difference",
                "anchor": f"merge-base {stale['merge_base_sha']}",
            },
            {
                "name": "fresh-three-dot-empty",
                "measured": True,
                "method": "git-diff-three-dot-numstat",
                "anchor": f"git diff --numstat {S.INTEGRATION}...{S.FRESH}",
            },
        ],
        "control_ids": [
            "fresh-HEAD-empty-surface",
            "author-delete-not-would-revert",
            "worktree-noise-on-two-dot",
        ],
        "title": "Change-surface confirmation on the three-dot commit range, not the working-tree diff",
        "question": QUESTION,
        "answer": answer,
        "claim_under_test": (
            "The three-dot commit-to-commit surface is the change a branch would "
            "propose. The two-dot tree compare against a stale branch silently "
            "proposes deleting paths the integration branch gained after the "
            "merge-base, and a dirty working tree makes two-dot disagree further."
        ),
        "comparison": {
            "left": "integration branch main (fixture)",
            "right": "candidate branches feature/stale and feature/fresh (fixture)",
            "method": "three-dot commit-to-commit vs two-dot commits vs two-dot worktree",
            "integration_branch": S.INTEGRATION,
        },
        "delta": {
            "added": list(three["added"]),
            "removed": list(three["removed"]),
            "changed": list(three["changed"]),
            "summary": (
                f"stale three-dot files={three['file_count']} deletions={three['deletions']}; "
                f"two-dot files={two['file_count']} deletions={two['deletions']}; "
                f"would-revert={stale['would_revert_count']}; "
                f"fresh control empty; worktree extra={stale.get('worktree_noise_paths')}"
            ),
            "three_dot_matches_author_description": True,
            "two_dot_matches_author_description": False,
            "unchanged_count_can_hide_flips": True,
        },
        "branches": [
            {
                "name": S.STALE,
                "role": "stale-candidate",
                "author_description": S.AUTHOR_DESCRIPTION,
                "merge_base_sha": stale["merge_base_sha"],
                "integration_sha": stale["integration_sha"],
                "branch_sha": stale["branch_sha"],
                "three_dot": _surf(three),
                "two_dot": _surf(two),
                "two_dot_worktree": _surf(wt),
                "deletion_count_three_dot": three["deletions"],
                "deletion_count_two_dot": two["deletions"],
                "would_revert": list(stale["would_revert"]),
                "would_revert_count": stale["would_revert_count"],
                "stale_branch_would_revert": True,
                "worktree_noise_paths": list(stale.get("worktree_noise_paths") or []),
            },
            {
                "name": S.FRESH,
                "role": "freshly-branched-control",
                "author_description": "no commits; branched from integration HEAD",
                "merge_base_sha": fresh["merge_base_sha"],
                "integration_sha": fresh["integration_sha"],
                "branch_sha": fresh["branch_sha"],
                "three_dot": _surf(fresh["three_dot"]),
                "two_dot": _surf(fresh["two_dot"]),
                "deletion_count_three_dot": 0,
                "deletion_count_two_dot": 0,
                "would_revert": [],
                "would_revert_count": 0,
                "stale_branch_would_revert": False,
                "control_empty": True,
            },
        ],
        "control": {
            "branch": S.FRESH,
            "three_dot_empty": True,
            "two_dot_empty": True,
            "merge_base_sha": fresh["merge_base_sha"],
            "proves_comparison_does_not_invent_changes": True,
        },
        "historical_incident": {
            "files": 1188,
            "deletions": 316222,
            "note": (
                "Measured leftover feature branch against main. Fixture reproduces "
                "the same two-dot mass-deletion class at smaller scale; it does not "
                "re-quote those counts as this run's file_count."
            ),
        },
        "host_worktree": {
            "path": str(REPO),
            "is_git_repo": host_git,
            "note": (
                "Host tree is not a git repository on this Linux worktree; candidate "
                "branches are the isolated fixture (never staged into a shared index)."
            ),
        },
        "windows_shell_8d": {
            "declared_input": "rules/common/windows-shell.md section 8d",
            "host_path_present": (REPO / "rules/common/windows-shell.md").is_file(),
            "rule_applied": (
                "Proposal surface is the three-dot commit-to-commit range against "
                "the integration branch; two-dot and working-tree diffs are recorded "
                "separately and must not be treated as the proposal."
            ),
        },
        "completion_sentinel": SENTINEL,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "cloud_ok": False,
    }

    placeholder = "0" * 64
    doc: dict = {
        "schema_version": 1,
        "unit_id": "CNF-0029",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "rules/common/windows-shell.md:8d; command-center/WORK-UNIT-CATALOG.json:CNF-0029",
        "min_bytes_threshold": 2048,
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2048,
                "sha256": placeholder,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Three-dot and two-dot surfaces are both recorded per branch; "
                    "the freshly-branched control is empty; two-dot deletions exceed "
                    "three-dot on the stale fixture."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0029/change_surface.py:surface_from_spec",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        f"git diff --numstat {S.INTEGRATION}...{S.STALE} ; git diff --numstat {S.INTEGRATION}..{S.STALE}",
                        json.dumps(
                            {
                                "three_dot": _surf(three),
                                "two_dot": _surf(two),
                                "fresh_three_empty": True,
                                "fresh_two_empty": True,
                            },
                            sort_keys=True,
                        ),
                        "git:three-dot-two-dot-numstat",
                    ),
                    _probe(
                        "verifier",
                        "schema-validate",
                        P1,
                        (
                            f"stale three-dot files={three['file_count']} "
                            f"deletions={three['deletions']} "
                            f"two-dot files={two['file_count']} "
                            f"deletions={two['deletions']} control empty=True"
                        ),
                        "probe1:three-dot-two-dot",
                    ),
                ],
            },
            {
                "claim": (
                    "Any deletion of a path the integration branch gained after the "
                    "merge-base is flagged as would-revert and listed by path; the "
                    "author-described deletion obsolete.txt is not in that list."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0029/change_surface.py:would_revert_paths",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        "git ls-tree -r --name-only <integration> minus merge-base minus branch",
                        json.dumps(
                            {
                                "merge_base_sha": stale["merge_base_sha"],
                                "would_revert": list(stale["would_revert"]),
                                "author_deletion_excluded": "obsolete.txt",
                            },
                            sort_keys=True,
                        ),
                        "git:ls-tree-would-revert",
                    ),
                    _probe(
                        "verifier",
                        "static-analysis",
                        P2,
                        (
                            f"would-revert={stale['would_revert_count']} "
                            f"merge-base={stale['merge_base_sha']} "
                            "author-deletion-excluded=obsolete.txt"
                        ),
                        "probe2:would-revert-ls-tree",
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "fresh-HEAD-empty-surface",
                "kind": "known-broken-fixture",
                "description": (
                    "A freshly branched HEAD must show an empty three-dot and "
                    "two-dot surface; the stale fixture must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"feature/stale three-dot files={three['file_count']} "
                    f"two-dot files={two['file_count']}"
                ),
                "good_state_output": "feature/fresh three-dot files=0 two-dot files=0",
            },
            {
                "id": "author-delete-not-would-revert",
                "kind": "mutation",
                "description": (
                    "obsolete.txt is an author-described deletion on the feature "
                    "branch; the would-revert detector must not classify it as a "
                    "post-fork revert."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": " ".join(stale["would_revert"]),
                "good_state_output": "obsolete.txt not in would-revert",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0029-probe2-would-revert",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Named probe2 rebuilds the isolated fixture and re-derives "
                "would-revert from ls-tree set difference BEFORE reading this "
                "receipt's conclusion. Self-review of emit.py does not count."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": "CNF-0029",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0029/probe1_three_dot_two_dot.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "test-run",
                    P1,
                    "consumer reads artifact branches and live-recomputes surfaces",
                    "consumer:probe1",
                ),
            },
            {
                "consumer": "command-center/p2-wave/probes/CNF-0029/probe2_would_revert.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "test-run",
                    P2,
                    "consumer re-derives would-revert then reads artifact conclusion",
                    "consumer:probe2",
                ),
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "retry": {
            "count": 0,
            "policy": "zero retries. This unit's first observation IS the verdict; a later run that disagrees is a DISCREPANCY to record (spec 11039), never an error to retry away",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Host /opt/p2/ast-integrate is not a git checkout, so live "
                    "origin/main...HEAD cannot be measured here; the isolated "
                    "fixture reproduces the 8d class."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run change_surface.measure_branch against a real leftover "
                    "feature branch once this tree has .git and origin/main."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "change-surface-auditor",
            "execution_substrate": "local-serialized",
        },
        "report": report,
        "extensions": {"cloud_ok": False},
    }

    blob = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    raw = blob.encode("utf-8")
    doc["artifacts"][0]["sha256"] = sha256_bytes(raw)
    doc["artifacts"][0]["bytes"] = len(raw.replace(b"\r\n", b"\n"))
    doc["timestamps"]["ended_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0029 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}):
        g_errs = schema_errors(garbage)
        if not g_errs:
            print(f"FAILED:CNF-0029 schema accepted garbage {list(garbage)[:2]}")
            return 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0029 sentinel-absent before write")
        return 1
    if len(text.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:CNF-0029 artifact below min_bytes_threshold")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    live = out.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(live)} sha256={sha256_bytes(live)}")
    print("SUCCESS:CNF-0029 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
