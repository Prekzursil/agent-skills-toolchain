#!/usr/bin/env python3
"""AUD-0003 Probe 2: GitHub merged_at + merge_commit_sha reachability.

For the same bounded sample as probe1, read `merged_at` and
`merge_commit_sha` via `gh api` / `gh pr view`, then test whether
`merge_commit_sha` is an ancestor of `origin/main`.

Cross-check rule (catalog evidence_requirement):
  Only call content "deliberately absent from main" when BOTH signals agree
  the PR was merged:
    - merged_at is non-null
    - merge_commit_sha is a reachable ancestor of origin/main

Writes:
  probe2-github-merge-reachability.json
  probe2-github-merge-reachability.raw.txt
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE))
import sample_bound as SB  # noqa: E402

OUT_JSON = PROBE / "probe2-github-merge-reachability.json"
OUT_RAW = PROBE / "probe2-github-merge-reachability.raw.txt"
# Probe1 output for cross-join of deliberate-absence findings
P1_JSON = PROBE / "probe1-git-diff-missing.json"


def refresh_merge_fields(pr: dict) -> dict:
    """Re-read merge fields from GitHub API (authoritative for merge_commit_sha)."""
    data = SB.gh_json(["api", f"repos/{SB.REPO}/pulls/{pr['number']}"])
    return {
        "merged_at": data.get("merged_at"),
        "merge_commit_sha": data.get("merge_commit_sha"),
        "state": data.get("state"),
        "merged": bool(data.get("merged")),
    }


def classify(
    merged_at: str | None, reachable: bool, sha: str | None, reach_note: str
) -> dict:
    github_says_merged = merged_at is not None
    if github_says_merged and reachable:
        agreement = "agree_merged"
        deliberately_absent_eligible = True
    elif (not github_says_merged) and (not reachable):
        agreement = "agree_not_merged"
        deliberately_absent_eligible = False
    elif github_says_merged and not reachable:
        agreement = "disagree_github_merged_but_unreachable"
        deliberately_absent_eligible = False
    else:
        # not github-merged but commit IS ancestor (unusual; e.g. cherry-pick)
        agreement = "disagree_unreachable_claim_but_ancestor"
        deliberately_absent_eligible = False
    return {
        "github_says_merged": github_says_merged,
        "merge_commit_reachable_from_main": reachable,
        "reach_note": reach_note,
        "merge_commit_sha": sha,
        "agreement": agreement,
        "deliberately_absent_eligible": deliberately_absent_eligible,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = SB.selection_meta()
    main_ref = meta["main_ref"]
    rc, main_sha_out = SB.run(["git", "rev-parse", main_ref])
    main_sha = main_sha_out.strip() if rc == 0 else None

    sample = SB.load_sample()
    p1_by_num: dict[int, dict] = {}
    if P1_JSON.is_file():
        p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))
        p1_by_num = {r["number"]: r for r in p1.get("rows", [])}

    rows = []
    raw_lines = [
        "PROBE=AUD-0003-probe2-github-merge-reachability",
        f"STARTED_AT={started}",
        f"MAIN_REF={main_ref}",
        f"MAIN_SHA={main_sha}",
        f"SAMPLE_BOUND={meta['bound_description']}",
        f"SAMPLE_COUNT={len(sample)}",
        "",
    ]

    deliberate_findings = []
    for pr in sample:
        api = refresh_merge_fields(pr)
        sha = api.get("merge_commit_sha")
        if sha:
            reachable, reach_note = SB.is_ancestor(sha, main_ref)
        else:
            reachable, reach_note = False, "no-merge-commit-sha"
        verdict = classify(api.get("merged_at"), reachable, sha, reach_note)

        p1 = p1_by_num.get(pr["number"], {})
        differing = list(p1.get("missing_or_differing") or [])
        deliberate_paths = (
            differing if verdict["deliberately_absent_eligible"] and differing else []
        )
        # Closed-without-merge with differing paths: accidental / never-merged loss,
        # NOT "deliberate absence after merge".
        never_merged_paths = (
            differing
            if (not verdict["deliberately_absent_eligible"]) and differing
            else []
        )

        row = {
            "number": pr["number"],
            "title": pr["title"],
            "sample_class": pr["sample_class"],
            "head_sha": pr["head_sha"],
            "api": api,
            **verdict,
            "probe1_missing_or_differing_count": len(differing),
            "probe1_missing_or_differing": differing,
            "deliberately_absent_paths": deliberate_paths,
            "never_merged_or_disagree_paths": never_merged_paths,
            "ok": True,
        }
        rows.append(row)
        if deliberate_paths:
            deliberate_findings.append(
                {"number": pr["number"], "paths": deliberate_paths}
            )

        raw_lines.append(
            f"PR=#{row['number']} class={row['sample_class']} "
            f"merged_at={api.get('merged_at')} sha={(sha or '-')[:12]} "
            f"reachable={reachable} agreement={verdict['agreement']} "
            f"deliberate_eligible={verdict['deliberately_absent_eligible']} "
            f"p1_diff={len(differing)} deliberate_paths={len(deliberate_paths)}"
        )
        for p in deliberate_paths:
            raw_lines.append(f"  DELIBERATE_ABSENT: {p}")
        for p in never_merged_paths:
            raw_lines.append(f"  NON_DELIBERATE_DIFF: {p}")

    agree_merged = sum(1 for r in rows if r["agreement"] == "agree_merged")
    agree_not = sum(1 for r in rows if r["agreement"] == "agree_not_merged")
    disagree = sum(1 for r in rows if r["agreement"].startswith("disagree"))
    deliberate_path_count = sum(len(r["deliberately_absent_paths"]) for r in rows)
    deliberate_pr_count = sum(1 for r in rows if r["deliberately_absent_paths"])

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines += [
        "",
        f"AGREE_MERGED={agree_merged}",
        f"AGREE_NOT_MERGED={agree_not}",
        f"DISAGREE={disagree}",
        f"DELIBERATE_ABSENT_PRS={deliberate_pr_count}",
        f"DELIBERATE_ABSENT_PATHS={deliberate_path_count}",
        f"ENDED_AT={ended}",
    ]
    raw = "\n".join(raw_lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")

    doc = {
        "probe": "AUD-0003-probe2-github-merge-reachability",
        "ok": True,
        "started_at": started,
        "ended_at": ended,
        "main_ref": main_ref,
        "main_sha": main_sha,
        "selection": meta,
        "sample_count": len(sample),
        "sample_numbers": [r["number"] for r in rows],
        "cross_check_rule": (
            "Content is 'deliberately absent from main' only when merged_at is "
            "set AND merge_commit_sha is an ancestor of origin/main AND probe1 "
            "reports the path as still differing."
        ),
        "summary": {
            "agree_merged": agree_merged,
            "agree_not_merged": agree_not,
            "disagree": disagree,
            "deliberate_absent_prs": deliberate_pr_count,
            "deliberate_absent_paths": deliberate_path_count,
        },
        "deliberate_findings": deliberate_findings,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(raw)
    print(
        f"WROTE {OUT_JSON} deliberate_prs={deliberate_pr_count} "
        f"deliberate_paths={deliberate_path_count} disagree={disagree}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
