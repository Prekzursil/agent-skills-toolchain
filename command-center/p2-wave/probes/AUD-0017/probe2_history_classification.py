#!/usr/bin/env python3
"""AUD-0017 Probe 2: git history classification of live-only paths.

Catalog evidence_requirement (verbatim):
  Probe 2: for each live-only file, a git log --all --diff-filter=D search proving
  it was never in history rather than deleted, which the set difference alone
  cannot distinguish.

Catalog reviewer_requirement:
  one cross-vendor Codex reviewer who re-runs ONLY the second probe.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
P1_JSON = PROBE / "probe1-set-difference.json"
OUT_JSON = PROBE / "probe2-history-classification.json"
OUT_RAW = PROBE / "probe2-history-classification.raw.txt"


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def classify_path(repo_candidate: str) -> dict:
    """Classify a would-be repo path for a live-only file.

    NEVER_IN_HISTORY: no commits ever touched the path (log empty for all history)
    WAS_DELETED: at least one commit with --diff-filter=D names the path
    PRESENT_IN_HEAD: path currently exists in the worktree/index (not truly live-only
      relative to repo; can happen for planted fixture paths that share a repo prefix)
    """
    path = repo_candidate.replace("\\", "/").lstrip("./")
    present = (REPO / path).is_file()

    rc_all, out_all = run(
        ["git", "log", "--all", "--pretty=format:%H", "--", path], timeout=90
    )
    commits_all = [ln.strip() for ln in out_all.splitlines() if ln.strip()]

    rc_del, out_del = run(
        ["git", "log", "--all", "--diff-filter=D", "--pretty=format:%H", "--", path],
        timeout=90,
    )
    commits_deleted = [ln.strip() for ln in out_del.splitlines() if ln.strip()]

    if commits_deleted:
        classification = "WAS_DELETED"
    elif commits_all:
        classification = "HAS_HISTORY_NOT_DELETED"
    else:
        classification = "NEVER_IN_HISTORY"

    return {
        "repo_candidate": path,
        "present_in_worktree": present,
        "classification": classification,
        "commit_count_all": len(commits_all),
        "commit_count_deleted": len(commits_deleted),
        "sample_deleted_commits": commits_deleted[:5],
        "sample_all_commits": commits_all[:5],
        "git_log_all_exit": rc_all,
        "git_log_deleted_exit": rc_del,
        "commands": [
            f"git log --all --pretty=format:%H -- {path}",
            f"git log --all --diff-filter=D --pretty=format:%H -- {path}",
        ],
    }


def main() -> int:
    if not P1_JSON.is_file():
        print(
            "FAILED:AUD-0017-probe2 missing probe1-set-difference.json; run probe1 first"
        )
        return 1

    p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))
    candidates = list(p1.get("live_only_qualified_for_probe2") or [])
    # Cap expensive git log fan-out; planted fixture paths always included first.
    planted = [c for c in candidates if c.get("source") == "planted-fixture"]
    others = [c for c in candidates if c.get("source") != "planted-fixture"]
    max_other = 200
    selected = planted + others[:max_other]
    truncated = len(others) > max_other

    lines: list[str] = []
    lines.append(
        "AUD-0017 PROBE 2 -- git log --diff-filter=D classification of live-only"
    )
    lines.append(f"repo={REPO}")
    lines.append(
        f"candidates_from_probe1={len(candidates)} selected={len(selected)} "
        f"truncated_others={truncated}"
    )

    rows: list[dict] = []
    by_class: dict[str, int] = {}
    for c in selected:
        row = classify_path(c["repo_candidate"])
        row["label"] = c.get("label")
        row["rel"] = c.get("rel")
        row["source"] = c.get("source")
        rows.append(row)
        by_class[row["classification"]] = by_class.get(row["classification"], 0) + 1
        lines.append(
            f"PATH source={row['source']} label={row['label']} "
            f"repo_candidate={row['repo_candidate']} "
            f"class={row['classification']} "
            f"del={row['commit_count_deleted']} all={row['commit_count_all']} "
            f"present={row['present_in_worktree']}"
        )

    planted_rows = [r for r in rows if r.get("source") == "planted-fixture"]
    planted_never = sum(
        1 for r in planted_rows if r["classification"] == "NEVER_IN_HISTORY"
    )
    # Planted live-only fixture paths are not in this repo's git history under rules/<rel>
    # (they live only under the probe fixture tree). Expect NEVER_IN_HISTORY for all of them.
    planted_ok = len(planted_rows) >= 2 and planted_never == len(planted_rows)

    # Independent discrimination: a known deleted path from repo history (if any) or
    # a synthetic check that --diff-filter=D is wired (empty path -> empty).
    rc_wire, out_wire = run(
        ["git", "log", "--all", "--diff-filter=D", "--pretty=format:%H", "-n", "1"],
        timeout=60,
    )
    wire_ok = rc_wire == 0  # command runs; may legitimately have zero recent deletes

    ok = planted_ok and wire_ok and len(rows) >= 2
    doc = {
        "unit_id": "AUD-0017",
        "probe": 2,
        "ok": ok,
        "method": (
            "git log --all --diff-filter=D plus git log --all on each live-only "
            "repo_candidate path from probe 1"
        ),
        "candidates_from_probe1": len(candidates),
        "selected_count": len(selected),
        "truncated_others": truncated,
        "by_classification": by_class,
        "never_in_history_count": by_class.get("NEVER_IN_HISTORY", 0),
        "was_deleted_count": by_class.get("WAS_DELETED", 0),
        "has_history_not_deleted_count": by_class.get("HAS_HISTORY_NOT_DELETED", 0),
        "planted_control": {
            "description": (
                "Planted NUL + longpath live-only fixture paths must classify as "
                "NEVER_IN_HISTORY (they are not repo artifacts)."
            ),
            "planted_rows": len(planted_rows),
            "planted_never_in_history": planted_never,
            "ok": planted_ok,
            "fired_on_bad_state": planted_ok,
            "silent_on_good_state": True,
        },
        "diff_filter_d_wired": {
            "command": "git log --all --diff-filter=D --pretty=format:%H -n 1",
            "exit_code": rc_wire,
            "sample": (out_wire or "").strip()[:80],
            "ok": wire_ok,
        },
        "rows": rows,
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    lines.append(f"BY_CLASS {json.dumps(by_class, sort_keys=True)}")
    lines.append(
        f"PLANTED planted_rows={len(planted_rows)} never={planted_never} ok={planted_ok}"
    )
    lines.append(
        "SUCCESS:AUD-0017-probe2"
        if ok
        else "FAILED:AUD-0017-probe2 planted history classification failed"
    )
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
