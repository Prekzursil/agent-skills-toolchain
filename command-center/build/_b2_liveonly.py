"""B2: enumerate LIVE-ONLY (LEFT-ONLY-FILE) and LEFT-AHEAD content on the repo axis.

These are the two mechanically-safe live->repo directions:
  LEFT-ONLY-FILE : the file exists only in the deployed tree -> copying it into the repo
                   cannot destroy anything (the repo has no bytes there at all).
  LEFT-AHEAD     : the deployed copy strictly contains the repo copy -> copying is a superset.

Everything else (DIVERGED) needs a read-both-sides merge and is listed separately, not copied.
"""
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")
REPO_AGENTS = REPO / ".agents" / "skills"

# a .bak-<tag> DIRECTORY leaks through ci/check_skill_deploy_drift.py's is_noise(),
# which only tests the LEAF for the ".bak-" infix.  Filter it here too so the
# reconcile plan is not polluted by backup snapshots.
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".db", ".sqlite", ".zip", ".pdf", ".ico", ".webp"}


def is_bak(rel: str) -> bool:
    return any(".bak-" in part for part in rel.split("/"))


out = subprocess.run(
    [sys.executable, str(REPO / "ci" / "check_skill_deploy_drift.py"),
     "--left", str(DAILY), "--right", str(REPO_AGENTS), "--json"],
    capture_output=True, text=True, encoding="utf-8", cwd=str(REPO),
)
data = json.loads(out.stdout)

buckets = defaultdict(list)
for skill, info in sorted(data["skills"].items()):
    for rel, verdict in sorted(info.get("files", {}).items()):
        full = f"{skill}/{rel}"
        if is_bak(full):
            buckets["EXCLUDED-bak-dir"].append(full)
            continue
        if Path(rel).suffix.lower() in BINARY_EXT:
            buckets[f"BINARY-{verdict}"].append(full)
            continue
        buckets[verdict].append(full)

print("== bucket counts (repo axis: live daily LEFT vs repo .agents/skills RIGHT) ==")
for k in sorted(buckets):
    print(f"  {k:24} {len(buckets[k])}")

plan = {k: buckets[k] for k in buckets}
(REPO / "command-center" / "build" / "B2-reconcile-buckets.json").write_text(
    json.dumps(plan, indent=1, sort_keys=True), encoding="utf-8"
)

print("\n== LEFT-ONLY-FILE (safe live->repo additions), by skill ==")
byskill = defaultdict(int)
for f in buckets.get("LEFT-ONLY-FILE", []):
    byskill[f.split("/")[0]] += 1
for s, n in sorted(byskill.items(), key=lambda kv: -kv[1]):
    print(f"  {n:4}  {s}")

print("\n== LEFT-AHEAD files (safe live->repo supersets) ==")
for f in buckets.get("LEFT-AHEAD", []):
    print("  +", f)
