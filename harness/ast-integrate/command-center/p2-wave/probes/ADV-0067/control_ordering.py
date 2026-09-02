#!/usr/bin/env python3
"""Control: genuine package must not score lower than the gamed one."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def main() -> int:
    cmp = C.compare_packages()
    row = cmp["control_genuine_not_lower"]
    print(json.dumps(row, sort_keys=True))
    if row["inverted"] and not row["named_term"]:
        print("FAILED:ADV-0067-control inverted without a named term")
        return 1
    print(
        "SUCCESS:ADV-0067-control ordering "
        f"genuine={row['genuine']} gamed={row['gamed']} inverted={row['inverted']} "
        f"term={row['named_term']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
