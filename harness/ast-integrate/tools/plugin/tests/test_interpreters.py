#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
from plugin.interpreters import DeclarationError, lint_entrypoints, load_manifest  # noqa: E402

UNDECLARED = Path(__file__).resolve().parent / "fixtures" / "undeclared.json"


def main() -> int:
    rows = lint_entrypoints()
    assert len(rows) >= 2
    bad = load_manifest(UNDECLARED)
    try:
        lint_entrypoints(bad)
        print("FAIL accepted undeclared")
        return 1
    except DeclarationError as exc:
        assert "missing interpreter" in str(exc)
    print("SUCCESS:test_interpreters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
