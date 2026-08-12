"""B10: MUTATION-test the deploy gate's own self-test.

A self-test that stays green when its guard is removed is a no-op dressed as a gate.  This
copies scripts/deploy-skills-daily.py, removes ONE guard per run, and REQUIRES the self-test to
go RED.  A surviving mutant is a hole in the self-test, reported as such.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
SRC = REPO / "scripts" / "deploy-skills-daily.py"

MUTANTS = {
    "P2 skill-existence guard removed": (
        "    if not (target / skill).is_dir():\n"
        '        return "P2 would resurrect a skill absent from the curated tree"\n',
        '    if False:\n        return "disabled"\n',
    ),
    "P1 safe-list replaced by the needs-merge list": (
        '    safe = list(report["safe_to_deploy"])\n',
        '    safe = list(report["safe_to_deploy"]) + list(report["needs_merge"])\n',
    ),
    "P3 prune added (deletes target-only files)": (
        "            shutil.copy2(source / rel, dst)\n",
        "            shutil.copy2(source / rel, dst)\n"
        '            for extra in list(dst.parent.glob("*")):\n'
        "                if not (source / rel).parent.joinpath(extra.name).exists():\n"
        "                    extra.unlink()\n",
    ),
}

rows = []
for name, (old, new) in MUTANTS.items():
    text = SRC.read_text(encoding="utf-8")
    if old not in text:
        rows.append((name, "SKIP", "anchor not found -- mutation could not be applied"))
        continue
    with tempfile.TemporaryDirectory() as td:
        mut = Path(td) / "mutant.py"
        # the script resolves REPO_ROOT from its own location, so keep the same depth
        pkg = Path(td) / "scripts"
        pkg.mkdir()
        mut = pkg / "deploy-skills-daily.py"
        mut.write_text(text.replace(old, new), encoding="utf-8")
        shutil.copytree(
            REPO / "ci",
            Path(td) / "ci",
            ignore=shutil.ignore_patterns("__pycache__", "tests", "harness"),
        )
        r = subprocess.run(
            [sys.executable, str(mut), "--self-test"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        killed = r.returncode != 0
        rows.append(
            (
                name,
                "KILLED" if killed else "SURVIVED",
                (r.stdout or "").strip().splitlines()[-1] if r.stdout else "",
            )
        )

print("mutation results -- every mutant MUST be KILLED:")
bad = 0
for name, verdict, tail in rows:
    print(f"  {verdict:9} {name}")
    if tail:
        print(f"            last line: {tail[:120]}")
    if verdict != "KILLED":
        bad += 1
print(
    f"\n{'SUCCESS' if bad == 0 else 'FAILED'}:deploy-gate-mutation survivors={bad}/{len(rows)}"
)
sys.exit(1 if bad else 0)
