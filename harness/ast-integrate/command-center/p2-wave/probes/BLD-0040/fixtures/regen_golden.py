#!/usr/bin/env python3
"""Regenerate snapshot/golden.json by running the code under test.

This is the process recorded in snapshot/REGEN.json. A golden produced this
way is a self-confirming oracle: it cannot catch a wrong produce_report().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from subject import produce_report  # noqa: E402

GOLDEN = HERE / "snapshot" / "golden.json"


def main() -> int:
    payload = produce_report()
    GOLDEN.write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {GOLDEN.relative_to(HERE.parent.parent.parent.parent)} from produce_report()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
