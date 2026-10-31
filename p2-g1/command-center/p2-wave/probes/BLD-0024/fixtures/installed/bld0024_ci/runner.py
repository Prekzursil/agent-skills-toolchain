"""Console-script body: re-run dismissals without python -m pytest."""
from __future__ import annotations

import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parents[3]
if str(PROBE) not in sys.path:
    sys.path.insert(0, str(PROBE))

from revalidate import run_worker  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    return run_worker(["console", *args])
