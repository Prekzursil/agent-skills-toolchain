#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
IDS = [
    ln.strip()
    for ln in (HERE / "shard-21.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
FAIL_RE = re.compile(r"""FAILED:[^\n"']{0,180}|print\("FAILED[^"]+|fail\([^)]{0,200}""")


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        fails: list[str] = []
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            for m in FAIL_RE.finditer(text):
                s = m.group(0).replace("\n", " ")[:180]
                if s not in fails:
                    fails.append(s)
        rows.append({"id": uid, "fails": fails[:14], "n": len(fails)})
        print(uid, "n=", len(fails))
        for s in fails[:8]:
            print(" ", s[:170])
    dest = HERE / "_shard21_failstrs.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest, "n=", len(rows))


if __name__ == "__main__":
    main()
