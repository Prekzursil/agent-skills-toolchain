"""Parse the human-authored REGISTER.md into structured rows.

This module exists so the command-center catalog can be SEEDED by an algorithm
instead of by hand-transcription. `fan-out-contract.md` C4 is the reason: a
mechanical classification handed to judgement measured 86% accuracy with 100% of
the errors pointing at data loss, while a 40-line differ was exact. Transcribing
103 register rows by hand is exactly that shape of task.

Status is encoded by SECTION, not by a column: `R-*` rows live under
`## 1. OUTSTANDING`, `D-*` under DELIBERATELY-SKIPPED, `S-*` under SUPERSEDED,
`T-*` under SETTLED. The program tag comes from the enclosing `### 1A..1D`
heading. Both facts are load-bearing for the gate's keyword index, so they are
parsed here once and reused rather than re-derived per consumer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Section -> the disposition bucket its ids belong to.
SECTION_OUTSTANDING = "OUTSTANDING"
SECTION_SKIPPED = "DELIBERATELY-SKIPPED"
SECTION_SUPERSEDED = "SUPERSEDED"
SECTION_SETTLED = "SETTLED"

_SECTION_BY_H2 = (
    ("## 1. OUTSTANDING", SECTION_OUTSTANDING),
    ("## 2. DELIBERATELY-SKIPPED", SECTION_SKIPPED),
    ("## 3. SUPERSEDED", SECTION_SUPERSEDED),
    ("## 4. SETTLED", SECTION_SETTLED),
)

# `### 1A. Program A - toolchain / Prompt Two (32)` -> the program tag the gate
# indexes on. Keys are the sub-section letters the register actually uses.
PROGRAM_BY_SUBSECTION = {
    "1A": "A-toolchain",
    "1B": "HARNESS",
    "1C": "MONITOR",
    "1D": "B-workflow_design",
}

_H2 = re.compile(r"^##\s+\d+\.")
_H3 = re.compile(r"^###\s+(1[A-D])\.")
_ROW = re.compile(r"^\|(?!\s*-)(.+)\|\s*$")
_ID = re.compile(r"^(?:R|D|S|T)-[A-Z]?\d+$")
_OQ_ROW = re.compile(r"^\|\s*(OQ-\d+|Q\d+)\s*\|")


@dataclass(frozen=True)
class RegisterRow:
    """One parsed register row. `cells` keeps every column verbatim so a consumer
    can pick the column it needs without this parser guessing a schema for the
    four differently-shaped tables."""

    row_id: str
    section: str
    program: str
    title: str
    cells: tuple[str, ...]


@dataclass
class ParsedRegister:
    rows: list[RegisterRow] = field(default_factory=list)
    owner_questions: list[tuple[str, str]] = field(default_factory=list)

    def by_section(self, section: str) -> list[RegisterRow]:
        return [row for row in self.rows if row.section == section]

    def counts_by_prefix(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in self.rows:
            key = row.row_id.split("-", 1)[0] + "-*"
            out[key] = out.get(key, 0) + 1
        return out


def _split_row(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [cell.strip() for cell in body.split("|")]


def parse_text(text: str) -> ParsedRegister:
    """Parse register markdown. Unknown ids are skipped, never guessed."""
    parsed = ParsedRegister()
    section = ""
    program = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if _H2.match(line):
            section = ""
            program = ""
            for prefix, name in _SECTION_BY_H2:
                if line.startswith(prefix):
                    section = name
                    break
            continue
        h3 = _H3.match(line)
        if h3:
            program = PROGRAM_BY_SUBSECTION.get(h3.group(1), "")
            continue
        oq = _OQ_ROW.match(line)
        if oq and not section:
            cells = _split_row(line)
            if len(cells) >= 2 and not cells[1].startswith("---"):
                parsed.owner_questions.append((cells[0], cells[1]))
            continue
        if not section:
            continue
        match = _ROW.match(line)
        if not match:
            continue
        cells = _split_row(line)
        if not cells:
            continue
        row_id = _strip_markup(cells[0])
        if not _ID.match(row_id):
            continue
        title = _strip_markup(cells[1]) if len(cells) > 1 else ""
        parsed.rows.append(
            RegisterRow(
                row_id=row_id,
                section=section,
                program=program,
                title=title,
                cells=tuple(cells),
            )
        )
    return parsed


def parse_file(path: Path) -> ParsedRegister:
    return parse_text(Path(path).read_text(encoding="utf-8"))


def _strip_markup(cell: str) -> str:
    out = cell.replace("**", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", out)


def short_title(title: str, limit: int = 110) -> str:
    """First sentence-ish of a register title, for one-line surfaces.

    The register's titles carry their own evidence inline (anchors, byte counts),
    so a naive truncation mid-anchor reads as a broken citation. Cut at the first
    sentence boundary when one exists inside the limit."""
    text = _strip_markup(title)
    for stop in (". ", " - ", " -- "):
        idx = text.find(stop)
        if 0 < idx <= limit:
            return text[:idx].strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
