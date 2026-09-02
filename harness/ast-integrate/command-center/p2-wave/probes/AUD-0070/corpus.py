"""Disclosed fixture estate for AUD-0070.

This sparse worktree has no 17-DECISION-LOG.md, 13-ARCHITECTURE-CANDIDATES.md,
or AUD-0068 canonical claim records. The extractor still has to run on live
spans, so this module materialises a reconstructed estate under fixtures/estate/
and records every file as corpus_role=fixture.

as_of dates are explicit in file bodies (not mtime): fixtures written today
would otherwise share a timestamp and the temporal probe would be inert.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"

AUD0068_LIVE = "command-center/audit/AUD-0068-claim-extraction-canonical.json"
LIVE_CANDIDATES = [
    "17-DECISION-LOG.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "07-OPTION-UNIVERSE.md",
    AUD0068_LIVE,
    "command-center/audit/AUD-0068-claim-extraction-canonical.json",
]


def _decision_log() -> str:
    lines = ["# 17 Decision Log (as_of 2026-07-21)", ""]
    # Line 175 must carry the known present-tense collision claim.
    while len(lines) < 174:
        lines.append(
            f"Settled entry {len(lines)}: routine note with no mechanism-prefix tokens."
        )
    lines.append(
        "The 31-way option-id collision between family M and the architecture-"
        "candidate cards is still live (present tense) and is queued as P2-09."
    )
    if len(lines) != 175:
        raise RuntimeError(f"decision log expected 175 lines, got {len(lines)}")
    return "\n".join(lines) + "\n"


def _architecture() -> str:
    lines = [
        "# 13 Architecture Candidates (as_of 2026-08-07)",
        "",
        "Mechanism cards re-prefixed to MECH-NN on 2026-08-07 (107 substitutions).",
        "This file carries zero bare M-NN tokens.",
        "",
    ]
    for n in range(1, 13):
        lines.append(f"## MECH-{n} Mechanism card {n}")
        lines.append("")
        lines.append(
            f"Architecture-candidate mechanism MECH-{n} "
            "(post-fix prefix; not a bare M- token)."
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def _option_universe() -> str:
    return (
        "# 07 Option Universe — family M (as_of 2026-06-01)\n"
        "\n"
        "Defining headings for family-M option cards. These are DEFINING sites.\n"
        "\n"
        "## M-1 Option card 1\n"
        "\n"
        "Family M option card M-1: a selectable option in the option universe.\n"
        "\n"
        "## M-16 Option card 16\n"
        "\n"
        "Family M option card M-16: a selectable option in the option universe.\n"
    )


def _wave3() -> str:
    return (
        "# Wave-3 deep-research skill (as_of 2026-07-15)\n"
        "\n"
        "Deliverable: Research Harness (M-16) is the named wave-3 output.\n"
        "Operators invoke the Research Harness (M-16) on every deep-research pass.\n"
    )


def _wave1() -> str:
    lines = ["# Wave-1 register (as_of 2026-05-01)", ""]
    while len(lines) < 20:
        lines.append(f"Register filler {len(lines)}.")
    lines.append(
        "Mission grades: M-1 (pass) and M-3 (pass) recorded for the wave-1 register."
    )
    return "\n".join(lines) + "\n"


def _note_tools_present() -> str:
    return (
        "# notes/tools-lib-present (as_of 2026-08-01)\n"
        "\n"
        "tools/lib/ is present and is the salvage home for recovered modules.\n"
    )


def _note_tools_absent() -> str:
    return (
        "# notes/tools-lib-absent (as_of 2026-08-01)\n"
        "\n"
        "tools/lib/ does not exist on this checkout.\n"
    )


def _note_lock_broken() -> str:
    return (
        "# notes/lockfile-broken (as_of 2026-06-01)\n"
        "\n"
        "lockfile integrity is broken: the recorded hash does not match the tree.\n"
    )


def _note_lock_repaired() -> str:
    return (
        "# notes/lockfile-repaired (as_of 2026-08-10)\n"
        "\n"
        "lockfile integrity was repaired on 2026-08-10; the recorded hash now matches.\n"
    )


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def materialize() -> Path:
    ESTATE.mkdir(parents=True, exist_ok=True)
    _write(ESTATE / "17-DECISION-LOG.md", _decision_log())
    _write(ESTATE / "13-ARCHITECTURE-CANDIDATES.md", _architecture())
    _write(ESTATE / "07-OPTION-UNIVERSE.md", _option_universe())
    _write(ESTATE / "wave3" / "SKILL.md", _wave3())
    _write(ESTATE / "wave1" / "REGISTER.md", _wave1())
    _write(ESTATE / "notes" / "tools-lib-present.md", _note_tools_present())
    _write(ESTATE / "notes" / "tools-lib-absent.md", _note_tools_absent())
    _write(ESTATE / "notes" / "lockfile-broken.md", _note_lock_broken())
    _write(ESTATE / "notes" / "lockfile-repaired.md", _note_lock_repaired())
    return ESTATE


def live_presence(repo: Path) -> list[dict]:
    rows = []
    for rel in LIVE_CANDIDATES:
        path = repo / rel
        present = path.is_file()
        rows.append(
            {
                "path": rel,
                "present": present,
                "bytes": path.stat().st_size if present else 0,
                "corpus_role": "live-cited",
            }
        )
    return rows


if __name__ == "__main__":
    root = materialize()
    print(f"materialized {root}")
