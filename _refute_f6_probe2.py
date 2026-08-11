#!/usr/bin/env python3
"""refute/codex-stubs/F6 -- probe 2: is state-A redness ROBUST or POSITIONAL?

gen_skill_index exits 1 on `marketplace_entries != generate_declarations` ONLY.
The `dangling (declared, absent)` count it prints is never consulted by the exit
code (ci/gen_skill_index.py:252). So state A goes red because the 9 carried-forward
routes move to the TAIL of the list, not because they are dangling.

Question: is there any deletion for which the tail position coincides with the
committed position, leaving the gate GREEN with dangling routes present?
"""

from __future__ import annotations

import json
import pathlib
import subprocess

REPO = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")
REV = "HEAD"


def blob(path: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{REV}:{path}"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")


def tracked(root: str) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", REV, f"{root}/"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    names = set()
    for line in out.splitlines():
        rel = line[len(root) + 1 :].split("/")
        if len(rel) == 2 and rel[1] == "SKILL.md":
            names.add(rel[0])
    return names


def expected(canon: set[str], proj: dict, declared: list[str]) -> list[str]:
    out = [f"./.agents/skills/{n}" for n in sorted(canon)]
    seen = set(canon)
    for root in ("skills", "skills-claude-only"):
        only = sorted(proj.get(root, set()) - seen)
        out += [f"./{root}/{n}" for n in only]
        seen |= set(only)
    for e in declared:
        n = e.rstrip("/").split("/")[-1]
        if n not in seen:
            out.append(e)
            seen.add(n)
    return out


mp = json.loads(blob(".claude-plugin/marketplace.json"))
plug = [p for p in mp["plugins"] if p.get("name") == mp.get("name")][0]
declared0 = list(plug["skills"])
canon0 = tracked(".agents/skills")
proj0 = {
    "skills": tracked("skills"),
    "skills-claude-only": tracked("skills-claude-only"),
}

proj_only = sorted(proj0["skills"] - canon0) + sorted(
    proj0["skills-claude-only"] - canon0 - proj0["skills"]
)
carried = [
    e
    for e in declared0
    if e.rstrip("/").split("/")[-1]
    not in (canon0 | proj0["skills"] | proj0["skills-claude-only"])
]

print("== BLOCK STRUCTURE of the generated list ==")
print(f"  block1 canonical        : {len(canon0)}")
print(f"  block2 projection-only  : {len(proj_only)}  {proj_only[:5]}")
print(f"  block3 carried-forward  : {len(carried)}  {carried[:5]}")
print(
    f"  total                   : {len(canon0) + len(proj_only) + len(carried)} vs declared {len(declared0)}"
)

# EXHAUSTIVE: delete each canonical skill one at a time; does the gate go red?
print("\n== EXHAUSTIVE single-deletion sweep (mechanical, not judgement) ==")
green_with_dangling = []
for name in sorted(canon0):
    c = canon0 - {name}
    exp = expected(c, proj0, declared0)
    if exp == declared0:  # gate GREEN
        green_with_dangling.append(name)
print(f"  canonical skills swept          : {len(canon0)}")
print(
    f"  deletions the gate MISSES (green): {len(green_with_dangling)} {green_with_dangling[:10]}"
)

# And the reverse direction: prune one marketplace entry, keep the dir.
print("\n== EXHAUSTIVE single-prune sweep (state-C direction) ==")
missed_c = []
for e in list(declared0):
    d = [x for x in declared0 if x != e]
    if expected(canon0, proj0, d) == d:
        missed_c.append(e)
print(f"  declared entries swept          : {len(declared0)}")
print(f"  prunes the gate MISSES (green)  : {len(missed_c)} {missed_c[:10]}")
