#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import error_taxonomy as et


def test_uncoded_plant_is_caught() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.py"
        p.write_text("raise RuntimeError('x')\n", encoding="utf-8")
        assert et.uncoded_sites(Path(td))


def main() -> int:
    test_uncoded_plant_is_caught()
    print("SUCCESS:IMP-0051-tests error taxonomy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
