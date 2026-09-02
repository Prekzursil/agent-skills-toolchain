#!/usr/bin/env python3
"""Token extractor for option-id namespaces.

Counts come from executing these printed regexes, not from inherited prose.
Two independent constructions (primary vs reviewer) must agree on the same
(path, line, number, kind) set.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

# Printed in the receipt. Primary uses lookbehind/lookahead; reviewer uses \b.
REGEX_M_PRIMARY = r"(?<![A-Za-z0-9_])M-(\d{1,3})(?!\d)"
REGEX_M_REVIEWER = r"\bM-(\d{1,3})\b"
REGEX_MECH_PRIMARY = r"(?<![A-Za-z0-9_])MECH-(\d{1,3})(?!\d)"
REGEX_MECH_REVIEWER = r"\bMECH-(\d{1,3})\b"

DECL_HEADER_M = r"^#{1,6}\s+M-(\d{1,3})\b"
DECL_HEADER_MECH = r"^#{1,6}\s+MECH-(\d{1,3})\b"
DECL_JSON_ID_M = r'"id"\s*:\s*"M-(\d{1,3})"'
DECL_HARNESS = r"Research Harness \(M-(\d{1,3})\)"
DECL_MISSION_LINE = r"Mission grades: M-(\d+)"

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv", ".mypy_cache"}
TEXT_SUFFIX = {".md", ".json", ".txt", ".yml", ".yaml"}


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    column: int
    token: str
    number: int
    kind: str
    snippet: str
    in_fence: bool

    def key(self) -> tuple:
        return (self.path, self.line, self.number, self.kind)

    def as_dict(self) -> dict:
        return asdict(self)


def _compile(which: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    if which == "reviewer":
        return re.compile(REGEX_M_REVIEWER), re.compile(REGEX_MECH_REVIEWER)
    return re.compile(REGEX_M_PRIMARY), re.compile(REGEX_MECH_PRIMARY)


def iter_text_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    out: list[Path] = []
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if p.suffix.lower() not in TEXT_SUFFIX:
            continue
        if p.stat().st_size > 8_000_000:
            continue
        out.append(p)
    return sorted(out)


def extract(
    root: Path,
    *,
    kind: str = "both",
    which: str = "primary",
    path_base: Path | None = None,
) -> list[Hit]:
    """Extract M-NN and/or MECH-NN tokens under root.

    `path_base` is the prefix stripped to form Hit.path; default is `root`
    for a directory and `root.parent` for a file.
    """
    rx_m, rx_mech = _compile(which)
    files = iter_text_files(root)
    if root.is_file():
        base = path_base or root.parent
    else:
        base = path_base or root
    hits: list[Hit] = []
    for fp in files:
        try:
            rel = fp.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            rel = fp.as_posix()
        text = fp.read_text(encoding="utf-8", errors="replace")
        in_fence = False
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            pairs: list[tuple[str, re.Pattern[str]]] = []
            if kind in {"M", "both"}:
                pairs.append(("M", rx_m))
            if kind in {"MECH", "both"}:
                pairs.append(("MECH", rx_mech))
            for k, rx in pairs:
                for m in rx.finditer(line):
                    num = int(m.group(1))
                    token = m.group(0)
                    # Primary M regex can theoretically see a leading char in group(0)
                    # if we used a capturing lookbehind; we did not. Still normalise.
                    if k == "M" and not token.startswith("M-"):
                        token = "M-" + m.group(1)
                    if k == "MECH" and "MECH-" not in token:
                        token = "MECH-" + m.group(1)
                    hits.append(
                        Hit(
                            path=rel,
                            line=i,
                            column=m.start() + 1,
                            token=token if token.startswith(("M-", "MECH-")) else (
                                f"MECH-{num}" if k == "MECH" else f"M-{num}"
                            ),
                            number=num,
                            kind=k,
                            snippet=line.strip()[:240],
                            in_fence=in_fence,
                        )
                    )
    return hits


def declaration_ids(root: Path, *, kind: str) -> list[int]:
    """Unique declaration-site numbers (headers / JSON id / named declaration phrases)."""
    found: set[int] = set()
    if kind == "M":
        header = re.compile(DECL_HEADER_M)
        json_id = re.compile(DECL_JSON_ID_M)
        harness = re.compile(DECL_HARNESS)
        mission = re.compile(r"\bM-(\d{1,3})\b")
        for fp in iter_text_files(root):
            text = fp.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                for rx in (header, json_id, harness):
                    for m in rx.finditer(line):
                        found.add(int(m.group(1)))
                if re.search(DECL_MISSION_LINE, line):
                    for m in mission.finditer(line):
                        found.add(int(m.group(1)))
    elif kind == "MECH":
        header = re.compile(DECL_HEADER_MECH)
        for fp in iter_text_files(root):
            text = fp.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                for m in header.finditer(line):
                    found.add(int(m.group(1)))
    else:
        raise ValueError(kind)
    return sorted(found)


def regex_catalog() -> dict:
    return {
        "regex_primary": REGEX_M_PRIMARY,
        "regex_reviewer": REGEX_M_REVIEWER,
        "regex_mech_primary": REGEX_MECH_PRIMARY,
        "regex_mech_reviewer": REGEX_MECH_REVIEWER,
        "declaration_patterns": [
            DECL_HEADER_M,
            DECL_HEADER_MECH,
            DECL_JSON_ID_M,
            DECL_HARNESS,
            DECL_MISSION_LINE,
        ],
    }
