"""Resolve the exact design-doc line for each P25-P36 card's mechanism / failure-mode / proof.

Read-only. Prevents a citation that points at the wrong bullet: the offsets are MEASURED per
card, not assumed constant.
"""

from __future__ import annotations

import re
from pathlib import Path

DOC = (
    Path.home()
    / ".claude"
    / "harness-restore-20260806"
    / "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
)
WANT = {
    "mechanism": "**concrete mechanism:**",
    "failure": "**failure modes:**",
    "proof": "**proof needed before adoption:**",
}


def main() -> int:
    lines = DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    heads = {}
    for i, line in enumerate(lines, start=1):
        m = re.match(r"^#### (P\d\d) `([a-z0-9-]+)`", line)
        if m:
            heads[m.group(1)] = (i, m.group(2))

    ids = [f"P{n}" for n in range(25, 37)]
    print("id   head  mech  fail  proof  name")
    out = {}
    for pid in ids:
        if pid not in heads:
            print(f"{pid}  MISSING")
            continue
        head, name = heads[pid]
        found = {}
        for j in range(head, min(head + 20, len(lines) + 1)):
            text = lines[j - 1]
            for key, needle in WANT.items():
                if needle in text and key not in found:
                    found[key] = j
        print(
            f"{pid}  {head:5} {found.get('mechanism', 0):5} {found.get('failure', 0):5} "
            f"{found.get('proof', 0):6} {name}"
        )
        out[pid] = (
            head,
            found.get("mechanism"),
            found.get("failure"),
            found.get("proof"),
        )

    missing = [p for p, v in out.items() if None in v]
    print(
        f"-- resolved {len(out) - len(missing)}/12 cards with all three anchors; missing={missing}"
    )
    print("cite tuples:")
    for pid in ids:
        if pid in out and None not in out[pid]:
            print(
                f"  {pid}: cite({out[pid][0]}, {out[pid][1]}, {out[pid][2]}, {out[pid][3]})"
            )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
