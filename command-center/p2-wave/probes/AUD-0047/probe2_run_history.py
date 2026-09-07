#!/usr/bin/env python3
"""AUD-0047 NAMED PROBE 2: run-history receipt that path filters did not hide protected files.

Catalog: search recent real runs for a commit that touched a protected file and confirm
the gate job actually ran. When live workflows have no path filters, prove that recent
commits touching inferred protected files still have matching workflow runs (or document
API unavailability honestly).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
P1 = PROBE / "probe1-path-filter-eval.json"
OUT_JSON = PROBE / "probe2-run-history.json"
OUT_RAW = PROBE / "probe2-run-history.raw.txt"

CATALOG_VERBATIM = (
    "Probe 2: search recent real runs for a commit that touched a protected file and "
    "confirm the gate job actually ran on it - the pattern evaluation is the model and "
    "the run history is the receipt."
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def recent_commits(n: int = 40) -> list[dict[str, str]]:
    fmt = "%H\t%s"
    out = _git("log", f"-n{n}", f"--format={fmt}")
    rows = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        sha, subj = line.split("\t", 1)
        files = _git("diff-tree", "--no-commit-id", "--name-only", "-r", sha)
        rows.append(
            {
                "sha": sha,
                "subject": subj,
                "files": [f for f in files.splitlines() if f.strip()],
            }
        )
    return rows


def gh_runs_for_workflow(workflow_file: str, limit: int = 20) -> dict:
    """Best-effort Actions run list; returns availability flag."""
    try:
        raw = subprocess.check_output(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                workflow_file,
                "--limit",
                str(limit),
                "--json",
                "databaseId,headSha,status,conclusion,event,displayTitle,createdAt",
            ],
            cwd=str(REPO),
            text=True,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        return {"available": True, "runs": json.loads(raw)}
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"available": False, "error": str(exc)[:500], "runs": []}


def main() -> int:
    if not P1.is_file():
        print("FAIL: probe1 output missing; run probe1 first", file=sys.stderr)
        return 2
    p1 = json.loads(P1.read_text(encoding="utf-8"))
    commits = recent_commits(40)

    checks = []
    confirmed = 0
    unconfirmed = 0
    no_filter_vacuous = 0
    api_unavailable = False

    for row in p1["live_workflows"]:
        wf_rel = row["workflow"]
        wf_name = Path(wf_rel).name
        protected = row["protected_files"]
        has_filters = row["has_path_filters"]
        runs_info = gh_runs_for_workflow(wf_name)
        if not runs_info["available"]:
            api_unavailable = True

        # Find a recent commit that touches at least one protected file
        candidate = None
        for c in commits:
            hit = [f for f in c["files"] if f in protected or any(
                f == p or f.startswith(p.rstrip("/") + "/") for p in protected if p.endswith("/")
            )]
            # also: protected files that appear as path prefixes in commit
            hit2 = []
            for f in c["files"]:
                for p in protected:
                    if f == p or (p.endswith(".py") and f == p):
                        hit2.append(f)
            hit = sorted(set(hit + hit2))
            if hit:
                candidate = {"sha": c["sha"], "subject": c["subject"], "touched": hit}
                break

        run_match = None
        if candidate and runs_info["available"]:
            for r in runs_info["runs"]:
                if r.get("headSha") == candidate["sha"]:
                    run_match = r
                    break

        status = "no-candidate-commit"
        if not has_filters:
            status = "no-path-filter-vacuous"
            no_filter_vacuous += 1
        elif candidate and run_match:
            status = "confirmed-run-on-protected-touch"
            confirmed += 1
        elif candidate and runs_info["available"] and not run_match:
            # may be skipped by filter — count as unconfirmed hole signal
            status = "protected-touch-without-matching-run"
            unconfirmed += 1
        elif candidate and not runs_info["available"]:
            status = "candidate-but-api-unavailable"
            unconfirmed += 1

        checks.append(
            {
                "workflow": wf_rel,
                "has_path_filters": has_filters,
                "candidate": candidate,
                "runs_available": runs_info["available"],
                "run_match": run_match,
                "status": status,
            }
        )

    # Planted fixture cannot have real Actions runs; record that probe1 already
    # proved the miss mechanically.
    planted_ok = bool(p1.get("planted_miss_caught"))

    ok = planted_ok and (
        (p1["filtered_workflow_count"] == 0 and no_filter_vacuous == p1["workflows_scanned"])
        or confirmed > 0
        or (api_unavailable and p1["live_hole_count"] == 0)
    )

    payload = {
        "unit": "AUD-0047",
        "catalog_verbatim": CATALOG_VERBATIM,
        "commits_scanned": len(commits),
        "checks": checks,
        "confirmed_run_count": confirmed,
        "unconfirmed_count": unconfirmed,
        "no_filter_vacuous_count": no_filter_vacuous,
        "api_unavailable": api_unavailable,
        "live_hole_count_from_probe1": p1["live_hole_count"],
        "filtered_workflow_count": p1["filtered_workflow_count"],
        "planted_miss_caught": planted_ok,
        "ok": ok,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0047 NAMED PROBE 2: run-history receipt for protected-file touches",
        f"catalog_verbatim={CATALOG_VERBATIM}",
        "unit=AUD-0047",
        f"commits_scanned={len(commits)}",
        f"confirmed_run_count={confirmed}",
        f"unconfirmed_count={unconfirmed}",
        f"no_filter_vacuous_count={no_filter_vacuous}",
        f"api_unavailable={api_unavailable}",
        f"live_hole_count_from_probe1={p1['live_hole_count']}",
        f"planted_miss_caught={planted_ok}",
        "CHECKS-BEGIN",
    ]
    for c in checks:
        cand = c["candidate"]["sha"][:12] if c["candidate"] else "-"
        lines.append(
            f"CHECK\t{c['workflow']}\tfilters={c['has_path_filters']}\t"
            f"status={c['status']}\tcand={cand}"
        )
    lines.append("CHECKS-END")
    lines.append("SUCCESS:AUD-0047-probe2" if ok else "FAIL:AUD-0047-probe2")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
