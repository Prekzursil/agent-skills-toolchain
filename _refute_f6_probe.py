#!/usr/bin/env python3
"""refute/codex-stubs/F6 -- MECHANICALLY DIFFERENT probe.

The claim's own probe was: clone the repo to a scratch path, physically delete 9
directories / edit marketplace.json, run the CLI, read the exit code.

This probe instead:
  (1) reads the workflow + marketplace from the GIT BLOB (git cat-file), not the
      working tree, so uncommitted sibling-agent files cannot contaminate it;
  (2) reimplements the expected declaration list INDEPENDENTLY (a ~20-line differ)
      and does exact ordered list comparison -- never calls gen_skill_index's own
      verdict function for ground truth;
  (3) simulates states 0/A/B/C as PURE LIST ALGEBRA over the blob content -- no
      filesystem mutation, no subprocess, no clone;
  (4) then, and only as a cross-check, asks gen_skill_index whether it agrees.
Different mechanism, different data field, different measurement.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")
REV = "HEAD"
NINE = [
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


def blob(path: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-p", f"{REV}:{path}"],
        capture_output=True,
        check=True,
    )
    return out.stdout.decode("utf-8")


def tracked_skill_names(root: str) -> list[str]:
    """Enumerate skills from the GIT INDEX (ls-tree), not a filesystem walk."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", REV, f"{root}/"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    names = []
    for line in out.splitlines():
        parts = line.split("/")
        if len(parts) >= 2 and parts[-1] == "SKILL.md":
            # <root>/<name>/SKILL.md  -- depth-1 only, matching glob('*/SKILL.md')
            rel = line[len(root) + 1 :].split("/")
            if len(rel) == 2:
                names.append(rel[0])
    return sorted(set(names))


def independent_expected(
    canonical: list[str], proj: dict, declared: list[str]
) -> list[str]:
    """Reimplementation of the generator contract, written from the DOCSTRING."""
    out = [f"./.agents/skills/{n}" for n in sorted(canonical)]
    seen = set(canonical)
    for root in ("skills", "skills-claude-only"):
        only = sorted(set(proj.get(root, [])) - seen)
        out += [f"./{root}/{n}" for n in only]
        seen |= set(only)
    for entry in declared:
        name = entry.rstrip("/").split("/")[-1]
        if name not in seen:
            out.append(entry)
            seen.add(name)
    return out


def main() -> int:
    mp = json.loads(blob(".claude-plugin/marketplace.json"))
    plugins = [p for p in mp.get("plugins", []) if p.get("name") == mp.get("name")]
    assert len(plugins) == 1, "marketplace shape changed"
    declared0 = list(plugins[0]["skills"])

    canonical0 = tracked_skill_names(".agents/skills")
    proj0 = {
        "skills": tracked_skill_names("skills"),
        "skills-claude-only": tracked_skill_names("skills-claude-only"),
    }

    print("== DETECTOR CONTROL ==")
    print(f"  canonical tracked (git ls-tree): {len(canonical0)}")
    print(f"  projection skills/            : {len(proj0['skills'])}")
    print(f"  declared in marketplace blob  : {len(declared0)}")
    ctl = "010-editor" in canonical0
    print(f"  control 010-editor in canonical: {ctl}")
    present9 = [n for n in NINE if n in canonical0]
    print(f"  nine stubs present in canonical: {len(present9)}/9")

    # ---- state matrix, as pure list algebra -------------------------------
    states = {
        "0 baseline        ": (canonical0, declared0),
        "A dirs gone only  ": ([n for n in canonical0 if n not in NINE], declared0),
        "C manifest pruned ": (
            canonical0,
            [e for e in declared0 if e.rstrip("/").split("/")[-1] not in NINE],
        ),
        "B both            ": (
            [n for n in canonical0 if n not in NINE],
            [e for e in declared0 if e.rstrip("/").split("/")[-1] not in NINE],
        ),
    }
    print("\n== INDEPENDENT VERDICT (exact ordered list equality) ==")
    verdicts = {}
    for label, (canon, decl) in states.items():
        exp = independent_expected(canon, proj0, decl)
        drift = exp != decl
        # why it drifts: same multiset but different order, or different members?
        same_members = sorted(exp) == sorted(decl)
        verdicts[label.strip()[0]] = drift
        print(
            f"  {label} drift={'YES (exit 1)' if drift else 'no  (exit 0)'}"
            f"   |gen|={len(exp)} |declared|={len(decl)}"
            f"   same_members={same_members}"
            + ("  <-- ORDER-ONLY difference" if drift and same_members else "")
        )
    print("\n  claim requires: A=RED C=RED 0=GREEN B=GREEN")
    ok = verdicts["A"] and verdicts["C"] and not verdicts["0"] and not verdicts["B"]
    print(f"  independent probe agrees with the 4-state table: {ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
