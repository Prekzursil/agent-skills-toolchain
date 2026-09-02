#!/usr/bin/env python3
"""Deterministic reconstructed estate for CC-0021.

Named live inputs (07-OPTION-UNIVERSE.md, 13-ARCHITECTURE-CANDIDATES.md,
wave3/ast-cc/..., wave1/REGISTER.md) are absent from this worktree. The
fixture reconstructs the four namespaces the catalog names, using the
33/38/31/7/2 partition as the id-set construction (re-measured after write,
not inherited as a live-estate count).
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

# Option universe family M: ids 1..33 (33). Mechanisms: 1..31 and 34..40 (38).
# Intersection 1..31 (31); option-only {32,33} (2); mech-only {34..40} (7).
OPTION_IDS = list(range(1, 34))
MECH_IDS = list(range(1, 32)) + list(range(34, 41))
HARNESS_ID = 16
MISSION_IDS = [1, 3]

TREE_A = "fixtures/estate/wave3/ast-cc"
TREE_B = "fixtures/estate/skills-deployed/ast-cc"
HARNESS_FILES = [
    ("skills/deep-research/SKILL.md", 2, True),
    ("skills/deep-research/README.md", 1, False),
    ("skills/deep-research/refs/alpha.md", 1, False),
    ("skills/deep-research/refs/beta.md", 1, False),
    ("skills/deep-research/refs/gamma.md", 1, False),
    ("skills/deep-research/refs/delta.md", 1, False),
    ("skills/deep-research/refs/epsilon.md", 1, False),
    ("skills/deep-research/refs/zeta.md", 2, False),
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _harness_body(n_refs: int, skill_line16: bool) -> str:
    hid = HARNESS_ID
    ns = "<!-- option-id-namespace: research-harness -->"
    if skill_line16:
        lines = [ns]
        while len(lines) < 15:
            lines.append("")
        lines.append(f"Research Harness (M-{hid})")
        written = 1
        while written < n_refs:
            lines.append(f"Index entry for deliverable M-{hid}.")
            written += 1
        return "\n".join(lines) + "\n"
    lines = [ns, "# harness references"]
    for i in range(n_refs):
        lines.append(f"Reference {i + 1} to deliverable M-{hid}.")
    return "\n".join(lines) + "\n"


def _option_md() -> str:
    lines = [
        "<!-- option-id-namespace: option-universe-family-M -->",
        "# Option universe family M",
        "",
        "Declaration site pattern: ATX heading `### M-<n>`.",
    ]
    for n in OPTION_IDS:
        lines.append(f"### M-{n}")
        lines.append(f"Option card {n} in family M.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _option_json() -> str:
    import json

    doc = {
        "option_id_namespace": "option-universe-family-M",
        "family": "M",
        "ids": [{"id": f"M-{n}", "title": f"option card {n}"} for n in OPTION_IDS],
    }
    return json.dumps(doc, indent=2) + "\n"


def _arch_md() -> str:
    lines = [
        "<!-- option-id-namespace: architecture-mechanism -->",
        "# Architecture candidates",
        "",
        "Re-prefixed 2026-08-07. This file holds MECH cards only.",
        "Declaration site pattern: ATX heading `### MECH-<n>`.",
        "",
    ]
    for n in MECH_IDS:
        lines.append(f"### MECH-{n}")
        lines.append(f"Mechanism card MECH-{n}.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _register_md() -> str:
    lines = ["<!-- option-id-namespace: wave1-mission-grade -->"]
    for i in range(2, 304):
        lines.append(f"; padding line {i}")
    a, b = MISSION_IDS
    lines.append(f"Mission grades: M-{a} (pass) and M-{b} (fail).")
    assert len(lines) == 304
    return "\n".join(lines) + "\n"


def _decision_log() -> str:
    hid = HARNESS_ID
    lines = ["<!-- option-id-namespace: mention-only -->"]
    for i in range(2, 175):
        lines.append(f"; padding line {i}")
    lines.append(
        f"The 31-way option-id collision (including M-{hid}) is live. Queued as P2-09."
    )
    assert len(lines) == 175
    return "\n".join(lines) + "\n"


def _mention_md() -> str:
    hid = HARNESS_ID
    return (
        "<!-- option-id-namespace: mention-only -->\n"
        "# Quoting the collision in order to describe it\n"
        "\n"
        f"A document that quotes the collision (option-universe `{f'M-{hid}'}` versus "
        "the already-re-prefixed mechanism card) is a MENTION, not a live unresolved "
        "identifier.\n"
        "\n"
        "Fenced example of the historical token:\n"
        "\n"
        "```\n"
        f"M-{hid}\n"
        "```\n"
    )


def _planted_md() -> str:
    hid = HARNESS_ID
    return f"TODO: implement M-{hid} next.\n"


def ensure_corpus() -> dict:
    """Write the fixture estate. Idempotent."""
    estate = HERE / "fixtures" / "estate"
    mention = HERE / "fixtures" / "mention"
    planted = HERE / "fixtures" / "planted"

    _write(estate / "07-OPTION-UNIVERSE.md", _option_md())
    _write(estate / "07-OPTION-UNIVERSE.json", _option_json())
    _write(estate / "13-ARCHITECTURE-CANDIDATES.md", _arch_md())
    _write(estate / "17-DECISION-LOG.md", _decision_log())
    _write(estate / "wave1" / "REGISTER.md", _register_md())

    written_harness = []
    for tree in (TREE_A, TREE_B):
        for rel, n_refs, skill in HARNESS_FILES:
            path = HERE / tree / rel
            _write(path, _harness_body(n_refs, skill))
            written_harness.append((tree + "/" + rel).replace("\\", "/"))

    _write(mention / "quoting-collision.md", _mention_md())
    _write(planted / "scratch-bare-token.md", _planted_md())

    return {
        "estate": str(estate),
        "mention": str(mention),
        "planted": str(planted),
        "harness_files": written_harness,
        "option_ids": list(OPTION_IDS),
        "mech_ids": list(MECH_IDS),
        "harness_id": HARNESS_ID,
        "mission_ids": list(MISSION_IDS),
    }


def estate_root() -> Path:
    return HERE / "fixtures" / "estate"


def mention_root() -> Path:
    return HERE / "fixtures" / "mention"


def planted_file() -> Path:
    return HERE / "fixtures" / "planted" / "scratch-bare-token.md"


def arch_file() -> Path:
    return estate_root() / "13-ARCHITECTURE-CANDIDATES.md"


def option_md() -> Path:
    return estate_root() / "07-OPTION-UNIVERSE.md"


def tree_paths() -> tuple[Path, Path]:
    return HERE / TREE_A, HERE / TREE_B


if __name__ == "__main__":
    info = ensure_corpus()
    print("corpus", len(info["harness_files"]), "harness files")
