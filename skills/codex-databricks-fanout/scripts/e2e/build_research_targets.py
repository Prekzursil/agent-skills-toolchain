"""Generate the tiered research plan (target x lens) for the ~500-unit programme.

Two source trees, fetched differently on the node:
  * harness  — ~/.agents/harness is NOT a git repo and is NOT mirrored on the toolchain
               remote (verified 2026-07-26: `.agents/harness` absent from origin/main).
               It ships as a DBFS bundle, so we neither push canonical local state to git
               nor research a stale mirror.
  * toolchain — Prekzursil/agent-skills-toolchain, cloned from origin/main. Enumerated from
               origin/main and NOT the working tree: the local checkout is a stale, dirty,
               peer-held copy carrying an untracked CRCP auth-audit artifact that must never
               leave this box.

Budget is spent by TIER, not spread evenly: 8 lenses on a 350-line policy doc buys far less
than 8 lenses on the harness module that injects into every session. Deterministic — sorted
throughout, so a re-run reproduces the same plan.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(r"C:\Users\Prekzursil\.agents\harness")
TOOLCHAIN = Path(r"C:\Users\Prekzursil\source\agent-skills-toolchain")
OUT = Path(__file__).resolve().parent / "_R_plan.json"

BUDGET = 500
SKIP = ("__pycache__", "/backups/", "node_modules", ".bak", "/test_", "_test.py")

DEEP = (
    "bugs",
    "security",
    "cross-session",
    "test-gaps",
    "performance",
    "api-design",
    "new-venues",
    "architecture",
)
MID = ("bugs", "security", "cross-session", "test-gaps", "new-venues", "architecture")
BROAD = ("bugs", "new-venues")

# (glob, lenses, cap-on-targets). Order IS priority: earlier tiers are funded first.
TIERS: tuple[tuple[str, str, tuple[str, ...], int], ...] = (
    ("harness", "harness/*.py", DEEP, 99),
    ("hooks", "agent-self/config/hooks/*/*.py", MID, 40),
    ("mcp-tools", "tools/mcp/**/*.py", BROAD, 25),
    ("rules", "rules/common/*.md", BROAD, 20),
    ("workflows", ".github/workflows/*.yml", BROAD, 10),
    ("monitor", "tools/monitorcore/**/*.py", BROAD, 15),
    ("crcp", "tools/crcp/**/*.py", BROAD, 15),
    ("skills", ".agents/skills/*/SKILL.md", BROAD, 40),
)


def _ok(path: str) -> bool:
    return not any(m in path for m in SKIP)


def harness_files() -> list[str]:
    return sorted(
        f"harness/{p.name}" for p in HARNESS_DIR.glob("*.py") if _ok(p.as_posix())
    )


def toolchain_files() -> list[str]:
    try:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "origin/main"],
            cwd=TOOLCHAIN,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        ).stdout.splitlines()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not list origin/main: {e}", file=sys.stderr)
        return []
    return sorted(p for p in listing if _ok(p))


def main() -> int:
    harness, tool = harness_files(), toolchain_files()
    plan: list[dict] = []
    spent = 0
    report: list[tuple[str, int, int, int]] = []

    for name, glob, lenses, tcap in TIERS:
        pool = harness if name == "harness" else tool
        hits = sorted(f for f in pool if fnmatch.fnmatch(f, glob))[:tcap]
        added = 0
        for f in hits:
            if spent + len(lenses) > BUDGET:
                break
            tgt = f if name == "harness" else f"toolchain/{f}"
            plan.append({"target": tgt, "lenses": list(lenses), "tier": name})
            spent += len(lenses)
            added += len(lenses)
        report.append((name, len(hits), added, len(lenses)))

    manifest = {
        "budget": BUDGET,
        "planned_units": spent,
        "harness_bundle": "dbfs:/tmp/R-research/src/harness.tgz",
        "toolchain_clone": "https://github.com/Prekzursil/agent-skills-toolchain.git",
        "plan": plan,
    }
    OUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{'tier':12} {'targets':>8} {'lenses':>7} {'units':>7}")
    for name, nhits, added, nl in report:
        print(f"{name:12} {nhits:>8} {nl:>7} {added:>7}")
    print(f"{'TOTAL':12} {len(plan):>8} {'':>7} {spent:>7}  (budget {BUDGET})")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
