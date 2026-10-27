r"""Rank the READY set using the FIXED delivered() predicate (imports it, does not re-implement).

Ordering is the recorded owner ruling OQ-2: ascending phase (INT, not lexicographic -- the
grounding lane's disclosed bug put '10' before '2'), then unblocking power, then id.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUCKET = re.compile(r"B\d+")


def load_ready_units():
    p = REPO / "command-center" / "ready_units.py"
    spec = importlib.util.spec_from_file_location("ready_units", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ready_units"] = mod
    spec.loader.exec_module(mod)
    return mod


def phase_key(p: object) -> tuple[int, str]:
    s = str(p)
    m = re.match(r"(\d+)", s)
    return (int(m.group(1)) if m else 9999, s)


def main() -> int:
    ru = load_ready_units()
    units = json.loads(ru.CATALOG.read_text(encoding="utf-8"))["work_units"]
    by_id = {u["id"]: u for u in units}
    resolver = ru._load_resolver()
    cache: dict[str, bool] = {}

    def delivered(uid: str) -> bool:
        if uid not in cache:
            u = by_id.get(uid)
            cache[uid] = False if u is None else ru.artifact_delivered(u, resolver)[0]
        return cache[uid]

    ready = []
    for u in units:
        if delivered(u["id"]) or u.get("owner_approval_required"):
            continue
        if all(
            BUCKET.fullmatch(d) or (d in by_id and delivered(d))
            for d in (u.get("dependencies") or [])
        ):
            ready.append(u)

    dependents: Counter = Counter()
    for u in units:
        for dep in u.get("dependencies") or []:
            dependents[dep] += 1

    ready.sort(key=lambda u: (phase_key(u.get("phase")), -dependents[u["id"]], u["id"]))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"READY={len(ready)} under the FIXED predicate (catalog units={len(units)})")
    print("-" * 104)
    for u in ready[:n]:
        print(
            f"{u['id']:>10} phase={str(u.get('phase')):<4} unblocks={dependents[u['id']]:<3} "
            f"sub={str(u.get('execution_substrate'))[:18]:<18} out={u.get('output_path')}"
        )
    print("-" * 104)
    print("PHASE-0 READY:", sum(1 for u in ready if phase_key(u.get("phase"))[0] == 0))
    ctl = sorted(["10", "2", "0", "2A"], key=phase_key)
    print(
        "CONTROL phase-sort:",
        ctl,
        "->",
        "OK" if ctl == ["0", "2", "2A", "10"] else "BROKEN",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
