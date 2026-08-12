"""I2: verify the deploy actually landed where Claude Code reads, and that the ALWAYS-LOADED
description was not silently changed.

Round 1 measured a near-miss on exactly this axis: deploying a pure BODY edit would have
silently shortened two skills' descriptions by 282 and 307 chars, because the repo held a
never-deployed description cap and the live tree held the full text.  A description is
always-loaded context and the entire lexical recall surface, so a shrink is a real regression
that a body-only diff review would not show.  This asserts the delta is body-only.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
SKILL = "writing-skills/SKILL.md"
TREES = {
    "repo/.agents/skills": REPO / ".agents" / "skills" / SKILL,
    "repo/skills": REPO / "skills" / SKILL,
    "live/skills.daily": Path.home() / ".claude" / "skills.daily" / SKILL,
    "live/.claude/skills": Path.home() / ".claude" / "skills" / SKILL,
}
BASELINE_REV = "HEAD"


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def description_of(text: str) -> str:
    lines = text.split("\n")
    assert lines[0].strip() == "---", "no frontmatter"
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    for line in out:
        if line.startswith("description:"):
            return line[len("description:") :].strip()
    return ""


def main() -> int:
    bad = 0
    print("TREE PARITY (LF-normalised sha256, first 16)")
    shas = {}
    for name, p in TREES.items():
        if not p.is_file():
            print(f"  MISSING {name:22} {p}")
            bad += 1
            continue
        shas[name] = lf_sha(p)
        print(f"  {shas[name]}  {len(p.read_bytes()):>6} B  {name}")
    if len(set(shas.values())) != 1:
        print("  ! trees disagree")
        bad += 1
    else:
        print("  OK all four routes byte-identical after LF-normalisation")

    print("\nDESCRIPTION DELTA (always-loaded context -- must be ZERO)")
    before = subprocess.run(
        ["git", "show", f"{BASELINE_REV}:.agents/skills/{SKILL}"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    after = (REPO / ".agents" / "skills" / SKILL).read_text(encoding="utf-8")
    d_before, d_after = description_of(before), description_of(after)
    print(f"  before  {len(d_before):>4} chars")
    print(f"  after   {len(d_after):>4} chars")
    print(f"  delta   {len(d_after) - len(d_before):>+4} chars")
    if d_before != d_after:
        print("  ! the always-loaded description CHANGED")
        bad += 1
    else:
        print("  OK description byte-identical; the whole delta is body")

    print("\nBODY DELTA")
    print(f"  before  {len(before):>6} chars total")
    print(f"  after   {len(after):>6} chars total")
    print(f"  delta   {len(after) - len(before):>+6} chars (body only)")

    print("\nCONTROL: the detector can see a difference")
    mangled = after.replace("description:", "description: XX", 1)
    print(
        f"  a mangled description is detected as changed: "
        f"{description_of(mangled) != d_after}"
    )
    if description_of(mangled) == d_after:
        print(
            "  ! detector cannot see a description change; no verdict above may be read"
        )
        bad += 1

    print(f"\n{'SUCCESS' if not bad else 'FAILED'}:i2-verify-live problems={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
