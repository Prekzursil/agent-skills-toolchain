#!/usr/bin/env python3
"""AUD-0044 Probe 2: distinct check-run / status context names on a recent merged PR.

Selection (documented, not silent):
  - List recently closed PRs with base=main via GET /repos/{owner}/{repo}/pulls
  - Prefer the most recently merged PR whose head commit reports at least one
    check-run (fallback: first merged PR examined).
  - Collect distinct check-run names from GET .../commits/{sha}/check-runs
    and distinct status contexts from GET .../commits/{sha}/status.

Writes:
  probe2-recent-pr-check-runs.json
  probe2-recent-pr-check-runs.raw.txt
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-recent-pr-check-runs.json"
OUT_RAW = PROBE / "probe2-recent-pr-check-runs.raw.txt"
REPO = "Prekzursil/agent-skills-toolchain"
CANDIDATE_LIMIT = 10


def gh_api(path: str) -> tuple[int, str]:
    r = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def gh_api_paginated_check_runs(sha: str) -> tuple[int, list[dict], str]:
    """Fetch all check-runs for a commit (single page of 100 is enough for this repo)."""
    path = f"repos/{REPO}/commits/{sha}/check-runs?per_page=100"
    rc, raw = gh_api(path)
    if rc != 0:
        return rc, [], raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 1, [], raw
    runs = payload.get("check_runs") or []
    return 0, runs, raw


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_parts: list[str] = []

    pulls_path = f"repos/{REPO}/pulls?state=closed&per_page={CANDIDATE_LIMIT}&base=main"
    pr_rc, pr_raw = gh_api(pulls_path)
    raw_parts.append(f"=== GET {pulls_path} rc={pr_rc} ===\n")
    raw_parts.append(pr_raw)

    if pr_rc != 0:
        ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc = {
            "probe": "AUD-0044-probe2-recent-pr-check-runs",
            "started_at": started,
            "ended_at": ended,
            "ok": False,
            "error": pr_raw[:1000],
            "selection": {"rule": "most-recently-merged PR with check-runs", "chosen": None},
            "emitted_contexts": [],
            "emitted_count": 0,
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        OUT_RAW.write_text("".join(raw_parts), encoding="utf-8")
        print("probe2 FAILED: could not list PRs")
        return 1

    try:
        pulls = json.loads(pr_raw)
    except json.JSONDecodeError as e:
        print(f"probe2 FAILED: PR list JSON: {e}")
        return 1

    merged = [
        p
        for p in pulls
        if isinstance(p, dict) and p.get("merged_at") and p.get("head", {}).get("sha")
    ]
    # Sort by merged_at descending (API already roughly recent, but be explicit).
    merged.sort(key=lambda p: p.get("merged_at") or "", reverse=True)

    selection_notes: list[dict] = []
    chosen = None
    check_runs: list[dict] = []
    status_contexts: list[str] = []
    status_raw = ""
    check_raw = ""

    for pr in merged:
        number = pr["number"]
        sha = pr["head"]["sha"]
        title = pr.get("title") or ""
        merged_at = pr.get("merged_at")
        c_rc, runs, c_raw = gh_api_paginated_check_runs(sha)
        raw_parts.append(
            f"\n=== GET repos/{REPO}/commits/{sha}/check-runs (PR #{number}) rc={c_rc} ===\n"
        )
        raw_parts.append(c_raw[:20000])
        names = sorted({r.get("name") for r in runs if r.get("name")})
        selection_notes.append(
            {
                "number": number,
                "merged_at": merged_at,
                "head_sha": sha,
                "check_run_count": len(runs),
                "distinct_names": names,
                "considered": True,
            }
        )
        if c_rc == 0 and names:
            chosen = {
                "number": number,
                "title": title,
                "merged_at": merged_at,
                "head_sha": sha,
                "html_url": pr.get("html_url"),
                "merge_commit_sha": pr.get("merge_commit_sha"),
            }
            check_runs = runs
            check_raw = c_raw
            s_path = f"repos/{REPO}/commits/{sha}/status"
            s_rc, s_raw = gh_api(s_path)
            raw_parts.append(f"\n=== GET {s_path} rc={s_rc} ===\n")
            raw_parts.append(s_raw[:10000])
            status_raw = s_raw
            if s_rc == 0:
                try:
                    sp = json.loads(s_raw)
                    status_contexts = sorted(
                        {
                            st.get("context")
                            for st in (sp.get("statuses") or [])
                            if st.get("context")
                        }
                    )
                except json.JSONDecodeError:
                    status_contexts = []
            break

    if chosen is None:
        ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc = {
            "probe": "AUD-0044-probe2-recent-pr-check-runs",
            "started_at": started,
            "ended_at": ended,
            "ok": False,
            "error": "No merged PR in the candidate window produced check-runs",
            "selection": {
                "rule": (
                    f"Among the {CANDIDATE_LIMIT} most recently closed base=main PRs, "
                    "pick the most recently merged PR whose head commit has ≥1 check-run name"
                ),
                "candidates_examined": selection_notes,
                "chosen": None,
            },
            "emitted_contexts": [],
            "emitted_count": 0,
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        OUT_RAW.write_text("".join(raw_parts), encoding="utf-8")
        print("probe2 FAILED: no check-runs on recent merged PRs")
        return 1

    check_names = sorted({r.get("name") for r in check_runs if r.get("name")})
    emitted = sorted(set(check_names) | set(status_contexts))
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "probe": "AUD-0044-probe2-recent-pr-check-runs",
        "started_at": started,
        "ended_at": ended,
        "ok": True,
        "repo": REPO,
        "selection": {
            "rule": (
                f"Among the {CANDIDATE_LIMIT} most recently closed base=main PRs, "
                "pick the most recently merged PR whose head commit has ≥1 check-run name"
            ),
            "candidates_examined": selection_notes,
            "chosen": chosen,
            "why_this_pr": (
                f"PR #{chosen['number']} is the most recently merged candidate "
                f"(merged_at={chosen['merged_at']}) with "
                f"{len(check_names)} distinct check-run name(s)."
            ),
        },
        "check_run_names": check_names,
        "check_run_count": len(check_names),
        "status_contexts": status_contexts,
        "status_context_count": len(status_contexts),
        "emitted_contexts": emitted,
        "emitted_count": len(emitted),
        "check_runs_detail": [
            {
                "name": r.get("name"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "app": (r.get("app") or {}).get("slug"),
            }
            for r in check_runs
        ],
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("".join(raw_parts), encoding="utf-8")
    print(
        f"probe2 ok=True pr=#{chosen['number']} emitted_count={len(emitted)} "
        f"check_runs={len(check_names)} status_contexts={len(status_contexts)}"
    )
    for n in emitted:
        print(f"  emitted: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
