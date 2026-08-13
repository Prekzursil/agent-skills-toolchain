"""AUDIT probe 5: control on MY OWN walker -- do the untracked mutant fixtures move the 51?

Probe 2 walked the worktree, which holds 4 UNTRACKED deliberately-broken mutant fixtures under
command-center/p2-next/_mutants/. If any carried a unit id that is not otherwise blocked, my 51
would be inflated by my own instrument. Re-walk with and without them and diff the SETS.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CC = REPO / "command-center"
ID = re.compile(r"^[A-Z]{2,4}-\d{4}$")

ids = {
    r["id"]
    for r in json.load(io.open(CC / "WORK-UNIT-CATALOG.json", encoding="utf-8"))[
        "work_units"
    ]
}


def walk(skip_mutants: bool) -> dict:
    got: dict[str, list] = {}
    for p in sorted(CC.rglob("*.json")):
        rp = p.relative_to(REPO).as_posix()
        if skip_mutants and "/_mutants/" in rp:
            continue
        try:
            o = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        u = o.get("unit_id") or o.get("id")
        s = o.get("state")
        if not (isinstance(u, str) and ID.match(u) and isinstance(s, str) and u in ids):
            continue
        got.setdefault(u, []).append((rp, s.upper()))
    return got


def blocked(g):
    return {
        u for u, lst in g.items() if any(s in ("BLOCKED", "FAILED") for _, s in lst)
    }


a, b = walk(False), walk(True)
ba, bb = blocked(a), blocked(b)
print(f"with mutants   : {len(ba)}")
print(f"without mutants: {len(bb)}")
print(f"set symmetric difference: {sorted(ba ^ bb)}")
print(f"TST-0334 receipt paths (mutants excluded): {b.get('TST-0334')}")

# same question against the COMMITTED tree only (git ls-files), the cleanest signal
r = subprocess.run(
    ["git", "ls-files", "command-center"], cwd=REPO, capture_output=True, text=True
)
tracked = [x for x in r.stdout.splitlines() if x.endswith(".json")]
got: dict[str, list] = {}
for rp in tracked:
    raw = subprocess.run(
        ["git", "show", f"HEAD:{rp}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if raw.returncode != 0:
        continue
    try:
        o = json.loads(raw.stdout)
    except Exception:
        continue
    if not isinstance(o, dict):
        continue
    u = o.get("unit_id") or o.get("id")
    s = o.get("state")
    if not (isinstance(u, str) and ID.match(u) and isinstance(s, str) and u in ids):
        continue
    got.setdefault(u, []).append((rp, s.upper()))
bt = blocked(got)
print(f"\nCOMMITTED-BLOBS-ONLY (HEAD) blocked units: {len(bt)}")
print(f"  vs worktree-minus-mutants: symmetric diff = {sorted(bt ^ bb)}")
