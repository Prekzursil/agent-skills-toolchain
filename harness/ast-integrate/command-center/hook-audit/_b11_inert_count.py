"""O4 control: how many hooks did the fleet probe prove inert BY FIRING?

The round-2 report said "prior art fired 5 hooks to prove inertness"; the verifier
said B6 records 6. Neither is a reading of the FIELD -- both are readings of a
sentence. Count the field, and control the counter in both directions so a zero or
an inflated number cannot pass silently.
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
B6 = HERE / "B6-FLEET.json"


def main() -> int:
    data = json.loads(B6.read_text(encoding="utf-8"))
    # SELF-CORRECTION, kept deliberately: the first version of this probe read
    # data["inertness"] as the row list. It is a DICT -- the same one-level-too-high
    # collection error that produced four false parity readings earlier in this
    # program. It failed CLOSED (rc 2, "inertness is dict, expected list") instead of
    # counting dict KEY NAMES and reporting a plausible-looking 9. The rows are one
    # level down.
    inert = (data.get("inertness") or {}).get("rows")
    if not isinstance(inert, list):
        print(
            f"FAILED:inert-count inertness.rows is {type(inert).__name__}, expected list"
        )
        return 2

    verdicts = collections.Counter(row.get("verdict") for row in inert)

    # A verdict alone is not proof of firing. INERT-CONFIRMED must ALSO carry ran=true,
    # or the label is an assertion rather than a fired probe.
    fired = [
        r
        for r in inert
        if r.get("verdict") == "INERT-CONFIRMED" and r.get("ran") is True
    ]
    claimed = [r for r in inert if r.get("verdict") == "INERT-CONFIRMED"]

    # C1 POSITIVE: the collection must be non-trivially populated.
    c1 = len(inert) >= 5
    # C2 DISCRIMINATION: the counter must distinguish verdicts, not lump them.
    c2 = len(verdicts) >= 2
    # C3 BOTH-STATES: a hook that did NOT run must exist and must NOT be counted as
    # fired. Without this, "every row is INERT-CONFIRMED" would look identical.
    not_ran = [r for r in inert if r.get("ran") is not True]
    fired_names = {f.get("hook_dir") for f in fired}
    c3 = len(not_ran) >= 1 and all(
        r.get("hook_dir") not in fired_names for r in not_ran
    )
    # C4 BOTH-STATES on the LABEL: a row that was never fired must never carry
    # INERT-CONFIRMED. This is the control that separates "proven inert by firing"
    # from "asserted inert", which is the entire content of DoD item 2.
    c4 = not any(r.get("verdict") == "INERT-CONFIRMED" for r in not_ran)

    print(f"C1 collection populated (n={len(inert)}): {c1}")
    print(f"C2 verdicts discriminate ({dict(verdicts)}): {c2}")
    print(f"C3 non-fired rows exist and are excluded (n={len(not_ran)}): {c3}")
    print(f"C4 no non-fired row claims INERT-CONFIRMED: {c4}")
    print()
    print(f"INERT-CONFIRMED rows           : {len(claimed)}")
    print(f"INERT-CONFIRMED *and* ran=true : {len(fired)}")
    for r in sorted(fired, key=lambda r: r.get("hook_dir") or ""):
        print(
            f"    fired {r.get('hook_dir')}  wall_ms={r.get('wall_ms')} exit={r.get('exit')}"
        )
    for r in sorted(not_ran, key=lambda r: r.get("hook_dir") or ""):
        if r.get("verdict"):
            print(f"    NOT fired {r.get('hook_dir')}  verdict={r.get('verdict')}")

    if not (c1 and c2 and c3 and c4):
        print("FAILED:inert-count controls failed")
        return 2
    print(f"SUCCESS:inert-count {len(fired)} hooks proven inert BY FIRING")
    return 0


if __name__ == "__main__":
    sys.exit(main())
