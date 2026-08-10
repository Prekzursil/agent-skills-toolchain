r"""Print the full disposition/anchor/confidence cells for named register rows.

Written as a FILE, not a heredoc: the unescaped-pipe lookbehind `(?<!\\)\|` loses its backslash
through a bash heredoc even under `<<'PY'` quoting (windows-shell rule 8c), which turns the pattern
into a syntax error. The module docstring is raw for the same reason -- a bare `\|` in a normal
docstring is an invalid escape sequence and warns.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")

#: Which lane OWNS which register block. A row appearing outside its owning lane is advisory only --
#: on a split verdict the owning lane's specific probe wins, never a vote across lanes.
#: Keyed by (lane, family) -> the numeric range that lane owns. A3 owns R-A23..R-A32 AND the whole
#: HARNESS block R-H01..R-H10; M3 owns R-M15..R-M19 AND R-B01..R-B08. Keying on the number alone
#: conflated the M- and B- numbering and reported R-B04/R-B05 as having no owner at all.
OWNER = {
    ("CLOSE-PROPOSALS-A1.md", "A"): range(1, 12),
    ("CLOSE-PROPOSALS-A2.md", "A"): range(12, 23),
    ("CLOSE-PROPOSALS-A3.md", "A"): range(23, 33),
    ("CLOSE-PROPOSALS-A3.md", "H"): range(1, 11),
    ("CLOSE-PROPOSALS-M1.md", "M"): range(1, 8),
    ("CLOSE-PROPOSALS-M2.md", "M"): range(8, 15),
    ("CLOSE-PROPOSALS-M3.md", "M"): range(15, 20),
    ("CLOSE-PROPOSALS-M3.md", "B"): range(1, 9),
}


def owns(name: str, rid: str) -> bool:
    """True if `name` is the lane that owns `rid`."""
    fam, num = rid[2], int(rid[3:])
    rng = OWNER.get((name, fam))
    return rng is not None and num in rng


def main(argv: list[str]) -> int:
    want = set(argv) or {"R-A04", "R-A08", "R-A23", "R-A24", "R-B04", "R-B05"}
    seen = set()
    for path in sorted(HERE.glob("CLOSE-PROPOSALS-*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.lstrip().startswith("|"):
                continue
            parts = UNESCAPED_PIPE.split(line)
            if len(parts) < 7:
                continue
            rid = parts[1].strip().strip("*")
            if rid not in want:
                continue
            tag = "OWNED" if owns(path.name, rid) else "advisory"
            if tag == "advisory":
                continue
            seen.add(rid)
            print(f"\n=== {rid}   [{path.name}, {tag}]")
            print(f"  DISPOSITION: {parts[4].strip()[:400]}")
            print(f"  ANCHOR     : {parts[5].strip()[:400]}")
            print(f"  CONFIDENCE : {parts[6].strip()[:100]}")
    missing = want - seen
    if missing:
        print(f"\nWARNING: no OWNED row found for {sorted(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
