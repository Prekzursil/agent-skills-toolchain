"""Test-support package for :mod:`plugin`.

Submodules are imported explicitly by the probes that need them
(``plugin.tests.harness``, ``plugin.tests.test_pack_determinism``,
``plugin.tests.test_divergence_packet`` ...).  Nothing is imported here on
purpose: loading one suite must never drag every other suite -- and its
fixtures -- into an unrelated probe's import graph.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def discover_test_modules(package_dir: Path | str | None = None) -> list[str]:
    """Return the sorted module names of every ``test_*.py`` suite in the package."""
    root = Path(package_dir) if package_dir is not None else PACKAGE_DIR
    return sorted(p.stem for p in root.glob("test_*.py") if p.is_file())


__all__ = ["PACKAGE_DIR", "discover_test_modules"]
