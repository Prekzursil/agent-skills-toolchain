"""Collapse the walk's junction aliases -- the raw checkout count is inflated, not a count.

`enumerate_checkouts.py` walked 4,447 `.git` locations. That number is WRONG as a count of
checkouts, and the tell is in its own distribution:

    2553  C:/Users/Prekzursil/Local Settings/Application Data
     835  C:/Users/Prekzursil/Local Settings/Temp
      50  C:/Users/Prekzursil/Documents/GitHub
      50  C:/Users/Prekzursil/My Documents/GitHub      <- same 50, second alias

`Local Settings` and `My Documents` are legacy Windows compatibility JUNCTIONS pointing at
`AppData/Local` and `Documents`. The SKIP set excludes `AppData` by name, so the walk refuses
the real path and then walks straight into it through the alias. Two names, one directory,
counted twice -- and `Documents/GitHub` vs `My Documents/GitHub` at exactly 50 each is the
signature.

A suspiciously equal pair on both sides is the estate's own tell for a collection-level
mistake rather than a real quantity, so this resolves every path to its real location and
collapses duplicates. Runs offline against `walk-paths.json` -- no re-walk.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALK = HERE / "walk-paths.json"
OUT = HERE / "walk-dedup.json"


def main() -> int:
    data = json.loads(WALK.read_text(encoding="utf-8"))
    paths = data["paths"]

    # --- CONTROL: realpath must actually collapse a KNOWN alias pair, and must NOT
    # collapse two genuinely different directories. Without both, a dedupe that did
    # nothing (or everything) would look like a result.
    a = "C:/Users/Prekzursil/Documents"
    b = "C:/Users/Prekzursil/My Documents"
    c = "C:/Users/Prekzursil/source"
    ra, rb, rc = (os.path.realpath(x).replace("\\", "/").lower() for x in (a, b, c))
    ctl = {
        "alias_pair": [a, b],
        "alias_resolves_equal": ra == rb,
        "distinct_pair": [a, c],
        "distinct_resolves_equal": ra == rc,
        "discriminates": (ra == rb) and (ra != rc),
    }
    print(
        f"CONTROL: '{a}' == '{b}' -> {ctl['alias_resolves_equal']}; "
        f"'{a}' == '{c}' -> {ctl['distinct_resolves_equal']}; "
        f"discriminates={ctl['discriminates']}"
    )
    if not ctl["discriminates"]:
        print("FAILED:dedupe-walk realpath does not discriminate alias from distinct")
        return 3

    seen: dict[str, str] = {}
    dupes = []
    for p in paths:
        rp = os.path.realpath(p).replace("\\", "/").rstrip("/").lower()
        if rp in seen:
            dupes.append({"alias": p, "first_seen": seen[rp], "real": rp})
        else:
            seen[rp] = p

    print(f"\nraw walk entries      : {len(paths)}")
    print(f"distinct real paths   : {len(seen)}")
    print(f"junction duplicates   : {len(dupes)}")

    pref = Counter()
    for d in dupes:
        pref["/".join(d["alias"].split("/")[:5])] += 1
    print("\nwhere the duplicates came from:")
    for k, v in pref.most_common(8):
        print(f"  {v:6d}  {k}")

    OUT.write_text(
        json.dumps(
            {
                "control": ctl,
                "raw": len(paths),
                "distinct": len(seen),
                "duplicates": len(dupes),
                "duplicate_examples": dupes[:20],
                "distinct_paths": sorted(seen.values()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    print(
        f"SUCCESS:dedupe-walk raw={len(paths)} distinct={len(seen)} dupes={len(dupes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
