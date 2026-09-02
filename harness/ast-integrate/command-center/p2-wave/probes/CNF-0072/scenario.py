#!/usr/bin/env python3
"""Control-corpus fixtures for CNF-0072.

These files reconstruct the four historically documented M-NN namespaces as a
detector control. They are NOT claimed to be the original 07/13/17/wave trees
(those basenames are absent from this worktree). Counts here are fixture
counts, labelled control-reconstruction.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROL = HERE / "fixtures" / "control"
BACKUP = HERE / "fixtures" / "prefix-backup"

OPTION_IDS = ("M-1", "M-16", "M-29", "M-31", "M-40", "M-41")
MECH_IDS = ("MECH-1", "MECH-12", "MECH-16", "MECH-17", "MECH-19", "MECH-28", "MECH-30", "MECH-31", "MECH-38")
PRE_FIX_M = tuple(f"M-{n.split('-', 1)[1]}" for n in MECH_IDS)

OPTION_MD = """# 07-OPTION-UNIVERSE (control reconstruction)

Family M declaration sites. This is a detector control subset, not the 283-card original.

""" + "\n".join(f"## {i} option-card\n\nBody of option {i}.\n" for i in OPTION_IDS)

OPTION_JSON = {
    "family": "M",
    "note": "control reconstruction, not the original twin",
    "options": [{"id": i, "title": f"option-card-{i}"} for i in OPTION_IDS],
}

ARCH_MD = """# 13-ARCHITECTURE-CANDIDATES (control reconstruction, POST-FIX)

Re-prefixed to MECH-NN. This file must carry zero bare M-NN declaration headings.

""" + "\n".join(f"## {i} mechanism-card\n\nMechanism body {i}.\n" for i in MECH_IDS)

PRE_FIX_MD = """# 13-ARCHITECTURE-CANDIDATES (control reconstruction, PRE-FIX backup)

Bare M-NN mechanism headings as they existed before the 2026-08-07 re-prefix.

""" + "\n".join(f"## {i} mechanism-card\n\nMechanism body {i}.\n" for i in PRE_FIX_M)

DECISION_HEADER = "# 17-DECISION-LOG (control reconstruction)\n"
DECISION_LINE = (
    "The 31-way M-NN option-id collision is a live blocker. Queued as P2-09. "
    "Family M and architecture candidates still share the prefix."
)

REGISTER_HEADER = "# wave1 REGISTER (control reconstruction)\n"
REGISTER_LINE = "Mission grades: M-1 pass. Mission grade M-3 hold."

SKILL = """# deep-research skill (control reconstruction)

This skill is the Research Harness (M-16) deliverable.

Instructions refer to Research Harness (M-16) as this skill's own id.
"""

REF_BODY = "Deployed tree reference to Research Harness (M-16) for the deep-research skill.\n"

AMBIGUOUS = "See M-16.\n"
MENTION = (
    "A document quoting the collision in order to describe it, as an example: "
    "`M-16` is the token the four namespaces share. This sentence is a mention, not a use.\n"
)
ABSENT = "Forward reference to M-99 which no registry declares.\n"
MECH_ONLY = "Unambiguous mechanism token MECH-16 must not be reported as a bare M-NN hit.\n"


def _padded(header: str, line_no: int, content: str) -> str:
    lines = [header.rstrip("\n")]
    for i in range(2, line_no):
        lines.append(f"# pad-{i:04d}")
    lines.append(content.rstrip("\n"))
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def ensure_fixtures() -> Path:
    import json

    CONTROL.mkdir(parents=True, exist_ok=True)
    BACKUP.mkdir(parents=True, exist_ok=True)
    _write(CONTROL / "07-OPTION-UNIVERSE.md", OPTION_MD)
    _write(
        CONTROL / "07-OPTION-UNIVERSE.json",
        json.dumps(OPTION_JSON, indent=2, sort_keys=True) + "\n",
    )
    _write(CONTROL / "13-ARCHITECTURE-CANDIDATES.md", ARCH_MD)
    _write(BACKUP / "13-ARCHITECTURE-CANDIDATES.md", PRE_FIX_MD)
    _write(CONTROL / "17-DECISION-LOG.md", _padded(DECISION_HEADER, 175, DECISION_LINE))
    _write(CONTROL / "wave1" / "REGISTER.md", _padded(REGISTER_HEADER, 304, REGISTER_LINE))
    trees = (
        CONTROL / "wave3" / "ast-cc" / "skills" / "deep-research",
        CONTROL / "skills" / "deep-research",
    )
    for tree in trees:
        _write(tree / "SKILL.md", SKILL)
        for i in range(1, 8):
            _write(tree / "refs" / f"r{i:02d}.md", REF_BODY)
    _write(CONTROL / "ambiguous-scratch.md", AMBIGUOUS)
    _write(CONTROL / "mention-quote.md", MENTION)
    _write(CONTROL / "absent-scratch.md", ABSENT)
    _write(CONTROL / "mech-false-positive.md", MECH_ONLY)
    return CONTROL


if __name__ == "__main__":
    p = ensure_fixtures()
    print(f"SUCCESS:CNF-0072-fixtures {p}")
