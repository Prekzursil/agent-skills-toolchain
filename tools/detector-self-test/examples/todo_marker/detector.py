"""Worked-example detector: block on a leftover "do not ship" marker.

Wraps a real release-hygiene predicate: some teams forbid shipping any file
that still carries an explicit ``XXX-DO-NOT-SHIP`` marker. The both-states
self-test proves this detector FIRES on the ``broken/`` fixture (marker
present) and stays SILENT on the ``fixed/`` fixture (marker removed). The
detector scans ``target``, never its own source, so the literal below is safe.
"""

from __future__ import annotations

from pathlib import Path

_MARKER = "XXX-DO-NOT-SHIP"


def detect(target: Path) -> list[str]:
    """Return one finding per line under ``target`` that carries the marker."""
    findings: list[str] = []
    for path in sorted(p for p in target.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _MARKER in line:
                findings.append(f"{path.name}:{lineno}: {_MARKER} marker present")
    return findings
