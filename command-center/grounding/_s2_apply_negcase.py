"""LANE SKILLS2 / item 4 -- add negative-case clauses BUDGET-NEUTRALLY, in all three trees.

Two measurements from this same lane constrain how item 4 can be done at all:

  * item 1: skills.daily descriptions total 115,478 chars against a render budget fitted at
    ~108,144. The fleet is ~7,300 chars OVER. So a clause is NOT free -- every added char
    pushes roughly its own length of tail description into darkness. The brief's "costs
    nothing" is refuted. Hard constraint here: len(new) <= len(old), per skill.
  * the append-only proof: `classify_pair` compares unique-line SETS, so MODIFYING the
    description line makes the file DIVERGED and `deploy-skills-daily.py` refuses it forever.
    An edit authored only in the repo can therefore never reach the loaded tree. So the edit
    is applied to all THREE trees at once, which also leaves them IDENTICAL (no new drift).

PRECONDITIONS, all enforced, refuse the skill if any fails:
  P1 the skill exists in all three trees          (never create a live-only or repo-only skill)
  P2 the current description is IDENTICAL in all three (else this is a diverged file -- leave it)
  P3 len(new) <= len(old)                         (budget-neutral or better)
  P4 the new text contains no ": " and no '"'     (stays a valid plain YAML scalar)

DETECTOR CONTROL: a deliberately BAD candidate (longer than the original) is included in the
table and MUST be refused by P3. If it is accepted, the length gate is not running and no
"budget-neutral" claim here may be cited. After --apply the script RE-READS every file from
disk and re-asserts identity across the three trees; a write that silently did not land, or
landed in only one tree, fails that check rather than being reported as success.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TREES = {
    "repo-skills": Path(r"C:/Users/Prekzursil/source/ast-integrate/skills"),
    "repo-agents": Path(r"C:/Users/Prekzursil/source/ast-integrate/.agents/skills"),
    "daily": Path(r"C:/Users/Prekzursil/.claude/skills.daily"),
}

NEW = {
    "transcribe": (
        "Transcribe audio/video to text with optional diarization and known-speaker "
        "hints, for recordings, interviews and meetings. Do NOT use when you need "
        "WORD-LEVEL timing for captions or karaoke -- use reframe-transcribe."
    ),
    "tdd-workflow": (
        "Use when writing features, fixing bugs or refactoring -- enforces TDD at 80%+ "
        "coverage (unit, integration, E2E). NOT the bare red-green loop "
        "(use test-driven-development)."
    ),
    "security-review": (
        "Use when adding authentication, handling user input, secrets, API endpoints, "
        "or payment/sensitive features -- gives a security checklist and patterns. NOT "
        "for scanning your .claude config (use security-scan)."
    ),
    "screenshot": (
        "Use when the user asks for a desktop or OS-level screenshot (full screen, a "
        "window, or a pixel region), or when tool-specific capture is unavailable. NOT "
        "for a web page or app UI (use playwright or ui-audit)."
    ),
    "e2e-testing": (
        "Playwright E2E patterns -- Page Object Model, config, CI/CD, artifacts, "
        "flaky tests. NOT for driving a live app (use webapp-testing)."
    ),
    "python-testing": (
        "pytest strategies -- fixtures, mocking, parametrization, coverage. NOT the TDD "
        "process (use test-driven-development)."
    ),
    "research-ops": (
        "Thin router for the research stack. Use for fresh facts, comparisons, "
        "enrichment, or an evidence-backed recommendation -- it picks the right research "
        "skill. NOT the full multi-source pass (use deep-research)."
    ),
    # DETECTOR CONTROL -- deliberately longer than the original. P3 MUST refuse this.
    "__control_too_long": (
        "x" * 4000
    ),
}
CONTROL = "__control_too_long"
NEW[CONTROL] = NEW[CONTROL]
CONTROL_HOST = "e2e-testing"  # the control is scored against this skill's length

DESC = re.compile(r"^description:[ \t]*(.*)$")


def read(p: Path) -> str:
    # newline="" preserves the file's own line endings; anything else rewrites the
    # whole file and turns a one-line change into a whole-file diff.
    with p.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(p: Path, text: str) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def find_desc(text: str) -> tuple[int, str, bool] | None:
    """(line index, current description, was_quoted) for the frontmatter description."""
    lines = text.split("\n")
    if not lines or not lines[0].startswith("---"):
        return None
    for i in range(1, min(len(lines), 60)):
        if lines[i].rstrip("\r").startswith("---"):
            return None
        m = DESC.match(lines[i].rstrip("\r"))
        if m:
            raw = m.group(1)
            q = len(raw) >= 2 and raw[0] == raw[-1] == '"'
            return i, (raw[1:-1] if q else raw), q
    return None


apply = "--apply" in sys.argv
rows, refusals, applied = [], [], []

for name, new in NEW.items():
    target = CONTROL_HOST if name == CONTROL else name
    found = {}
    for tag, root in TREES.items():
        p = root / target / "SKILL.md"
        if not p.is_file():
            refusals.append((name, f"P1 absent in {tag}"))
            break
        d = find_desc(read(p))
        if d is None:
            refusals.append((name, f"P1 no description line in {tag}"))
            break
        found[tag] = (p, d)
    else:
        cur = {v[1][1] for v in found.values()}
        if len(cur) != 1:
            refusals.append((name, f"P2 description differs across trees ({len(cur)} variants)"))
            continue
        old = cur.pop()
        if len(new) > len(old):
            refusals.append((name, f"P3 grows description {len(old)} -> {len(new)}"))
            continue
        if ": " in new or '"' in new:
            refusals.append((name, "P4 unsafe YAML plain scalar"))
            continue
        # The new TEXT must travel in the row. It did not in the first version, so the
        # writer below fell back to the `new` left over from THIS loop -- the 4000-char
        # control string -- and corrupted 7 skills x 3 trees. The length gate was fine;
        # the writer was reading a stale binding. Caught by the post-write re-read.
        rows.append((name, len(old), len(new), len(new) - len(old), found, new))

print("=" * 78)
print(f"{'skill':26s} {'old':>5s} {'new':>5s} {'delta':>6s}  action")
for name, lo, ln, dl, found, new_text in rows:
    print(f"{name:26s} {lo:5d} {ln:5d} {dl:+6d}  {'APPLY' if apply else 'WOULD-APPLY'}")
    assert len(new_text) == ln, f"row/text length disagree for {name}"
    if apply:
        for tag, (p, (idx, old, quoted)) in found.items():
            text = read(p)
            lines = text.split("\n")
            cr = "\r" if lines[idx].endswith("\r") else ""
            lines[idx] = f'description: {chr(34) + new_text + chr(34) if quoted else new_text}{cr}'
            write(p, "\n".join(lines))
        applied.append(name)
print()
for name, why in refusals:
    print(f"REFUSED {name:26s} {why}")

ctrl_refused = any(n == CONTROL for n, _ in refusals)
print()
print("=" * 78)
print(f"DETECTOR CONTROL: the deliberately-oversized candidate was "
      f"{'REFUSED by P3 -- length gate is live' if ctrl_refused else 'ACCEPTED -- GATE IS DEAD, no budget claim here may be cited'}")
print(f"net description-char delta: {sum(r[3] for r in rows):+d}")

if apply:
    print()
    print("POST-WRITE RE-READ -- every tree must now carry the SAME new text")
    bad = []
    for name in applied:
        target = CONTROL_HOST if name == CONTROL else name
        seen = set()
        for tag, root in TREES.items():
            d = find_desc(read(root / target / "SKILL.md"))
            seen.add(d[1] if d else None)
        ok = seen == {NEW[name]}
        print(f"  {name:26s} {'OK -- identical in all 3' if ok else 'MISMATCH'}")
        if not ok:
            bad.append(name)
    print(f"\n{'FAILED' if bad else 'SUCCESS'}:s2-negcase applied={len(applied)} mismatched={len(bad)}")

Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/S2-NEGCASE-APPLIED.json"
).write_text(
    json.dumps(
        {
            "applied": applied,
            "planned": [
                {"skill": r[0], "old": r[1], "new": r[2], "delta": r[3]} for r in rows
            ],
            "refusals": [{"skill": n, "why": w} for n, w in refusals],
            "control_refused": ctrl_refused,
            "net_delta": sum(r[3] for r in rows),
        },
        indent=1,
    ),
    encoding="utf-8",
)
