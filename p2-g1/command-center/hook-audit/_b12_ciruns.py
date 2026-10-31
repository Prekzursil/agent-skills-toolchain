"""B12c. Settle round 2's flagged UNVERIFIED: has hook-audit.yml ever run on a real runner?

Round 2 wired `.github/workflows/hook-audit.yml` and rated it LIKELY (55-80%) that it "will be
green on its first real GitHub run", with the honest caveat that the only evidence was a local
fresh-clone + redirected-HOME proxy, not a Linux runner. That is now settleable by asking GitHub.

The prediction was WRONG and this probe records it rather than quietly noting the current green:
the workflow was RED on its first runs and needed two further fixes (fetch-depth 0 for a pinned
historical blob, and a control pinning a Windows path frozen in a blob). A local proxy that cannot
model a shallow checkout or a case-sensitive Linux path is not evidence about a runner.

CONTROLS:
    C1 gh_reachable        the CLI returned parseable rows -- an auth/network failure is a
                           DETECTOR failure, never a verdict of "no runs".
    C2 both_states_present the history contains BOTH success and failure rows. If every row were
                           green the probe could not distinguish "always passed" from "cannot see
                           failures", which is the shape that makes a green meaningless.

Re-runnable:  python command-center/hook-audit/_b12_ciruns.py
Evidence:     command-center/hook-audit/B12-CIRUNS.json
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "B12-CIRUNS.json"
FIELDS = "conclusion,headSha,createdAt,displayTitle,event"


def gh_runs(limit: int = 30) -> list[dict]:
    proc = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--workflow=hook-audit.yml",
            f"--limit={limit}",
            "--json",
            FIELDS,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        return []
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return rows if isinstance(rows, list) else []


def main() -> int:
    rows = gh_runs()
    concl = [str(r.get("conclusion") or "") for r in rows]
    n_success = concl.count("success")
    n_failure = concl.count("failure")

    # Rows come back newest-first. The streak is the run of greens at the head.
    streak = 0
    for c in concl:
        if c == "success":
            streak += 1
        else:
            break

    controls = {
        "C1_gh_reachable": bool(rows),
        "C2_both_states_present": n_success > 0 and n_failure > 0,
    }

    blob = {
        "probe": "_b12_ciruns.py",
        "workflow": ".github/workflows/hook-audit.yml",
        "runs_seen": len(rows),
        "n_success": n_success,
        "n_failure": n_failure,
        "current_green_streak": streak,
        "has_ever_run_on_a_real_runner": bool(rows),
        "was_green_on_its_first_runs": n_failure == 0,
        "newest": rows[0] if rows else None,
        "oldest_seen": rows[-1] if rows else None,
        "controls": controls,
    }
    OUT.write_text(json.dumps(blob, indent=1) + "\n", encoding="utf-8")

    if not controls["C1_gh_reachable"]:
        print(
            "FAILED:b12-ciruns gh returned no parseable rows -- detector failure, not a verdict"
        )
        return 2
    print(
        f"runs={len(rows)} success={n_success} failure={n_failure} "
        f"green_streak={streak} first_runs_green={n_failure == 0}"
    )
    if not controls["C2_both_states_present"]:
        print(
            "WARN:b12-ciruns history shows only one state -- green is not distinguishable"
        )
    print("SUCCESS:b12-ciruns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
