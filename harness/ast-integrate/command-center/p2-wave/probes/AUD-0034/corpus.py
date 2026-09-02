#!/usr/bin/env python3
"""Disclosed fixture estate for AUD-0034.

Cited live inputs (07-OPTION-UNIVERSE, 13-ARCHITECTURE-CANDIDATES, docs 16/18/19,
17-DECISION-LOG, wave-3 deep-research, wave1/REGISTER) are absent on this
worktree. The resolver still has to run, so this module materialises a
reconstructed four-namespace estate plus the 58 unsettled bare M-NN references
and the historical pre-fix collision control. Every file is corpus_role=fixture.
Live cited paths are still probed for presence; they are not invented as
on-disk program artifacts.
"""
from __future__ import annotations

from pathlib import Path

from constants import (
    DOC16_REL,
    DOC18_REL,
    DOC19_REL,
    EXPECTED_UNSETTLED,
    HISTORICAL_COLLISION_IDS,
    LIVE_CANDIDATE_PATHS,
    OPTION_IDS,
)

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"

WAVE3_REF_FILES = [f"refs/r{i:02d}.md" for i in range(1, 8)]


def _option_universe_md() -> str:
    lines = [
        "# 07 Option Universe — family M",
        "",
        "Defining headings for 33 option cards. These are DEFINING sites.",
        "",
    ]
    for n in range(1, 34):
        lines.append(f"## M-{n} Option card {n}")
        lines.append("")
        lines.append(
            f"Family M option card M-{n}: a selectable option in the option universe."
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def _architecture_md() -> str:
    lines = [
        "# 13 Architecture Candidates",
        "",
        "Mechanism cards re-prefixed to MECH-NN on 2026-08-07 (107 substitutions).",
        "This file carries zero bare M-NN tokens.",
        "",
    ]
    for n in range(1, 39):
        lines.append(f"## MECH-{n} Mechanism card {n}")
        lines.append("")
        lines.append(
            f"Architecture-candidate mechanism MECH-{n} "
            "(post-fix prefix; not a bare M- token)."
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def _decision_log_md() -> str:
    lines = ["# 17 Decision Log", ""]
    while len(lines) < 174:
        lines.append(
            f"Settled entry {len(lines)}: routine note with no mechanism-prefix tokens."
        )
    lines.append(
        "The 31-way option-id collision between family M and the architecture-candidate "
        "cards is still live (present tense) and is queued as P2-09."
    )
    return "\n".join(lines) + "\n"


def _unsettled_ids() -> list[str]:
    """58 bare M-NN references whose numbers exist in both colliding namespaces."""
    ids: list[str] = []
    cycle = HISTORICAL_COLLISION_IDS  # M-1 .. M-31, all in both registries
    while len(ids) < EXPECTED_UNSETTLED:
        ids.append(cycle[len(ids) % len(cycle)])
    return ids


def _unsettled_doc(title: str, ids: list[str], start: int) -> str:
    lines = [
        f"# {title}",
        "",
        "Bare M-NN references below carry no surrounding cue that would "
        "assign a namespace.",
        "",
    ]
    for i, token in enumerate(ids, start=start):
        lines.append(f"{i}. Ship {token} next week.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _split_unsettled() -> tuple[list[str], list[str], list[str]]:
    ids = _unsettled_ids()
    return ids[:20], ids[20:40], ids[40:58]


def _historical_option_md() -> str:
    lines = [
        "# Historical pre-fix option-universe collision cards",
        "",
        "Each historically colliding id in its pre-fix form, with the option token.",
        "",
    ]
    for token in HISTORICAL_COLLISION_IDS:
        lines.append(f"## {token}")
        lines.append("")
        lines.append(f"Pre-fix option card {token} as declared in the option universe.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _historical_mech_md() -> str:
    lines = [
        "# Historical pre-fix architecture-candidate collision cards",
        "",
        "Each historically colliding id in its pre-fix form, with the mechanism token.",
        "",
    ]
    for token in HISTORICAL_COLLISION_IDS:
        lines.append(f"## {token}")
        lines.append("")
        lines.append(
            f"Pre-fix mechanism card {token} as declared among architecture candidates."
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def _skill_md() -> str:
    lines = ["# Deep research skill", ""]
    while len(lines) < 15:
        lines.append(f"Preamble line {len(lines)}.")
    lines.append("Deliverable: Research Harness (M-16) is the named wave-3 output.")
    lines.append(
        "Operators invoke the Research Harness (M-16) on every deep-research pass."
    )
    return "\n".join(lines) + "\n"


def _register_md() -> str:
    lines = ["# Wave-1 register", ""]
    while len(lines) < 303:
        lines.append(f"Register filler {len(lines)}.")
    lines.append(
        "Mission-grade scores: M-1 (pass) and M-3 (pass) recorded for the wave-1 register."
    )
    return "\n".join(lines) + "\n"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def materialize() -> Path:
    if ESTATE.exists():
        for child in ESTATE.rglob("*"):
            if child.is_file():
                child.unlink()
    ESTATE.mkdir(parents=True, exist_ok=True)

    _write(ESTATE / "07-OPTION-UNIVERSE.md", _option_universe_md())
    _write(ESTATE / "13-ARCHITECTURE-CANDIDATES.md", _architecture_md())
    _write(ESTATE / "17-DECISION-LOG.md", _decision_log_md())

    d16, d18, d19 = _split_unsettled()
    _write(ESTATE / DOC16_REL, _unsettled_doc("16 Grill Queue", d16, 1))
    _write(ESTATE / DOC18_REL, _unsettled_doc("18 Open Unknowns And Probes", d18, 21))
    _write(ESTATE / DOC19_REL, _unsettled_doc("19 Substance Audit Blueprints", d19, 41))

    _write(
        ESTATE / "historical" / "pre-fix-option-collisions.md",
        _historical_option_md(),
    )
    _write(
        ESTATE / "historical" / "pre-fix-mechanism-collisions.md",
        _historical_mech_md(),
    )

    skill = _skill_md()
    for tree in (
        "wave3/ast-cc/skills/deep-research",
        "wave3-dup/ast-cc/skills/deep-research",
    ):
        _write(ESTATE / tree / "SKILL.md", skill)
        for i, rel in enumerate(WAVE3_REF_FILES, start=1):
            _write(
                ESTATE / tree / rel,
                f"# Deep-research note {i:02d}\n\n"
                f"Status: Research Harness (M-16) deployed in this duplicated tree.\n",
            )

    _write(ESTATE / "wave1" / "REGISTER.md", _register_md())
    _write(
        ESTATE / "consumers" / "synthetic-no-token.md",
        "# Synthetic control\n\nShip M-12 next week.\n",
    )
    _write(
        ESTATE / "consumers" / "absent-id.md",
        "# Absent id control\n\nSee M-99 immediately.\n",
    )
    _write(
        ESTATE / "consumers" / "resolves-many.md",
        "# Dual-token control\n\nThe option mechanism pairing for M-8 is recorded here.\n",
    )
    _write(
        ESTATE / "consumers" / "unambiguous-mech.md",
        "# Consumer\n\nLoad MECH-12 as specified in 13-ARCHITECTURE-CANDIDATES.\n",
    )
    _write(
        ESTATE / "consumers" / "unambiguous-option.md",
        "# Consumer\n\nSelect option card M-20 from the option universe.\n",
    )
    _write(
        ESTATE / "consumers" / "mention-quoted-collision.md",
        "# Note\n\n"
        "Quoting the collision in order to describe it: the four M-NN namespaces "
        "were re-prefixed for architecture cards, so this sentence is a mention "
        "of M-16 not a binding.\n",
    )
    return ESTATE


def live_presence(repo: Path) -> list[dict]:
    rows = []
    for rel in LIVE_CANDIDATE_PATHS:
        path = repo / rel
        present = path.is_file()
        rows.append(
            {
                "path": rel,
                "present": present,
                "bytes": path.stat().st_size if present else 0,
            }
        )
    return rows


def unsettled_plan() -> dict:
    d16, d18, d19 = _split_unsettled()
    return {
        DOC16_REL: d16,
        DOC18_REL: d18,
        DOC19_REL: d19,
        "all": d16 + d18 + d19,
        "option_ids": list(OPTION_IDS),
        "historical": list(HISTORICAL_COLLISION_IDS),
    }


if __name__ == "__main__":
    root = materialize()
    print(f"materialized {root}")
    print(f"unsettled {len(unsettled_plan()['all'])}")
