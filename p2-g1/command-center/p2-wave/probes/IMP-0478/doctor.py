#!/usr/bin/env python3
"""IMP-0478 doctor: print the user-facing message for a taxonomy class.

Exit 0 when the class is mapped (message printed); exit 3 when unmapped -
an unmapped class must be visible as a refusal, never silent (receipt claim).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import error_catalog  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="taxonomy_class", required=True)
    args = ap.parse_args()
    entry = error_catalog.lookup(args.taxonomy_class)
    print("ID: " + str(entry["message_id"]))
    print("MAPPED: " + ("true" if entry["mapped"] else "false"))
    print("WHAT: " + entry["what"])
    print("WHY: " + entry["why"])
    print("NEXT: " + str(entry["next_command"]))
    return 0 if entry["mapped"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
