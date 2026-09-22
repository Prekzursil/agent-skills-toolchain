#!/usr/bin/env python3
"""P2 loop-to-green — cloud executor.

Runs ON a GitHub Actions runner. Loop (bounded):
  1. read the PR head's check runs (exclude known non-gates);
  2. if all green -> SUCCESS:<head>, exit 0;
  3. for each failing gate, look up its recipe in FIXPLAYBOOK.json;
     - recipe with "fix" -> run it (repo root), commit+push with the PAT;
     - recipe with "owner_action" or no recipe -> record and skip;
  4. no fixable failures left -> if only owner-action/none remain, exit 0 with
     a summary; else exit 1 with the unresolved list (a GitHub issue is filed
     by the workflow step, not here).

All intelligence lives in the committed playbook; this executor never guesses.
Every push uses the PAT so CI re-triggers (GITHUB_TOKEN pushes do not).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = "Prekzursil/agent-skills-toolchain"
BRANCH = "cursor/p2-loop-to-green-0db0"
MAX_ITER = int(os.environ.get("P2_MAX_ITER", "6"))
POLL_MIN = int(os.environ.get("P2_POLL_MIN", "6"))
EXCLUDED = {
    "Code scanning AI findings",
    "dependabot-auto-merge",
    "auto-merge",
    "github-advanced-security",  # GitHub platform defect: server-side model rejection; owner action
}
ROOT = Path(__file__).resolve().parents[2]


def api(path: str) -> object:
    tok = os.environ["RUNNER_PAT"]
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def checks(sha: str) -> list[dict]:
    data = api(f"repos/{REPO}/commits/{sha}/check-runs?per_page=100")
    return [
        {"name": c["name"], "status": c["status"], "conclusion": c.get("conclusion")}
        for c in data.get("check_runs", [])
        if c["name"] not in EXCLUDED and "copilot" not in c["name"].lower()
    ]


BAD_CONCLUSIONS = {"failure", "cancelled", "timed_out", "startup_failure"}


def main() -> int:
    playbook = json.loads(
        (ROOT / "command-center/p2-loop/FIXPLAYBOOK.json").read_text()
    )
    for it in range(1, MAX_ITER + 1):
        # the branch may have moved since dispatch (or since our own last push):
        # fast-forward to the remote head before judging anything
        run(
            [
                "git",
                "pull",
                "--ff-only",
                f"https://x-access-token:{os.environ['RUNNER_PAT']}@github.com/{REPO}.git",
                BRANCH,
            ]
        )
        sha = run(["git", "rev-parse", "HEAD"])[1].strip()
        # wait for terminal
        for _ in range(30):
            cs = checks(sha)
            if all(c["status"] == "completed" for c in cs):
                break
            time.sleep(POLL_MIN * 60 // 2)
        cs = checks(sha)
        failing = [
            c["name"] for c in cs if c["conclusion"] in BAD_CONCLUSIONS
        ]
        pending = [c["name"] for c in cs if c["status"] != "completed"]
        # cancelled checks also appear as completed+non-success; treat any
        # non-success terminal conclusion as needing attention (recipe or issue)
        print(
            f"[iter {it}] head={sha[:9]} failing={failing} pending={len(pending)}",
            flush=True,
        )
        if not failing and not pending:
            print(f"SUCCESS:p2-cloud-loop all gates green at {sha[:9]}")
            return 0
        fixed_any = False
        unresolved: list[str] = []
        for gate in failing:
            if gate in playbook.get("owner_action_gates", {}):
                unresolved.append(
                    f"{gate}: OWNER ACTION ({playbook['owner_action_gates'][gate][:120]})"
                )
                continue
            if gate not in playbook.get("routing", {}):
                unresolved.append(f"{gate}: no playbook recipe")
                continue
            rc, out = run(
                ["python", "command-center/p2-loop/apply_recipe.py", gate]
            )
            print(f"[fix {gate}] rc={rc}\n{out[-1500:]}", flush=True)
            if rc == 3:
                unresolved.append(f"{gate}: UNRESOLVED signature (see log above)")
                run(["git", "reset", "--hard", "HEAD"])
                continue
            if rc != 0:
                unresolved.append(f"{gate}: recipe rc={rc}")
                run(["git", "reset", "--hard", "HEAD"])
                continue
            run(["git", "add", "-A"])
            rc2, _ = run(
                ["git", "commit", "-m", f"fix(p2-cloud): {gate} per playbook recipe"]
            )
            if rc2 == 0:
                rc3, out3 = run(
                    [
                        "git",
                        "push",
                        f"https://x-access-token:{os.environ['RUNNER_PAT']}@github.com/{REPO}.git",
                        f"HEAD:{BRANCH}",
                    ]
                )
                if rc3 == 0:
                    fixed_any = True
                    print(f"[push] {gate} fix pushed", flush=True)
                else:
                    unresolved.append(f"{gate}: push failed {out3[-200:]}")
            else:
                # recipe verified green and the tree is already clean: next
                # iteration re-checks the same head; treat as progress
                fixed_any = True
        if unresolved and not fixed_any:
            print("FAILED:p2-cloud-loop unresolved: " + "; ".join(unresolved))
            return 1
    print("FAILED:p2-cloud-loop iteration budget exhausted")
    return 1


if __name__ == "__main__":
    sys.exit(main())
