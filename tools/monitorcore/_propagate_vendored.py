"""Propagate every top-level monitorcore module to each vendored copy, byte-exactly.

Discovery replaces the defective hardcoded six-module tuple, which printed a green
SUCCESS while 32 modules stayed drifted and only reddened CI after the fact. Empty
source discovery, missing copy roots, and orphaned destination modules fail closed.
New destination modules are created; orphans require deliberate operator deletion.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "tools" / "monitorcore" / "monitorcore"
COPIES = (
    REPO / "skills" / "workflow-monitor" / "monitorcore",
    REPO / ".agents" / "skills" / "workflow-monitor" / "monitorcore",
)


@dataclass(frozen=True)
class PropagationResult:
    """Outcome and operator-facing lines from one propagation attempt."""

    exit_code: int
    copied: int
    created: int
    lines: tuple[str, ...]


def _display(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def propagate(
    source: Path = SOURCE, copies: Sequence[Path] = COPIES
) -> PropagationResult:
    """Copy all discovered source modules, returning a printable result."""
    missing = [copy for copy in copies if not copy.is_dir()]
    if missing:
        paths = ", ".join(path.as_posix() for path in missing)
        line = f"FAILED:propagate vendored copy missing: {paths}"
        return PropagationResult(1, 0, 0, (line,))

    modules = sorted(source.glob("*.py"), key=lambda path: path.name)
    if not modules:
        line = f"FAILED:propagate no top-level Python modules discovered in {source}"
        return PropagationResult(1, 0, 0, (line,))

    source_names = {module.name for module in modules}
    orphans = sorted(
        (
            path
            for copy in copies
            for path in copy.glob("*.py")
            if path.name not in source_names
        ),
        key=lambda path: path.as_posix(),
    )
    if orphans:
        lines = tuple(f"  orphan: {_display(path)}" for path in orphans)
        failure = (
            "FAILED:propagate orphan module(s) found; operator must delete "
            "them deliberately"
        )
        return PropagationResult(1, 0, 0, (*lines, failure))

    copied = 0
    created = 0
    lines: list[str] = []
    for src in modules:
        blob = src.read_bytes()
        for copy in copies:
            dest = copy / src.name
            is_new = not dest.exists()
            dest.write_bytes(blob)
            if dest.read_bytes() != blob:
                failure = f"FAILED:propagate readback mismatch: {dest}"
                return PropagationResult(1, copied, created, (*lines, failure))
            copied += 1
            created += int(is_new)
            marker = "+" if is_new else "<-"
            lines.append(f"  {_display(dest)}  {marker} {len(blob)} B")

    lines.append(
        f"SUCCESS:propagate {copied} file(s) into {len(copies)} vendored copy/copies"
    )
    return PropagationResult(0, copied, created, tuple(lines))


def main() -> int:
    result = propagate()
    for line in result.lines:
        print(line)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
