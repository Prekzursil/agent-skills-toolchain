#!/usr/bin/env python3
"""Control: reference outputs must rank in the intended quality order."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def main() -> int:
    rank = C.ranking_bundle()
    row = rank["control_reference_order"]
    print(json.dumps(row, sort_keys=True))
    if row["already_inverted"] and row["pass"]:
        print("FAILED:ADV-0085-control inverted and pass both true")
        return 1
    print(
        "SUCCESS:ADV-0085-control ordering "
        f"observed={row['observed']} inverted={row['already_inverted']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
