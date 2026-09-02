#!/usr/bin/env python3
"""B07 cockpit HUD emitter under test for TST-0246.

Production `rules/common/bash-hud-and-terminal-emit.md` and a packaged
cockpit statusline are absent from this worktree. This module is the
executable fixed-width surface: ASCII-only glyphs, pad-aligned columns,
no colour (colour tokens are TST-0245).

A width-2 / East-Asian-ambiguous / emoji-presentation glyph in any cell
is a contract failure: Windows Terminal would overlap the next field.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0246"
KIND = "b07-cockpit-fixed-width-hud"

PRODUCTION_CANDIDATES = [
    "rules/common/bash-hud-and-terminal-emit.md",
    "tools/cockpit/hud.py",
    "tools/cockpit/statusline.py",
    "tools/monitorcore/hud.py",
    "tools/monitorcore/statusline.py",
    "tools/b07/hud.sh",
    "tools/command-center/hud.py",
]

# (name, width, align) — align is '<' left or '>' right.
COLUMNS: tuple[tuple[str, int, str], ...] = (
    ("time", 8, "<"),
    ("panel", 8, "<"),
    ("cache", 7, "<"),
    ("age_s", 5, ">"),
    ("value", 8, ">"),
    ("flag", 4, "<"),
)
GAP = " "


def production_hud() -> str | None:
    for rel in PRODUCTION_CANDIDATES:
        if (REPO / rel).is_file():
            return rel
    return None


def _cell(value: object, width: int, align: str) -> str:
    text = str(value)
    if len(text) > width:
        text = text[:width]
    return f"{text:{align}{width}}"


def format_row(row: dict[str, object]) -> str:
    parts = [
        _cell(row[name], width, align) for name, width, align in COLUMNS
    ]
    return GAP.join(parts)


def row_width() -> int:
    return sum(w for _, w, _ in COLUMNS) + len(GAP) * (len(COLUMNS) - 1)


def sample_rows() -> list[dict[str, object]]:
    # Deterministic clock so receipts don't churn on re-emit of the HUD
    # body itself; emit_report stamps measured_at separately.
    stamp = "20:00:00"
    return [
        {
            "time": stamp,
            "panel": "cpu",
            "cache": "fresh",
            "age_s": 2,
            "value": "12.4%",
            "flag": "OK",
        },
        {
            "time": stamp,
            "panel": "mem",
            "cache": "fresh",
            "age_s": 2,
            "value": "41.0%",
            "flag": "OK",
        },
        {
            "time": stamp,
            "panel": "disk",
            "cache": "stale",
            "age_s": 12,
            "value": "81.2%",
            "flag": "WARN",
        },
        {
            "time": stamp,
            "panel": "jobs",
            "cache": "fresh",
            "age_s": 1,
            "value": "4",
            "flag": "OK",
        },
        {
            "time": stamp,
            "panel": "net",
            "cache": "fresh",
            "age_s": 3,
            "value": "0.8MB",
            "flag": "OK",
        },
    ]


def header_row() -> str:
    return format_row(
        {
            "time": "time",
            "panel": "panel",
            "cache": "cache",
            "age_s": "age_s",
            "value": "value",
            "flag": "flag",
        }
    )


def rule_row() -> str:
    return "-" * row_width()


def title_row() -> str:
    title = "B07 cockpit  panel-cache  fixed-width  ascii-glyphs"
    width = row_width()
    if len(title) > width:
        title = title[:width]
    return f"{title:<{width}}"


def status_row() -> str:
    body = "STATUS  ready=12  blocked=1  failed=0  budget=80/100"
    width = row_width()
    if len(body) > width:
        body = body[:width]
    return f"{body:<{width}}"


def emit_lines(rows: list[dict[str, object]] | None = None) -> list[str]:
    rows = sample_rows() if rows is None else rows
    lines = [title_row(), header_row(), rule_row()]
    lines.extend(format_row(r) for r in rows)
    lines.append(rule_row())
    lines.append(status_row())
    for line in lines:
        if len(line) != row_width():
            raise RuntimeError(f"HUD line width {len(line)} != {row_width()}: {line!r}")
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in line):
            raise RuntimeError(f"HUD line is not ASCII printable: {line!r}")
    return lines


def emit_text(rows: list[dict[str, object]] | None = None) -> str:
    return "\n".join(emit_lines(rows)) + "\n"


def plant_in_line(line: str, glyph: str, col: int) -> str:
    """Replace the single ASCII cell at col with glyph (one codepoint)."""
    if col < 0 or col >= len(line):
        raise IndexError(col)
    if len(glyph) != 1:
        raise ValueError("plant glyph must be one codepoint")
    return line[:col] + glyph + line[col + 1 :]


def main() -> int:
    text = emit_text()
    print(text, end="")
    print(
        f"# {UNIT} width={row_width()} lines={len(emit_lines())} "
        f"production={production_hud() or 'absent'} kind={KIND}",
        file=__import__("sys").stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
