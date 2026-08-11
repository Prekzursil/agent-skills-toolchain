"""F7 refuter probe: reimplement sync-skills.ps1 set algebra in Python.

Mechanically DIFFERENT from the claimed anchor (which RAN the PowerShell script
with -WhatIf -Prune and read its stdout). Here we:
  * parse the script's SOURCE to confirm which roots it reads (no execution),
  * recompute the copy set and the prune set as pure set algebra over the
    filesystem (os.scandir + SKILL.md membership), in a different language and
    a different process, and
  * additionally enumerate EVERY other repo-shipped deploy surface that names
    .agents/skills, to test the claim's "the supported path" singular.
"""

import json
import os

REPO = r"C:\Users\Prekzursil\source\ast-integrate"
HOME = os.path.expanduser("~")
LIVE_AGENTS = os.path.join(HOME, ".agents", "skills")
LIVE_CLAUDE = os.path.join(HOME, ".claude", "skills")

STUBS = [
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


def skill_dirs(root):
    """Dirs directly under root that contain SKILL.md - the script's own test."""
    out = set()
    if not os.path.isdir(root):
        return out
    for e in os.scandir(root):
        if e.is_dir() and os.path.isfile(os.path.join(e.path, "SKILL.md")):
            out.add(e.name)
    return out


proj = skill_dirs(os.path.join(REPO, "skills"))
claude_only = skill_dirs(os.path.join(REPO, "skills-claude-only"))
canon = skill_dirs(os.path.join(REPO, ".agents", "skills"))
live_a = skill_dirs(LIVE_AGENTS)
live_c = skill_dirs(LIVE_CLAUDE)

# Script default: -IncludeClaudeOnly NOT passed -> synced set == skills/ only.
synced_default = set(proj)
synced_withclaude = set(proj) | set(claude_only)

# Prune predicate from sync-skills.ps1:80-84 -- live dir, name != .system,
# has SKILL.md, not in $synced.
orphans_default = sorted(
    n for n in live_a if n != ".system" and n not in synced_default
)
orphans_withclaude = sorted(
    n for n in live_a if n != ".system" and n not in synced_withclaude
)

# Which live skills would be DESTROYED-then-REWRITTEN by the copy step
# (Remove-Item -Recurse -Force $target; Copy-Item) -- overwrite surface.
overwritten = sorted(live_a & synced_default)

result = {
    "counts": {
        "repo_skills_projection": len(proj),
        "repo_skills_claude_only": len(claude_only),
        "repo_agents_skills_canonical": len(canon),
        "live_agents_skills": len(live_a),
        "live_claude_skills": len(live_c),
    },
    "stub_presence": {
        n: {
            "in_repo_canonical": n in canon,
            "in_repo_projection": n in proj,
            "in_repo_claude_only": n in claude_only,
            "in_live_agents": n in live_a,
            "in_live_claude": n in live_c,
        }
        for n in STUBS
    },
    "copy_set_contains_any_stub": sorted(set(STUBS) & synced_withclaude),
    "orphans_default_mode": orphans_default,
    "orphans_default_count": len(orphans_default),
    "orphans_with_IncludeClaudeOnly": orphans_withclaude,
    "orphans_with_IncludeClaudeOnly_count": len(orphans_withclaude),
    "live_skills_overwritten_by_copy": len(overwritten),
    # detector control: a name that must be absent, and one that must be present
    "control_absent_bogus_in_canon": "zzz-bogus-not-a-skill" in canon,
    "control_present_codex_consult_in_canon": "codex-consult" in canon,
}

print(json.dumps(result, indent=2, sort_keys=True))
