#!/usr/bin/env python3
"""AUD-0003 Probe 1: git diff <head> main --name-only, filtered to PR paths.

For each PR in the bounded sample (see sample_bound.py), compute the set of
files the PR touched, then intersect with `git diff <head_sha> origin/main
--name-only`. Paths in that intersection still differ between the PR head and
today's main — i.e. PR-touched content that did not land (or no longer matches)
on main.

Writes:
  probe1-git-diff-missing.json
  probe1-git-diff-missing.raw.txt
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE))
import sample_bound as SB  # noqa: E402

OUT_JSON = PROBE / "probe1-git-diff-missing.json"
OUT_RAW = PROBE / "probe1-git-diff-missing.raw.txt"


def analyze_pr(pr: dict, main_ref: str) -> dict:
    num = pr["number"]
    head = pr["head_sha"]
    fetched_ok, fetch_note = SB.ensure_head_fetched(head, num)
    row: dict = {
        "number": num,
        "title": pr["title"],
        "sample_class": pr["sample_class"],
        "head_sha": head,
        "base_ref": pr["base_ref"],
        "merged_at": pr.get("merged_at"),
        "head_fetched": fetched_ok,
        "fetch_note": fetch_note,
        "pr_paths": [],
        "diff_name_only": [],
        "missing_or_differing": [],
        "missing_or_differing_count": 0,
        "ok": False,
        "error": None,
    }
    if not fetched_ok:
        row["error"] = f"head-not-fetchable: {fetch_note}"
        return row
    try:
        paths = SB.pr_files(num)
        row["pr_paths"] = paths
        diff = SB.git_diff_name_only(head, main_ref)
        row["diff_name_only_count"] = len(diff)
        path_set = set(paths)
        filtered = sorted(p for p in diff if p in path_set)
        row["missing_or_differing"] = filtered
        row["missing_or_differing_count"] = len(filtered)
        row["ok"] = True
    except Exception as e:  # noqa: BLE001 — probe must record failures
        row["error"] = f"{type(e).__name__}: {e}"
    return row


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = SB.selection_meta()
    main_ref = meta["main_ref"]
    rc, main_sha_out = SB.run(["git", "rev-parse", main_ref])
    main_sha = main_sha_out.strip() if rc == 0 else None

    sample = SB.load_sample()
    rows = []
    raw_lines = [
        "PROBE=AUD-0003-probe1-git-diff-missing",
        f"STARTED_AT={started}",
        f"MAIN_REF={main_ref}",
        f"MAIN_SHA={main_sha}",
        f"SAMPLE_BOUND={meta['bound_description']}",
        f"SAMPLE_COUNT={len(sample)}",
        "",
    ]

    for pr in sample:
        row = analyze_pr(pr, main_ref)
        rows.append(row)
        raw_lines.append(
            f"PR=#{row['number']} class={row['sample_class']} "
            f"head={row['head_sha'][:12]} paths={len(row['pr_paths'])} "
            f"missing_or_differing={row['missing_or_differing_count']} "
            f"ok={row['ok']} err={row['error']}"
        )
        for p in row["missing_or_differing"]:
            raw_lines.append(f"  DIFF: {p}")

    total_findings = sum(r["missing_or_differing_count"] for r in rows)
    prs_with_findings = sum(1 for r in rows if r["missing_or_differing_count"] > 0)
    all_ok = all(r["ok"] for r in rows)

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines += [
        "",
        f"TOTAL_MISSING_OR_DIFFERING_PATHS={total_findings}",
        f"PRS_WITH_FINDINGS={prs_with_findings}",
        f"ALL_OK={all_ok}",
        f"ENDED_AT={ended}",
    ]
    raw = "\n".join(raw_lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")

    doc = {
        "probe": "AUD-0003-probe1-git-diff-missing",
        "ok": all_ok,
        "started_at": started,
        "ended_at": ended,
        "main_ref": main_ref,
        "main_sha": main_sha,
        "selection": meta,
        "sample_count": len(sample),
        "sample_numbers": [r["number"] for r in rows],
        "prs_with_findings": prs_with_findings,
        "total_missing_or_differing_paths": total_findings,
        "method": (
            "For each PR: list files via gh api pulls/{n}/files; "
            "git diff <head> origin/main --name-only; intersect with PR paths."
        ),
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(raw)
    print(f"WROTE {OUT_JSON} findings={total_findings} prs_with_findings={prs_with_findings}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
