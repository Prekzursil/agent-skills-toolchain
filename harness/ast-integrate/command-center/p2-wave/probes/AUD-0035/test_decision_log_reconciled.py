#!/usr/bin/env python3
"""Executable failing test: decision log must be reconciled to MECH-NN.

RED on the current unreconciled tree (line 175 present-tense M-NN collision,
zero MECH tokens, or a missing log). GREEN only after reconciliation.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    return E.run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
