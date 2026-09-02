"""Sixth pass: settling probe for the ' profile=<name>' claim, plus a KNOWN-PRESENT /
KNOWN-BROKEN detector control (a probe silent in both states measures nothing).

Question: the 118 units whose output_schema carries ' profile=<name> (required: ...)' --
is that profile's required-field set enforced anywhere, or is it dropped?

Control A (KNOWN-PRESENT): a profile name that IS a $defs key in artifact-class-profiles
must be reported as PRESENT. If the detector cannot find a key it is known to contain,
the detector is broken and its negatives mean nothing.
Control B (KNOWN-ABSENT): a synthetic nonsense profile name must be reported ABSENT.

Run: python platform/architecture/_mkt_measure6.py
"""

import json
import os
import re
import sys
from collections import Counter

REPO = "C:/Users/Prekzursil/source/ast-integrate"
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))


def main():
    acp_path = os.path.join(REPO, "platform/schema/artifact-class-profiles.schema.json")
    with open(acp_path, encoding="utf-8") as f:
        acp = json.load(f)
    defs = set(acp.get("$defs", {}).keys())
    print("artifact-class-profiles.schema.json $defs count:", len(defs))
    print("  sample $defs:", sorted(defs)[:10])
    print()

    # --- detector controls -------------------------------------------------
    known_present = sorted(defs)[0] if defs else None
    print("=== DETECTOR CONTROLS ===")
    print(
        f"  Control A KNOWN-PRESENT  {known_present!r} in $defs -> "
        f"{known_present in defs}  (must be True)"
    )
    print(
        f"  Control B KNOWN-ABSENT   'zzz-not-a-real-profile' in $defs -> "
        f"{'zzz-not-a-real-profile' in defs}  (must be False)"
    )
    ok = (known_present in defs) and ("zzz-not-a-real-profile" not in defs)
    print("  detector usable:", ok)
    if not ok:
        print("FAILED:mkt-measure6 detector-control")
        return 1
    print()

    # --- the actual question ----------------------------------------------
    with open(
        os.path.join(REPO, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"
    ) as f:
        wu = json.load(f)["work_units"]
    prof_units = [u for u in wu if " profile=" in str(u.get("output_schema", ""))]
    names = Counter()
    for u in prof_units:
        m = re.search(r" profile=([^\s(]+)", str(u["output_schema"]))
        if m:
            names[m.group(1)] += 1
    print("=== ' profile=' CLAIM ===")
    print("  units carrying ' profile=':", len(prof_units))
    print("  distinct profile names    :", len(names))
    present = {n for n in names if n in defs}
    absent = {n for n in names if n not in defs}
    print(
        "  profile names that ARE an artifact-class $defs key:",
        len(present),
        sorted(present)[:8],
    )
    print("  profile names that are NOT a $defs key            :", len(absent))
    for n in sorted(absent):
        print(f"      NO-DEF: {n}  ({names[n]} units)")
    units_absent = sum(names[n] for n in absent)
    print(
        f"  units whose declared profile has NO schema definition: {units_absent}"
        f" / {len(prof_units)}"
    )
    print()

    # --- does the resolver route them anywhere? ---------------------------
    from schema_resolver import resolve  # noqa: E402

    print("=== where does resolve() send a ' profile=' ref? ===")
    seen = set()
    for u in prof_units[:400]:
        m = re.search(r" profile=([^\s(]+)", str(u["output_schema"]))
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        try:
            r = resolve(u["output_schema"])
            print(
                f"  profile={m.group(1):34s} -> physical={r.physical_path}"
                f"  frag={r.physical_fragment}"
            )
        except Exception as e:  # noqa: BLE001
            print(
                f"  profile={m.group(1):34s} -> resolve RAISED {type(e).__name__}: {e}"
            )
        if len(seen) >= 8:
            break
    print()
    print("SUCCESS:mkt-measure6")
    return 0


if __name__ == "__main__":
    sys.exit(main())
