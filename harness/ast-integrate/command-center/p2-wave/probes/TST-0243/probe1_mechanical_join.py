#!/usr/bin/env python3
"""Probe 1: mechanical join of catalog timeouts to the live run ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from join import load_catalog_units, join  # noqa: E402
from ledger import harvest  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0243.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SENTINEL = "SUCCESS:TST-0243"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    units = load_catalog_units(CATALOG)
    led = harvest(write=True)
    result = join(units, led["durations_by_class"])
    payload = {
        "probe": "probe1-mechanical-join",
        "unit_id": "TST-0243",
        "ledger_source": led["source"],
        "n_ledger_records": led["n_records"],
        "n_catalog_units": len(units),
        "n_classes": result["n_classes"],
        "n_compared": result["n_compared"],
        "n_defects": result["n_defects"],
        "n_adequate": result["n_adequate"],
        "n_no_samples": result["n_no_samples"],
        "margin_declared": result["margin_declared"],
        "eyeballed": result["eyeballed"],
        "defects": result["defects"],
        "rows": result["rows"],
        "pass": False,
    }
    catalog_classes = sorted({u["id"].split("-")[0] for u in units})
    join_classes = [r["class"] for r in result["rows"]]
    if join_classes != catalog_classes:
        payload["error"] = f"class-set-mismatch join={join_classes} catalog={catalog_classes}"
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("FAILED:TST-0243-probe1 class set was not computed from the catalog")
        return 1
    if result["eyeballed"] is not False:
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("FAILED:TST-0243-probe1 join marked eyeballed")
        return 1
    if result["n_classes"] < 1:
        print(json.dumps(payload, indent=2, sort_keys=True))
        print("FAILED:TST-0243-probe1 empty join")
        return 1
    for row in result["rows"]:
        if row["verdict"] == "DEFECT":
            if row.get("proposed_new_timeout_seconds") is None:
                print(json.dumps(payload, indent=2, sort_keys=True))
                print("FAILED:TST-0243-probe1 defect missing proposed_new_timeout", row["class"])
                return 1
            if row["adequate"] is not False:
                print(json.dumps(payload, indent=2, sort_keys=True))
                print("FAILED:TST-0243-probe1 defect marked adequate", row["class"])
                return 1
        if row["verdict"] == "ADEQUATE" and row["adequate"] is not True:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0243-probe1 adequate polarity", row["class"])
            return 1
        if row["n_samples"] == 0 and row["verdict"] != "NO-SAMPLES":
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0243-probe1 empty class not NO-SAMPLES", row["class"])
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0243-probe1 self-declared", st)
            return 1
        if SENTINEL not in text:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0243-probe1 sentinel-absent")
            return 1
        rec_rows = (doc.get("join") or {}).get("rows") or []
        rec_classes = [r.get("class") for r in rec_rows if isinstance(r, dict)]
        if rec_classes != catalog_classes:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0243-probe1 receipt join missing a catalog class")
            return 1
        if (doc.get("join") or {}).get("eyeballed") is not False:
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:TST-0243-probe1 receipt join was eyeballed")
            return 1

    payload["pass"] = True
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"classes={result['n_classes']} compared={result['n_compared']} "
        f"defects={result['n_defects']} ledger={led['n_records']}"
    )
    print("SUCCESS:TST-0243-probe1 mechanical join over catalog and run ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
