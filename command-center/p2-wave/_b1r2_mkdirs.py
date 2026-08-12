r"""Scope expansion 2: create the output_path parent directories that READY units write into.

Measured (`_b1r2_scope_measure.py`): 27 distinct parent dirs are absent; 713 units write into one;
105 of those units are READY, spread over 14 of the 27 dirs. The failure mode is PROVEN, not
hypothesised -- the control in that probe showed `open(path,'w')` into a missing parent raises
FileNotFoundError (fires on the bad state) and succeeds into an existing parent (silent on the
good state). A unit that dies that way exits non-zero with no output file, which the program
classifies as SEVERED.

Scope: only the dirs that at least one READY unit writes into. Creating all 27 would seed empty
directories for units that are still blocked -- noise, not insurance. `.gitkeep` is required
because git cannot track an empty directory, so an uncommitted mkdir would not survive a clone.
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
KEEP = (
    "# Output substrate for work units whose catalog row declares an output_path here.\n"
    "# Created by command-center/p2-wave/_b1r2_mkdirs.py. Git cannot track an empty directory,\n"
    "# so this placeholder is what makes the directory survive a fresh clone. A unit writing\n"
    "# into a missing parent dies with FileNotFoundError and no output file = SEVERED.\n"
)


def main() -> int:
    apply = "--apply" in sys.argv
    p = REPO / "command-center" / "ready_units.py"
    spec = importlib.util.spec_from_file_location("ready_units", p)
    ru = importlib.util.module_from_spec(spec)
    sys.modules["ready_units"] = ru
    spec.loader.exec_module(ru)

    units = json.loads(ru.CATALOG.read_text(encoding="utf-8"))["work_units"]
    by_id = {u["id"]: u for u in units}
    resolver = ru._load_resolver()
    cache: dict[str, bool] = {}

    def delivered(uid: str) -> bool:
        if uid not in cache:
            u = by_id.get(uid)
            cache[uid] = False if u is None else ru.artifact_delivered(u, resolver)[0]
        return cache[uid]

    ready = set()
    for u in units:
        if delivered(u["id"]) or u.get("owner_approval_required"):
            continue
        if all(
            BUCKET.fullmatch(d) or (d in by_id and delivered(d))
            for d in (u.get("dependencies") or [])
        ):
            ready.add(u["id"])

    need: Counter = Counter()
    allmissing: Counter = Counter()
    for u in units:
        op = u.get("output_path")
        if not op:
            continue
        parent = (REPO / op).parent
        if parent.exists():
            continue
        rel = parent.relative_to(REPO).as_posix()
        allmissing[rel] += 1
        if u["id"] in ready:
            need[rel] += 1

    print(f"missing parent dirs total   : {len(allmissing)} ({sum(allmissing.values())} units)")
    print(f"missing parent dirs w/ READY: {len(need)} ({sum(need.values())} READY units)")
    for d, n in sorted(need.items()):
        print(f"  {'CREATE' if apply else 'would create'} {d:<52} ready_units={n}")
    if not apply:
        print("\n(dry run -- pass --apply to create)")
        return 0
    made = 0
    for d in sorted(need):
        target = REPO / d
        target.mkdir(parents=True, exist_ok=True)
        keep = target / ".gitkeep"
        if not keep.exists():  # never truncate an existing file
            keep.write_text(KEEP, encoding="utf-8")
        made += 1
    print(f"\ncreated/ensured {made} directories with .gitkeep")
    still = [d for d in need if not (REPO / d).is_dir()]
    if still:
        print(f"FAILED:p2-mkdirs {len(still)} dirs still absent: {still}")
        return 1
    print("SUCCESS:p2-mkdirs every READY output_path parent directory now exists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
