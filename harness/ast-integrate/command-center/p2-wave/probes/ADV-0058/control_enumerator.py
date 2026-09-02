#!/usr/bin/env python3
"""Catalog control: declared dependency in both sets; zero-diff+missed plant is broken."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402


def main() -> int:
    row = C.declared_control()
    nc = C.negative_control()
    print(json.dumps({"declared": row, "manifest_only_mutant": nc}, sort_keys=True))
    if not row["pass"]:
        print("FAILED:ADV-0058-control declared dependency not in both sets")
        return 1
    if not nc["pass"]:
        print("FAILED:ADV-0058-control manifest-only mutant did not fire two-sided")
        return 1
    print(
        "SUCCESS:ADV-0058-control "
        f"declared_in_both={row['declared_in_both']} "
        f"enumeration_broken={row['enumeration_broken']} "
        f"mutant_fired={nc['fired_on_bad_state']} "
        f"mutant_silent_on_good={nc['silent_on_good_state']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
