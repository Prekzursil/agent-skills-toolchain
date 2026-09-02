#!/usr/bin/env python3
"""Probe 2: all 20 declared rows executed; unreproducible downgraded, none deleted."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import confirm as C  # noqa: E402

OUT = HERE / "probe2-twenty-rows.raw.json"


def main() -> int:
    cmap = C.load_map()
    declared_ids = [r["id"] for r in cmap["rows"]]
    bundle = C.run_all()
    result_ids = [r["id"] for r in bundle["rows"]]
    errors = C.predicates(bundle)
    if declared_ids != result_ids:
        errors.append(f"id order/set changed declared={declared_ids} result={result_ids}")
    if set(declared_ids) - set(result_ids):
        errors.append("a declared row was deleted")

    suspected = [r["id"] for r in bundle["rows"] if r["verdict"] == "SUSPECTED"]
    confirmed = [r["id"] for r in bundle["rows"] if r["verdict"] == "CONFIRMED"]
    for row in bundle["rows"]:
        if row["verdict"] == "CONFIRMED":
            obs = row["observed"]
            if not obs.get("live_hit"):
                errors.append(f"{row['id']} CONFIRMED without live observation")
            if row["declared_kind"] == "SHARED_FILE" and not obs.get("target"):
                errors.append(f"{row['id']} missing collision path")
            if row["declared_kind"] == "SHARED_PLANE" and not obs.get("target"):
                errors.append(f"{row['id']} missing collision plane")
            if row["declared_kind"] == "INCOMPATIBLE_STOP" and not obs.get("live_stop"):
                errors.append(f"{row['id']} missing stop observation")

    # Independent recount from the fixture file, not from confirm's counter.
    fixture_n = len(json.loads((HERE / "fixtures" / "conflict_map.json").read_text())["rows"])
    if fixture_n != 20:
        errors.append(f"fixture recount {fixture_n} != 20")

    doc = {
        "probe": "probe2-twenty-rows-and-downgrade",
        "unit_id": "WFA-0150",
        "fixture_count": fixture_n,
        "declared_ids": declared_ids,
        "result_ids": result_ids,
        "confirmed": confirmed,
        "suspected": suspected,
        "deleted": bundle["deleted_ids"],
        "confirmed_count": bundle["confirmed_count"],
        "suspected_count": bundle["suspected_count"],
        "pass": not errors,
        "errors": errors,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fixture={fixture_n} confirmed={len(confirmed)} suspected={len(suspected)} "
        f"deleted={bundle['deleted_count']} suspected_ids={suspected}"
    )
    if errors:
        print("FAILED:WFA-0150-probe2 " + "; ".join(errors))
        return 1
    print(
        "SUCCESS:WFA-0150-probe2 20 rows executed; unreproducible downgraded "
        "to SUSPECTED; none deleted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
