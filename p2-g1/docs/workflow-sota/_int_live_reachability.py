#!/usr/bin/env python3
"""I1b -- is the H6 work REACHABLE from the tree Claude Code actually loads?

``~/.claude/skills.daily`` is the curated set Claude loads; the repo has no sync
path into it (``ci/check_skill_deploy_drift.py`` docstring: zero scripts write
there, the deploy is by hand).  So "committed to the repo" does not imply "an
author invoking the skill can see it".

This measures, per file, in BOTH directions -- because a one-directional read is
exactly how 31 files were nearly overwritten in an earlier wave.  A file is only
SAFE-TO-DEPLOY when it is absent live, or the repo side is a strict superset.

Detector control: a file compared against ITSELF must report IDENTICAL.  If that
control ever reports drift, the comparator is broken and no verdict here counts.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIVE_TREES = {
    "skills.daily": Path.home() / ".claude" / "skills.daily",
    "agents": Path.home() / ".agents" / "skills",
}
SKILLS = ["workflow-authoring", "workflow-foundry"]


def lines(path: Path) -> set[str]:
    return {
        ln.rstrip("\r")
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip()
    }


def classify(live: Path, repo: Path) -> str:
    if not live.exists():
        return "ABSENT-LIVE (additive deploy is lossless)"
    a, b = lines(live), lines(repo)
    if a == b:
        return "IDENTICAL"
    live_only, repo_only = len(a - b), len(b - a)
    if live_only == 0:
        return f"REPO-SUPERSET (+{repo_only} repo-only) -- deploy is lossless"
    if repo_only == 0:
        return f"LIVE-SUPERSET (+{live_only} live-only) -- deploy would DESTROY"
    return (
        f"TWO-WAY DIVERGED ({live_only} live-only vs {repo_only} repo-only)"
        " -- deploy would DESTROY; union-merge only"
    )


def main() -> int:
    control = classify(REPO / "README.md", REPO / "README.md")
    print(f"CONTROL self-vs-self: {control}")
    if control != "IDENTICAL":
        print("FAILED:reach comparator control did not hold; verdicts are void")
        return 1

    verdicts: list[str] = []
    for tree_name, tree in LIVE_TREES.items():
        if not tree.is_dir():
            print(f"  [{tree_name}] tree absent at {tree}")
            continue
        for skill in SKILLS:
            repo_skill = REPO / "skills" / skill
            for repo_file in sorted(repo_skill.rglob("*")):
                if not repo_file.is_file() or "__pycache__" in repo_file.parts:
                    continue
                rel = repo_file.relative_to(repo_skill)
                verdict = classify(tree / skill / rel, repo_file)
                verdicts.append(verdict)
                print(f"  [{tree_name}] {skill}/{rel.as_posix():<44} {verdict}")

    destroy = sum(1 for v in verdicts if "DESTROY" in v)
    absent = sum(1 for v in verdicts if v.startswith("ABSENT-LIVE"))
    identical = sum(1 for v in verdicts if v == "IDENTICAL")
    print(
        f"SUCCESS:reach files={len(verdicts)} identical={identical} "
        f"absent_live={absent} unsafe_to_deploy={destroy}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
