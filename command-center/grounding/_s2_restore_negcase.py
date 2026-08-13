"""LANE SKILLS2 -- revert the self-inflicted description corruption in all THREE trees.

What happened: `_s2_apply_negcase.py`'s apply loop unpacked `rows` as
`(name, len_old, len_new, delta, found)` -- the new TEXT was never in the tuple -- so the
identifier `new` still referred to the LAST value of the earlier `for name, new in
NEW.items()` loop, i.e. the 4000-char `__control_too_long` string. Seven skills x three
trees = 21 SKILL.md files had their description replaced with 4000 'x'. The length gate
correctly REFUSED the control candidate; the bug is downstream of the gate, in the writer.

It was caught by that script's own POST-WRITE RE-READ check (7/7 MISMATCH, FAILED:s2-negcase),
which is the one control that compares what is ON DISK against what was intended.

Ground truth for the revert: `git show HEAD:.agents/skills/<n>/SKILL.md`. The 14 repo files
were CLEAN at HEAD before the write (measured: git status listed none of them), and the
applier's own P2 precondition had already proven skills.daily carried a byte-identical
description, so HEAD's line is the correct restore value for all three trees.

CONTROL: after the revert the script greps all three trees for the corruption signature and
must find ZERO, AND re-asserts each restored description equals HEAD's byte for byte. A
revert that reports success while a single 'xxxx' survives is a failed revert.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
TREES = {
    "repo-skills": REPO / "skills",
    "repo-agents": REPO / ".agents/skills",
    "daily": Path(r"C:/Users/Prekzursil/.claude/skills.daily"),
}
NAMES = [
    "transcribe",
    "tdd-workflow",
    "security-review",
    "screenshot",
    "e2e-testing",
    "python-testing",
    "research-ops",
]
DESC = re.compile(r"^description:[ \t]*(.*)$")
SIG = "x" * 20


def read(p: Path) -> str:
    with p.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(p: Path, s: str) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        fh.write(s)


def desc_line(text: str) -> tuple[int, str] | None:
    lines = text.split("\n")
    for i in range(1, min(len(lines), 60)):
        if lines[i].rstrip("\r").startswith("---"):
            return None
        if DESC.match(lines[i].rstrip("\r")):
            return i, lines[i].rstrip("\r")
    return None


originals = {}
for n in NAMES:
    blob = subprocess.run(
        ["git", "show", f"HEAD:.agents/skills/{n}/SKILL.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    d = desc_line(blob)
    assert d, f"no description line at HEAD for {n}"
    originals[n] = d[1]
    print(f"HEAD {n:20s} desc line {len(d[1])} chars")

print()
for n in NAMES:
    for tag, root in TREES.items():
        p = root / n / "SKILL.md"
        text = read(p)
        d = desc_line(text)
        assert d, f"{p} has no description line"
        idx = d[0]
        lines = text.split("\n")
        cr = "\r" if lines[idx].endswith("\r") else ""
        lines[idx] = originals[n] + cr
        write(p, "\n".join(lines))
    print(f"restored {n} in all 3 trees")

print()
print("=" * 78)
print("CONTROL 1 -- corruption signature must be GONE from every tree")
bad = []
for tag, root in TREES.items():
    for p in root.glob("*/SKILL.md"):
        if SIG in read(p):
            bad.append(str(p))
print(f"  files still containing the signature: {len(bad)}  {bad[:5]}")

print("CONTROL 2 -- each restored description must equal HEAD byte for byte")
mism = []
for n in NAMES:
    for tag, root in TREES.items():
        d = desc_line(read(root / n / "SKILL.md"))
        if not d or d[1] != originals[n]:
            mism.append(f"{tag}/{n}")
print(f"  mismatches vs HEAD: {len(mism)}  {mism}")

print("CONTROL 3 -- git must report the two repo trees CLEAN again")
st = subprocess.run(
    ["git", "status", "--short", "--", "skills", ".agents/skills"],
    cwd=REPO,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=True,
).stdout.strip()
print(f"  git status on skill trees: {st if st else 'CLEAN'}")

ok = not bad and not mism and not st
print(
    f"\n{'SUCCESS' if ok else 'FAILED'}:s2-restore reverted={len(NAMES)}x3 "
    f"signature_left={len(bad)} mismatch={len(mism)} git_dirty={bool(st)}"
)
raise SystemExit(0 if ok else 1)
