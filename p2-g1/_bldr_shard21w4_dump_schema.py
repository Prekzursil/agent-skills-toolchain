"""Dump the resolved validator schema for my 12 units."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
from schema_resolver import validator_for  # noqa: E402

UNITS = [
    "WFA-0065", "WFA-0069", "WFA-0070", "WFA-0074",
    "WFA-0084", "WFA-0085", "WFA-0086", "WFA-0094",
    "WFA-0106", "WFA-0110", "WFA-0113",
]


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if u.get("id") in UNITS}
    for uid in UNITS:
        e = entries[uid]
        v = validator_for(e["output_schema"])
        s = v.schema
        props = s.get("properties", {})
        print("=" * 20, uid, e["output_schema"].split("#")[-1])
        print(" top-level allow:", sorted(props.keys()))
        req = s.get("required", [])
        print(" required:", req)
        ap = s.get("additionalProperties", "unset")
        print(" additionalProperties:", ap)
        # artifacts items shape
        art = props.get("artifacts", {})
        items = art.get("items", {}) if isinstance(art, dict) else {}
        if items:
            print(" artifacts.items props:", sorted((items.get("properties") or {}).keys()),
                  "required:", items.get("required"),
                  "role enum:", (items.get("properties") or {}).get("role", {}).get("enum"))
        ev = props.get("evidence", {})
        evi = ev.get("items", {}) if isinstance(ev, dict) else {}
        if evi:
            print(" evidence.items props:", sorted((evi.get("properties") or {}).keys()),
                  "required:", evi.get("required"))
        rv = props.get("reviewer", {})
        if isinstance(rv, dict) and rv:
            print(" reviewer props:", sorted((rv.get("properties") or {}).keys()),
                  "required:", rv.get("required"))
        ts = props.get("tests", {})
        tsi = ts.get("items", {}) if isinstance(ts, dict) else {}
        if tsi:
            print(" tests.items props:", sorted((tsi.get("properties") or {}).keys()),
                  "required:", tsi.get("required"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
