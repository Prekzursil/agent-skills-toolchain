"""(a) both-states control for the per-skill LICENSE-file scan;
(b) test whether the corpus's 'dark 9-skill cross-vendor council suite' is already
    catalogued among the 284 -> if not, those are legitimate EXTEND candidates.
"""

import json
import pathlib
import re
import subprocess

CORPUS = pathlib.Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
MIRROR = CORPUS / "main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
AGENTS_VAULT = pathlib.Path(r"C:/Users/Prekzursil/.agents/skills")
CLAUDE_VAULT = pathlib.Path(r"C:/Users/Prekzursil/.claude/skills")


def git(*a):
    r = subprocess.run(
        ["git", "--git-dir", str(MIRROR), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout or ""


print("=== CONTROL: per-skill LICENSE-file scan, both states ===")
# known-PRESENT (mirror): .agents/skills/figma/LICENSE.txt
rc, o = git("ls-tree", "-r", "--name-only", REF, "--", ".agents/skills/figma/")
present = [n for n in o.splitlines() if re.search(r"LICEN[CS]E", n, re.I)]
# known-ABSENT (one of ours)
rc2, o2 = git("ls-tree", "-r", "--name-only", REF, "--", ".agents/skills/mutation-check/")
absent = [n for n in o2.splitlines() if re.search(r"LICEN[CS]E", n, re.I)]
print(f"  mirror figma/ license files  = {present}  (must be non-empty)")
print(f"  mirror mutation-check/ files = {absent}   (expected empty)")
assert present, "license-file detector cannot see a known-present LICENSE"
assert not absent, "unexpected LICENSE in mutation-check"

live_present = [
    p.name for p in (AGENTS_VAULT / "figma").iterdir() if re.match(r"LICEN[CS]E", p.name, re.I)
] if (AGENTS_VAULT / "figma").is_dir() else ["<figma dir absent live>"]
live_absent = [
    p.name
    for p in (AGENTS_VAULT / "mutation-check").iterdir()
    if re.match(r"LICEN[CS]E", p.name, re.I)
] if (AGENTS_VAULT / "mutation-check").is_dir() else ["<dir absent>"]
print(f"  live figma/ license files    = {live_present}")
print(f"  live mutation-check/ files   = {live_absent}")

print("\n=== is the 'dark council suite' already catalogued among the 284? ===")
reg = json.loads(
    (CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json").read_text(encoding="utf-8")
)
cands = reg["candidates"]
ids = {c["id"] for c in cands}
names = {c["name"] for c in cands}
blob = json.dumps(cands)
DARK = [
    "codex-audit",
    "codex-brainstorm",
    "codex-coordinate",
    "codex-curate",
    "codex-discuss",
    "codex-fix",
    "codex-governance",
    "codex-review",
    "codex-triage",
]
rows = []
for d in DARK:
    as_id = f"skill-{d}" in ids
    as_name = (f"skills/{d}" in names) or (d in names)
    substr = bool(re.search(rf'"(?:id|name)"\s*:\s*"[^"]*\b{re.escape(d)}\b[^"]*"', blob))
    # where does it live?
    locs = []
    for pre in ("skills", ".agents/skills", "skills-claude-only"):
        rc3, o3 = git("ls-tree", "--name-only", REF, "--", f"{pre}/{d}/SKILL.md")
        if rc3 == 0 and o3.strip():
            rc4, o4 = git("log", "-1", "--format=%cI|%h", REF, "--", f"{pre}/{d}/SKILL.md")
            rc5, body = git("cat-file", "-p", f"{REF}:{pre}/{d}/SKILL.md")
            locs.append(
                {
                    "ref_path": f"{REF[:12]}:{pre}/{d}/SKILL.md",
                    "last_commit": o4.strip(),
                    "bytes": len(body.encode("utf-8", "replace")) if rc5 == 0 else 0,
                }
            )
    live = []
    for v, lbl in ((AGENTS_VAULT, "agents-live"), (CLAUDE_VAULT, "claude-live")):
        if (v / d / "SKILL.md").is_file():
            live.append(lbl)
    rows.append(
        {
            "name": d,
            "catalogued_as_id": as_id,
            "catalogued_as_name": as_name,
            "id_or_name_substring_hit": substr,
            "mirror_locations": locs,
            "live_locations": live,
        }
    )
    print(
        f"  {d:20s} catalogued(id={as_id}, name={as_name}, substr={substr}) "
        f"mirror={len(locs)} live={live}"
    )

# CONTROL: a name we KNOW is catalogued must report True
ctl = "skill-council" in ids
print(f"  CONTROL 'skill-council' in ids = {ctl} (must be True)")
assert ctl, "catalogue-membership detector is broken"

out = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_extend_scan.json"
)
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print(f"\nwrote {out}")
print("SUCCESS:wfa4-extend-scan")
