#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1].parent
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(TOOLS))
from marketplace.permission_catalog import EMPTY_SURFACE_LINE, extract_declared  # noqa: E402
from marketplace.permission_surface import HEADER, render_permission_surface  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_mixed_renders_declared() -> None:
    pkg = _load("declared-mixed.json")
    surface = render_permission_surface(pkg)
    for pid in extract_declared(pkg):
        assert f"PERM {pid} " in surface
    assert "=== CRITICAL ===" in surface
    assert "!!!" in surface


def test_empty_named() -> None:
    for name in ("declared-none.json", "declared-missing.json"):
        pkg = _load(name)
        surface = render_permission_surface(pkg)
        assert HEADER in surface
        assert EMPTY_SURFACE_LINE in surface
        assert extract_declared(pkg) == []


def main() -> int:
    failed = []
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:
                failed.append(name)
                print(f"FAIL {name} {exc}")
    if failed:
        print("FAILED", failed)
        return 1
    print("SUCCESS:IMP-0090 tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
