"""Extract (id, disposition, confidence) from every lane proposal table.

Splits on UNESCAPED pipes only: the measurement cells contain markdown-escaped `\\|` inside regex
literals (`Read\\|Edit\\|Bash`), and a naive `line.split("|")` shifts every later column -- the
delimiter-inside-a-field trap. Also refuses to report a table it could not parse, so a lane whose
format differs shows up as a parse failure rather than as silently zero proposals.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = [
    "CLOSE-PROPOSALS-A1.md",
    "CLOSE-PROPOSALS-A2.md",
    "CLOSE-PROPOSALS-A3.md",
    "CLOSE-PROPOSALS-M1.md",
    "CLOSE-PROPOSALS-M2.md",
    "CLOSE-PROPOSALS-M3.md",
]
ROW_ID = re.compile(r"^\*{0,2}(R-[A-Z]\d{2})\*{0,2}$")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
# The disposition verb, normalised. Order matters: check the compound forms first.
VERBS = ("STAYS-OPEN", "OWNER-GATED", "CLOSE", "SUPERSEDED", "DROPPED", "UNKNOWN")


def disposition_of(cell: str) -> str:
    up = cell.upper()
    for verb in VERBS:
        if verb in up:
            return verb
    return f"UNPARSED({cell.strip()[:40]})"


def confidence_of(cell: str) -> str:
    """The FIRST band token is the grading; later ones are prose ABOUT other quantities.

    Use-vs-mention, caught in this file: R-A04's cell reads
    `likely (55-80%) - the answer is almost-certain; I did not enumerate ...`.
    Scanning for any occurrence of "almost-certain" promoted a `likely` row to `almost-certain` and
    would have queued two owner-gated items for automatic closure. Take the earliest match by
    POSITION, not the first band in my own priority order.
    """
    low = cell.lower()
    hits = [
        (low.find(b), b)
        for b in ("almost-certain", "likely", "uncertain", "speculative")
    ]
    hits = [(pos, b) for pos, b in hits if pos >= 0]
    return min(hits)[1] if hits else "none-stated"


def main() -> int:
    rows: dict[str, tuple[str, str, str]] = {}
    parse_fail = []
    for name in FILES:
        path = HERE / name
        if not path.exists():
            parse_fail.append(f"{name}: ABSENT")
            continue
        found = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.lstrip().startswith("|"):
                continue
            parts = UNESCAPED_PIPE.split(line)
            if len(parts) < 7:
                continue
            m = ROW_ID.match(parts[1].strip())
            if not m:
                continue
            rid = m.group(1)
            found += 1
            # An id can appear twice: once as an owned row, once as an adjacent advisory row. The
            # owned table comes first, so keep the FIRST sighting and record the collision.
            if rid in rows:
                continue
            rows[rid] = (name, disposition_of(parts[4]), confidence_of(parts[6]))
        if found == 0:
            parse_fail.append(f"{name}: 0 rows parsed (format drift?)")

    if parse_fail:
        print("DETECTOR WARNING -- unparsed lanes: " + "; ".join(parse_fail))

    by_disp: dict[str, list[str]] = {}
    for rid, (_, disp, conf) in sorted(rows.items()):
        by_disp.setdefault(disp, []).append(f"{rid}({conf.split('-')[0]})")

    print(f"parsed {len(rows)} register rows across {len(FILES)} lanes\n")
    for disp in sorted(by_disp, key=lambda d: -len(by_disp[d])):
        ids = by_disp[disp]
        print(f"{disp:14} {len(ids):3}  {' '.join(ids)}")

    print()
    closes = [r for r, (_, d, _) in rows.items() if d == "CLOSE"]
    strong = [r for r in closes if rows[r][2] == "almost-certain"]
    print(f"CLOSE proposals: {len(closes)}  (almost-certain: {len(strong)})")
    print(f"  almost-certain: {' '.join(sorted(strong))}")
    print(f"  weaker:         {' '.join(sorted(set(closes) - set(strong)))}")
    print(f"\nconfidence spread: {dict(Counter(c for _, _, c in rows.values()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
