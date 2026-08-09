"""Enumerate every candidate entry in doc 08 in document order.

Deterministic partition helper for the wfa-N archaeology units: entry N of this
list is candidate N. Unit wfa-2 owns 33..64 inclusive.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DOC = Path(
    r"C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    r"08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
)

# a candidate entry is  "### `<id>` - <name>"
ENTRY = re.compile(r"^###\s+`([^`]+)`\s*(?:-|\u2014)?\s*(.*)$")
SECTION = re.compile(r"^##\s+([A-Z])\.\s+(.*)$")


def main() -> int:
    text = DOC.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out = []
    section = "?"
    section_title = "?"
    for i, ln in enumerate(lines, start=1):
        m = SECTION.match(ln)
        if m:
            section, section_title = m.group(1), m.group(2).strip()
            continue
        m = ENTRY.match(ln)
        if m:
            out.append(
                {
                    "n": len(out) + 1,
                    "doc_line": i,
                    "section": section,
                    "section_title": section_title,
                    "id": m.group(1),
                    "name": m.group(2).strip(),
                }
            )
    print(f"total entries: {len(out)}")
    by_sec: dict[str, int] = {}
    for e in out:
        by_sec[e["section"]] = by_sec.get(e["section"], 0) + 1
    print("per section:", json.dumps(by_sec))
    lo, hi = 33, 64
    print(f"\n--- MY RANGE {lo}..{hi} ---")
    for e in out:
        if lo <= e["n"] <= hi:
            print(
                f"{e['n']:>3}  L{e['doc_line']:<5} [{e['section']}] {e['id']}  ::  {e['name']}"
            )
    Path(
        r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa2_entries.json"
    ).write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
