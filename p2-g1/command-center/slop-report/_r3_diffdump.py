"""Print a compact, human-readable triage table of the differing twin pairs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).with_name("_r3_twinsurface.out.json")


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = data["differing_pairs"]
    mode = sys.argv[1] if len(sys.argv) > 1 else "table"
    if mode == "table":
        print(f"{'changed':>7} {'uh':>3}  root")
        for r in sorted(rows, key=lambda x: -x["changed_line_count"]):
            uh = "UH" if r.get("user_home_only") else ""
            print(f"{r['changed_line_count']:>7} {uh:>3}  {r['root']}")
        return 0
    # mode == a path substring: dump that pair's diff head
    for r in rows:
        if mode in r["root"]:
            print("=" * 70)
            print(r["root"])
            print(r["diff_head"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
