"""B1: enumerate LEFT-AHEAD (live-daily strict superset) per axis, plus ui-audit status.

LEFT-AHEAD is the ONLY mechanically-safe live->repo direction: the deployed copy strictly
contains the repo copy, so copying live->repo cannot destroy repo-unique content.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
DAILY = r"C:/Users/Prekzursil/.claude/skills.daily"
VAULT = r"C:/Users/Prekzursil/.agents/skills"
REPO_AGENTS = str(REPO / ".agents" / "skills")


def run(left, right):
    out = subprocess.run(
        [sys.executable, str(REPO / "ci" / "check_skill_deploy_drift.py"),
         "--left", left, "--right", right, "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO),
    )
    return json.loads(out.stdout)


def report(tag, data):
    print(f"### {tag}")
    print("  summary:", data["summary"])
    skills = data["skills"]
    for name, info in sorted(skills.items()):
        verdict = info.get("verdict")
        if verdict in ("LEFT-AHEAD",):
            files = info.get("files", {})
            la = [f for f, v in files.items() if v in ("LEFT-AHEAD", "LEFT-ONLY")]
            print(f"  LEFT-AHEAD skill {name}: {len(la)} live-ahead/only files")
            for f in sorted(la):
                print(f"      + {f}  ({files[f]})")
    print()


for tag, left, right in (
    ("daily-vs-repoagents", DAILY, REPO_AGENTS),
    ("daily-vs-vault", DAILY, VAULT),
):
    report(tag, run(left, right))
