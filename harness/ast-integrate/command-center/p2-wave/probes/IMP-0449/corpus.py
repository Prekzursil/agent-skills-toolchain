"""Harvest one live observed string per IMP-0449 taxonomy class from this worktree.

The catalog names `_USER-PROMPTS.md:11298-11347` and `adapter error corpus`.
Neither file exists here. Rows are REAL when the needle is found on disk,
SPECULATIVE otherwise. The catalog path command-center/phase3/A2/FAILURE-MODES.json
is absent on this worktree; partial-artifact uses the live ARC-0012 seed that
still carries the measured zero-byte title.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))

import failure_taxonomy as ft  # noqa: E402

SEEDS: tuple[dict[str, str], ...] = (
    {
        "class": "win-arg-limit",
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "needle": "died with os error 206",
    },
    {
        "class": "timeout",
        "path": "command-center/p2-wave/_p2lib.py",
        "needle": "TIMEOUT after {timeout}s",
    },
    {
        "class": "schema-invalid",
        "path": "command-center/ready_units.py",
        "needle": "schema-invalid:{len(errs)}",
    },
    {
        "class": "partial-artifact",
        "path": "command-center/p2-wave/probes/ARC-0012/emit_failure_modes.py",
        "needle": "Zero-byte file at the mapped path treated as present",
    },
    {
        "class": "severed-stream",
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "needle": "a dispatch returning only a progress stream or a job receipt is classified severed-stream",
    },
    {
        "class": "adapter-exit-n",
        "path": "command-center/p2-wave/probes/AUD-0064/_validate_out.json",
        "needle": '"current_launch_exit_code": 127',
    },
    {
        "class": "blocked",
        "path": "command-center/p2-wave/probes/IMP-0433/_measure_out.json",
        "needle": "self-declared:BLOCKED",
    },
    {
        "class": "degraded",
        "path": "command-center/p2-wave/_i1_dark_probe2.out.json",
        "needle": "resolver: UNAVAILABLE (contract check degraded)",
    },
)


def _find_line(text: str, needle: str) -> tuple[int, str] | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i, line.strip()
    return None


def harvest_coverage(repo: Path | None = None) -> list[dict[str, Any]]:
    root = repo or REPO
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for seed in SEEDS:
        cls = seed["class"]
        rel = seed["path"]
        needle = seed["needle"]
        path = root / rel
        if cls in seen:
            raise RuntimeError(f"duplicate seed class {cls}")
        seen.add(cls)
        if not path.is_file():
            rows.append(
                {
                    "class": cls,
                    "observed_error_string": needle,
                    "source": rel,
                    "line": 1,
                    "corpus_kind": "SPECULATIVE",
                    "classified_as": cls,
                    "speculative": True,
                    "speculative_reason": f"source file absent on this worktree: {rel}",
                    "fingerprint": ft.error_fingerprint(needle, cls),
                }
            )
            continue
        found = _find_line(path.read_text(encoding="utf-8", errors="replace"), needle)
        if found is None:
            rows.append(
                {
                    "class": cls,
                    "observed_error_string": needle,
                    "source": rel,
                    "line": 1,
                    "corpus_kind": "SPECULATIVE",
                    "classified_as": cls,
                    "speculative": True,
                    "speculative_reason": f"needle not found in {rel}",
                    "fingerprint": ft.error_fingerprint(needle, cls),
                }
            )
            continue
        line_no, snippet = found
        classified = ft.classify(snippet)
        rows.append(
            {
                "class": cls,
                "observed_error_string": snippet,
                "source": rel,
                "line": line_no,
                "corpus_kind": "REAL",
                "classified_as": classified,
                "speculative": False,
                "fingerprint": ft.error_fingerprint(snippet, classified),
            }
        )
    missing = [c for c in ft.TAXONOMY_CLASSES if c not in seen]
    if missing:
        raise RuntimeError(f"seeds missing classes {missing}")
    order = {c: i for i, c in enumerate(ft.TAXONOMY_CLASSES)}
    rows.sort(key=lambda r: order[r["class"]])
    return rows
