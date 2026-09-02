#!/usr/bin/env python3
"""Disclosed fixture estate for CNF-0190.

This sparse worktree does not contain 07-OPTION-UNIVERSE.md,
13-ARCHITECTURE-CANDIDATES.md, 17-DECISION-LOG.md, the wave-3 deep-research
trees, or wave1/REGISTER.md. The confirmation still has to run a live
resolver, so this module materialises a reconstructed four-namespace estate
under fixtures/estate/ and records every file as corpus_role=fixture.

Live cited paths are still probed for presence; they are not invented as
on-disk program artifacts. command-center/OPTION-ID-RESOLUTION.json and .md
are live catalog inputs on this worktree and are recorded as present, not
treated as the four namespace source documents.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ESTATE = HERE / "fixtures" / "estate"

OPTION_IDS = [f"M-{n}" for n in range(1, 34)]  # family M, 33 ids
MECH_IDS = [f"MECH-{n}" for n in range(1, 39)]  # 38 mechanism cards
SELECTED_IDS = ["M-1", "M-3", "M-5", "M-16", "M-20", "M-33", "MECH-7", "MECH-12"]

WAVE3_REL_FILES = [f"refs/r{i:02d}.md" for i in range(1, 8)]


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
        lines.append(f"Family M option card M-{n}: a selectable option in the option universe.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _option_universe_json() -> str:
    import json

    doc = {
        "family": "M",
        "count": 33,
        "ids": [{"id": f"M-{n}", "title": f"Option card {n}"} for n in range(1, 34)],
    }
    return json.dumps(doc, indent=2) + "\n"


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
            f"Architecture-candidate mechanism MECH-{n} (post-fix prefix; not a bare M- token)."
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
    if len(lines) != 175:
        raise RuntimeError(f"decision log expected 175 lines, got {len(lines)}")
    return "\n".join(lines) + "\n"


def _resolution_json() -> str:
    import json

    return (
        json.dumps(
            {
                "schema": "option-id-resolution/fixture",
                "note": (
                    "Fixture reconstruction. Live command-center/OPTION-ID-RESOLUTION.json "
                    "is absent on this worktree."
                ),
                "selected_ids": SELECTED_IDS,
                "namespaces": [
                    "option-universe",
                    "architecture-mechanisms",
                    "wave3-deliverable",
                    "wave1-mission",
                ],
            },
            indent=2,
        )
        + "\n"
    )


def _resolution_md() -> str:
    lines = [
        "# Option ID resolution (fixture)",
        "",
        "Selected ids from the option-universe family M plus two MECH controls:",
        "",
    ]
    for sid in SELECTED_IDS:
        lines.append(f"- {sid}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _skill_md() -> str:
    lines = ["# Deep research skill", ""]
    while len(lines) < 15:
        lines.append(f"Preamble line {len(lines)}.")
    lines.append("Deliverable: Research Harness (M-16) is the named wave-3 output.")
    lines.append("Operators invoke the Research Harness (M-16) on every deep-research pass.")
    lines.append("The Research Harness (M-16) artefact is duplicated across both deployed trees.")
    return "\n".join(lines) + "\n"


def _wave3_ref(n: int) -> str:
    return (
        f"# Deep-research note {n:02d}\n\n"
        f"Status: Research Harness (M-16) deployed in this duplicated tree.\n"
    )


def _register_md() -> str:
    lines = ["# Wave-1 register", ""]
    while len(lines) < 303:
        lines.append(f"Register filler {len(lines)}.")
    lines.append(
        "Mission grades: M-1 (pass) and M-3 (pass) recorded for the wave-1 register."
    )
    return "\n".join(lines) + "\n"


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def materialize() -> Path:
    """Write the reconstructed estate. Returns the estate root."""
    if ESTATE.exists():
        for child in ESTATE.rglob("*"):
            if child.is_file():
                child.unlink()
    ESTATE.mkdir(parents=True, exist_ok=True)

    _write(ESTATE / "07-OPTION-UNIVERSE.md", _option_universe_md())
    _write(ESTATE / "07-OPTION-UNIVERSE.json", _option_universe_json())
    _write(ESTATE / "13-ARCHITECTURE-CANDIDATES.md", _architecture_md())
    _write(ESTATE / "17-DECISION-LOG.md", _decision_log_md())
    _write(ESTATE / "command-center" / "OPTION-ID-RESOLUTION.json", _resolution_json())
    _write(ESTATE / "command-center" / "OPTION-ID-RESOLUTION.md", _resolution_md())

    skill = _skill_md()
    for tree in ("wave3/ast-cc/skills/deep-research", "wave3-dup/ast-cc/skills/deep-research"):
        _write(ESTATE / tree / "SKILL.md", skill)
        for rel in WAVE3_REL_FILES:
            idx = int(Path(rel).stem.replace("r", ""))
            _write(ESTATE / tree / rel, _wave3_ref(idx))

    _write(ESTATE / "wave1" / "REGISTER.md", _register_md())
    _write(
        ESTATE / "consumers" / "unambiguous-mech.md",
        "# Consumer\n\nLoad MECH-12 as specified in 13-ARCHITECTURE-CANDIDATES.\n",
    )
    _write(
        ESTATE / "consumers" / "ambiguous-m16.md",
        "# Scratch note\n\nShip M-16 next week.\n",
    )
    _write(
        ESTATE / "consumers" / "mention-quoted-collision.md",
        "# Note\n\n"
        "Quoting the collision in order to describe it: the four M-NN namespaces "
        "were re-prefixed for architecture cards, so this sentence is a mention "
        "of M-16 not a binding.\n",
    )
    return ESTATE


# Catalog input 1: live on this worktree. Not a four-namespace source document.
RESOLUTION_INDEX_PATHS = (
    "command-center/OPTION-ID-RESOLUTION.json",
    "command-center/OPTION-ID-RESOLUTION.md",
)
# Catalog inputs 2-4: the four M-NN namespace sources. Absent here; fixtures stand in.
NAMESPACE_SOURCE_PATHS = (
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
    "wave3/ast-cc/skills/deep-research/SKILL.md",
    "wave1/REGISTER.md",
)


def live_candidate_paths() -> list[str]:
    """Cited inputs from the catalog, unique, resolution-index first."""
    seen: list[str] = []
    for rel in (*RESOLUTION_INDEX_PATHS, *NAMESPACE_SOURCE_PATHS):
        if rel not in seen:
            seen.append(rel)
    return seen


def live_input_kind(rel: str) -> str:
    low = rel.replace("\\", "/").lower()
    if "option-id-resolution" in low:
        return "resolution-index"
    return "namespace-source"


def live_presence_rows() -> list[dict]:
    rows = []
    for rel in live_candidate_paths():
        path = REPO / rel
        present = path.is_file()
        rows.append(
            {
                "path": rel,
                "kind": live_input_kind(rel),
                "present": present,
                "bytes": path.stat().st_size if present else 0,
            }
        )
    return rows


def namespace_sources_present(rows: list[dict] | None = None) -> list[str]:
    rows = rows if rows is not None else live_presence_rows()
    return [r["path"] for r in rows if r.get("kind") == "namespace-source" and r.get("present")]


def resolution_index_present(rows: list[dict] | None = None) -> list[str]:
    rows = rows if rows is not None else live_presence_rows()
    return [r["path"] for r in rows if r.get("kind") == "resolution-index" and r.get("present")]


if __name__ == "__main__":
    root = materialize()
    print(f"materialized {root}")
