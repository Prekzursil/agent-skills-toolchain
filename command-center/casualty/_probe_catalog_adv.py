r"""Pull the AUTHORITATIVE unit specs for the ADV-* family out of WORK-UNIT-CATALOG.json.

The spawn prompt says the contract is in the catalog, not in the filename ("READ YOUR OWN UNIT
SPEC FIRST... Do not work from this prompt's summary alone"). So the census denominator and both
casualty contracts must come from here.

Writes:
  casualty/recovered/<UNIT>-spec.json  full catalog entry for each requested unit
  casualty/ADV-UNIT-INDEX.json         every ADV-* unit: id, title, output_path, deps, status
Prints a one-line summary per requested unit plus the family totals.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
OUT = REPO / "command-center" / "casualty"


def main(argv: list[str]) -> int:
    wanted = [a.upper() for a in argv] or ["ADV-0021", "ADV-0022", "ADV-0002"]
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = data.get("work_units")
    if not isinstance(units, list):
        print(f"FAILED:catalog work_units missing; top keys={sorted(data)[:20]}")
        return 1
    print(f"catalog units={len(units)}  top-level keys={sorted(data)}")

    by_id = {}
    for u in units:
        uid = u.get("id")
        if isinstance(uid, str):
            by_id[uid] = u

    adv = {k: v for k, v in by_id.items() if k.upper().startswith("ADV-")}
    print(f"ADV-* units in catalog: {len(adv)}")
    if adv:
        sample = next(iter(adv.values()))
        print(f"unit entry keys: {sorted(sample.keys())}")

    (OUT / "recovered").mkdir(parents=True, exist_ok=True)
    index = []
    for uid in sorted(adv):
        u = adv[uid]
        op = u.get("output_path") or ""
        f = REPO / op if op else None
        index.append(
            {
                "id": uid,
                "title": u.get("title"),
                "output_path": op,
                "artifact_exists": bool(f and f.is_file()),
                "artifact_bytes": f.stat().st_size if (f and f.is_file()) else 0,
                "status": u.get("status"),
                "state": u.get("state"),
                "dependencies": u.get("dependencies"),
                "assigned_vendor": u.get("assigned_vendor") or u.get("vendor"),
                "owner_gate": u.get("owner_gate") or u.get("owner_gated"),
            }
        )
    (OUT / "ADV-UNIT-INDEX.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    for uid in wanted:
        u = by_id.get(uid)
        if not u:
            print(f"\n##### {uid}: NOT PRESENT IN CATALOG (absent from work_units[])")
            continue
        (OUT / "recovered" / f"{uid}-spec.json").write_text(
            json.dumps(u, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"\n##### {uid}: present. output_path={u.get('output_path')!r} "
            f"status={u.get('status')!r} deps={u.get('dependencies')!r} "
            f"spec_bytes={len(json.dumps(u))}"
        )
    print("\nSUCCESS:catalog")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
