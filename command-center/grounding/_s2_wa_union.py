"""LANE SKILLS2 / item 3 -- the exact union-merge decision surface for workflow-authoring.

The deploy hop refuses a two-directionally diverged file BY DESIGN, so this can never close
by waiting. Produce the proposal, do not pick: enumerate every LIVE-ONLY line (what a merge
would DESTROY if the repo copy simply overwrote the live one) and every REPO-ONLY line (what
the live tree is missing), grouped into contiguous hunks under their owning section heading.

DETECTOR CONTROL: a differ that reports "0 live-only" would be indistinguishable from a
broken differ. So it also prints the COMMON line count and asserts both sides are non-empty
and that repo-only + live-only + common reconstructs each file's length. If the reconstruction
fails, the grouping is wrong and the hunk list may not be cited.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

REPO = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/.agents/skills/workflow-authoring/SKILL.md"
)
LIVE = Path(r"C:/Users/Prekzursil/.claude/skills.daily/workflow-authoring/SKILL.md")

# newline="" would preserve CRLF and turn a 3-line change into a whole-file diff.
rp = REPO.read_text(encoding="utf-8").splitlines()
lv = LIVE.read_text(encoding="utf-8").splitlines()

sm = difflib.SequenceMatcher(None, lv, rp, autojunk=False)
ops = sm.get_opcodes()

common = sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag == "equal")
live_only = sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag in ("delete", "replace"))
repo_only = sum(j2 - j1 for tag, _, _, j1, j2 in ops if tag in ("insert", "replace"))

print("=" * 78)
print("0. RECONSTRUCTION CONTROL")
print(f"  live lines  {len(lv):4d}  = common {common} + live-only {live_only}"
      f"  -> {'OK' if common + live_only == len(lv) else 'BROKEN'}")
print(f"  repo lines  {len(rp):4d}  = common {common} + repo-only {repo_only}"
      f"  -> {'OK' if common + repo_only == len(rp) else 'BROKEN'}")
print(f"  two-directional? live-only>0 AND repo-only>0 : "
      f"{live_only > 0 and repo_only > 0}")
if live_only == 0 or repo_only == 0:
    print("  ! not two-directional -- the premise of this item is wrong")


def section_of(lines: list[str], idx: int) -> str:
    for k in range(idx, -1, -1):
        if lines[k].startswith("#"):
            return lines[k].strip()
    return "(frontmatter/preamble)"


print()
print("=" * 78)
print("1. LIVE-ONLY HUNKS -- content that exists ONLY in ~/.claude/skills.daily")
print("   (a blind repo->live overwrite DESTROYS every line below)")
hunks = []
for tag, i1, i2, j1, j2 in ops:
    if tag in ("delete", "replace") and i2 > i1:
        sec = section_of(lv, i1)
        block = lv[i1:i2]
        hunks.append({"section": sec, "live_lines": f"{i1 + 1}-{i2}", "n": i2 - i1,
                      "text": block,
                      "repo_replacement": rp[j1:j2] if tag == "replace" else []})
for h in hunks:
    print(f"\n  --- live {h['live_lines']} ({h['n']} lines) under {h['section']}")
    for t in h["text"]:
        print(f"      | {t}")
    if h["repo_replacement"]:
        print(f"      REPO REPLACES IT WITH ({len(h['repo_replacement'])} lines):")
        for t in h["repo_replacement"][:14]:
            print(f"      > {t}")
        if len(h["repo_replacement"]) > 14:
            print(f"      > ... +{len(h['repo_replacement']) - 14} more")

print()
print("=" * 78)
print("2. REPO-ONLY SECTIONS -- what the live tree is missing (grouped by heading)")
repo_sections = {}
for tag, i1, i2, j1, j2 in ops:
    if tag in ("insert", "replace") and j2 > j1:
        for k in range(j1, j2):
            repo_sections.setdefault(section_of(rp, k), []).append(k + 1)
for sec, idxs in repo_sections.items():
    print(f"  {len(idxs):4d} lines  {sec}")

out = {
    "repo_lines": len(rp), "live_lines": len(lv), "common": common,
    "live_only": live_only, "repo_only": repo_only,
    "two_directional": live_only > 0 and repo_only > 0,
    "live_only_hunks": [
        {k: v for k, v in h.items() if k != "repo_replacement"} for h in hunks
    ],
    "repo_only_by_section": {k: len(v) for k, v in repo_sections.items()},
}
Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-WA-UNION.json"
).write_text(json.dumps(out, indent=1), encoding="utf-8")
print("\nwrote S2-WA-UNION.json")
