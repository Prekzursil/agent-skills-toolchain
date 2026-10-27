"""Throwaway sizing probe: what command receipts do this lane's docs actually contain?

Read-only. Prints every line that names a ``docs/rule-audit`` python script together with the
argv tokens that follow it, so the round-4 gate can be scoped to a measured inventory rather
than a guessed one.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = {p.name for p in HERE.glob("*.py")}
TOKEN = re.compile(r"([A-Za-z0-9_./-]+\.py)((?:\s+[-\w./=:*]+)*)")


def main() -> int:
    counter: Counter[str] = Counter()
    for doc in sorted(HERE.glob("*.md")):
        for lineno, raw in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            for match in TOKEN.finditer(raw):
                name = Path(match.group(1)).name
                if name not in SCRIPTS:
                    continue
                args = match.group(2).split()
                counter[f"{name} {' '.join(args)}".strip()] += 1
                if args:
                    print(f"{doc.name}:{lineno}: {name} {' '.join(args)}")
    print("")
    for invocation, count in sorted(counter.items()):
        print(f"{count:3d}  {invocation}")
    print(
        f"\ndistinct invocations: {len(counter)}  total mentions: {sum(counter.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
