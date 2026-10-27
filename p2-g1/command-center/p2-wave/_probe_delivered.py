r"""Probe the `delivered` detector used by ready_units.py.

ready_units.py calls a unit DELIVERED when `(REPO / output_path).exists()`. That is a
single-signal existence check. This probe adds mechanically independent signals:
  * byte size (an empty file "exists")
  * parses as its declared format (json/md)
  * a stub-sentinel scan (UNKNOWN / TODO / placeholder)
  * a repeated-character degenerate check (the "2,000 x characters" failure mode)

Prints a per-unit table plus a terminal SUCCESS/FAILED marker.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

STUB_PAT = re.compile(
    r"UNKNOWN - not yet measured|^\s*TODO\b|PLACEHOLDER|not yet implemented|LOREM IPSUM",
    re.IGNORECASE | re.MULTILINE,
)


def degenerate(text: str) -> bool:
    """True when the body is one character repeated (the 2,000-x failure mode)."""
    body = "".join(text.split())
    if len(body) < 50:
        return False
    return len(set(body)) <= 2


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]

    rows = []
    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        fp = REPO / p
        if not fp.exists():
            continue
        try:
            raw = fp.read_bytes()
        except OSError as exc:  # pragma: no cover - defensive
            rows.append((u["id"], p, -1, f"unreadable:{exc}"))
            continue
        size = len(raw)
        flags = []
        if size == 0:
            flags.append("EMPTY")
        text = raw.decode("utf-8", errors="replace")
        if p.endswith(".json"):
            try:
                json.loads(text)
            except Exception as exc:
                flags.append(f"JSON-PARSE-FAIL:{type(exc).__name__}")
        if STUB_PAT.search(text):
            flags.append("STUB-SENTINEL")
        if degenerate(text):
            flags.append("DEGENERATE")
        if size < 200:
            flags.append("TINY<200B")
        rows.append((u["id"], p, size, ",".join(flags) or "ok"))

    rows.sort()
    print(f"delivered-by-existence: {len(rows)}")
    tally: Counter = Counter()
    for uid, p, size, flag in rows:
        tally[flag] += 1
        print(f"  {uid:<12} {size:>9} B  {flag:<28} {p}")
    print(f"\nflag tally: {dict(tally)}")

    bad = [r for r in rows if r[3] != "ok"]
    print(f"\nnon-ok: {len(bad)} of {len(rows)}")
    print("SUCCESS:probe-delivered ran" if rows else "FAILED:probe-delivered no rows")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
