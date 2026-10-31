"""D5 pre-flight: validate the NORMALISED catalog in memory before anything is written.

Applies the d5 transform to an in-memory copy, then runs the project's own profile validators
over it. Reports the assigned_model_vendor_role contribution to the strict histogram and the
total pass/fail per profile, so the write decision is made on measured output rather than hope.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(HERE))

from wfdsl import schemas  # noqa: E402

from d5_normalize_assignment import CATALOG, FIELD, normalize_unit  # noqa: E402


def profile_counts(units: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for profile in ("structural", "normative", "strict"):
        v = schemas.work_unit_validator(profile)
        hist: dict[str, int] = {}
        fail = 0
        field_fail = 0
        for u in units:
            errs = list(v.iter_errors(u))
            if errs:
                fail += 1
            for e in errs:
                path = "/".join(str(p) for p in e.absolute_path) or "<root>"
                hist[f"{path} [{e.validator}]"] = (
                    hist.get(f"{path} [{e.validator}]", 0) + 1
                )
                if path.startswith(FIELD):
                    field_fail += 1
        out[profile] = {
            "pass": len(units) - fail,
            "fail": fail,
            f"{FIELD}_errors": field_fail,
            "top": dict(sorted(hist.items(), key=lambda kv: -kv[1])[:8]),
        }
    return out


def main() -> int:
    doc = json.loads(CATALOG.read_bytes().decode("utf-8"))
    before = [dict(u) for u in doc["work_units"]]

    after = []
    changed = 0
    for u in doc["work_units"]:
        u2 = dict(u)
        val, kind = normalize_unit(u2)
        if kind:
            u2[FIELD] = val
            changed += 1
        after.append(u2)

    print(f"units={len(before)}  would change={changed}\n")
    for label, units in (("BEFORE", before), ("AFTER", after)):
        print(f"===== {label} =====")
        for profile, c in profile_counts(units).items():
            print(
                f"  {profile:11s} pass={c['pass']:5d} fail={c['fail']:4d} "
                f"{FIELD}_errors={c[f'{FIELD}_errors']}"
            )
            for k, n in c["top"].items():
                print(f"        {n:5d}  {k}")
        print()

    # the canonical-shape claim, asserted on the AFTER state
    nonobj = [u["id"] for u in after if not isinstance(u.get(FIELD), dict)]
    print(f"AFTER: units whose {FIELD} is not an object = {len(nonobj)} {nonobj[:5]}")
    multi = [u["id"] for u in after if "co_assignments" in u.get(FIELD, {})]
    print(f"AFTER: units declaring co_assignments = {len(multi)} {multi}")
    print(
        "SUCCESS:d5-preflight"
        if not nonobj
        else f"FAILED:d5-preflight residual={len(nonobj)}"
    )
    return 0 if not nonobj else 1


if __name__ == "__main__":
    sys.exit(main())
