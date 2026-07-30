"""Purge THIS program's footprint from the shared Bolt Databricks workspace.

Scope discipline (Bolt is SHARED PRODUCTION):
  * only run_type=SUBMIT_RUN  (our one-time `jobs submit` runs; Bolt's are JOB_RUN)
  * AND run_name must match OURS_RE
  * never touches job definitions (we created none), other users' runs, or S3 logs.

Default is DRY-RUN. Pass --apply to actually delete.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

PROFILE = "bolt-datascience"
OURS_RE = re.compile(r"codex-(fanout|batch|harness)", re.I)
PAGE = 25


def db(args, timeout=180):
    return subprocess.run(
        ["databricks", *args, "--profile", PROFILE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env={**os.environ, "MSYS_NO_PATHCONV": "1"},
    )


def collect_runs() -> tuple[list[dict], int, int]:
    """Page through SUBMIT_RUN history. Returns (ours, total_seen, foreign_seen)."""
    ours, seen, foreign, offset = [], 0, 0, 0
    while True:
        r = db(
            [
                "jobs",
                "list-runs",
                "--run-type",
                "SUBMIT_RUN",
                "--limit",
                str(PAGE),
                "--offset",
                str(offset),
                "-o",
                "json",
            ]
        )
        try:
            d = json.loads(r.stdout or "[]")
        except Exception:
            break
        runs = d.get("runs", []) if isinstance(d, dict) else (d or [])
        if not runs:
            break
        seen += len(runs)
        for x in runs:
            name = str(x.get("run_name") or "")
            if OURS_RE.search(name):
                ours.append(
                    {
                        "id": x.get("run_id"),
                        "name": name,
                        "state": (x.get("state") or {}).get("life_cycle_state"),
                    }
                )
            else:
                foreign += 1
        if len(runs) < PAGE:
            break
        offset += PAGE
        if offset > 4000:  # backstop; disclose rather than silently truncate
            print("  WARN: hit 4000-run paging backstop; re-run to continue")
            break
    return ours, seen, foreign


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    mode = "APPLY" if a.apply else "DRY-RUN"
    print(f"=== purge_databricks [{mode}] ===\n")

    ours, seen, foreign = collect_runs()
    print(
        f"SUBMIT_RUN history: {seen} seen | OURS {len(ours)} | foreign {foreign} (untouched)"
    )
    active = [
        o
        for o in ours
        if o["state"] not in (None, "TERMINATED", "SKIPPED", "INTERNAL_ERROR")
    ]
    if active:
        print(f"  !! {len(active)} still non-terminal — cancel before delete:")
        for o in active:
            print("     ", o["id"], o["name"], o["state"])
    for o in ours[:8]:
        print(f"     {o['id']}  {o['name']}  [{o['state']}]")
    if len(ours) > 8:
        print(f"     ... and {len(ours) - 8} more")

    if a.apply:
        ok = fail = 0
        for o in ours:
            r = db(["jobs", "delete-run", str(o["id"])])
            if r.returncode == 0:
                ok += 1
            else:
                fail += 1
                if fail <= 3:
                    print(
                        f"  delete-run {o['id']} FAILED: {(r.stderr or '').strip()[:160]}"
                    )
        print(f"\n  runs deleted: {ok}   failed: {fail}")
    else:
        print(f"\n  [dry-run] would delete {len(ours)} runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
