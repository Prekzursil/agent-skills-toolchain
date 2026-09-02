#!/usr/bin/env python3
"""Probe 1: mutation control — datetime.now() and dict-order leaks go red.

Both-states: the unmodified generator stays green; each mutant turns the
determinism test red. The reviewer-named import-time UUID stays green
(documented miss, not a failure of this probe).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

ART = REPO / "command-center/phase3/A2/TEST-PLAN.json"


def main() -> int:
    report = S.measure()
    clean = report["clean"]
    ts = report["timestamp_mutant"]
    order = report["dict_order_mutant"]
    uncaught = report["uncaught_import_time_uuid"]
    print(
        json.dumps(
            {
                "probe": "probe1-mutation",
                "unit_id": "ARC-0015",
                "clean_green": clean["pass"],
                "datetime_now_goes_red": ts["goes_red"],
                "dict_order_goes_red": order["goes_red"],
                "import_time_uuid_stays_green": uncaught["stays_green"],
                "generated_files": report["generated_files"],
                "pass": bool(
                    clean["pass"]
                    and ts["pass"]
                    and order["pass"]
                    and uncaught["stays_green"]
                ),
            },
            sort_keys=True,
        )
    )
    print(
        f"clean_green={clean['pass']} datetime_now_red={ts['goes_red']} "
        f"dict_order_red={order['goes_red']} "
        f"uncaught_uuid_green={uncaught['stays_green']} files={report['generated_files']}"
    )
    if not clean["pass"]:
        print("FAILED:ARC-0015-probe1 clean two-run was not byte-identical")
        return 1
    if not ts["goes_red"] or not ts["pass"]:
        print("FAILED:ARC-0015-probe1 datetime.now() mutant stayed green")
        return 1
    if not order["goes_red"] or not order["pass"]:
        print("FAILED:ARC-0015-probe1 dict-order mutant stayed green")
        return 1
    if not uncaught["stays_green"]:
        print("FAILED:ARC-0015-probe1 import-time UUID unexpectedly went red")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ARC-0015-probe1 TEST-PLAN.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0015-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0015" not in text:
        print("FAILED:ARC-0015-probe1 sentinel absent")
        return 1
    controls = doc.get("mutation_controls") or []
    ids = {c.get("id") for c in controls if isinstance(c, dict)}
    if "MUT-DATETIME-NOW" not in ids or "MUT-DICT-ORDER" not in ids:
        print(f"FAILED:ARC-0015-probe1 mutation_controls missing {ids}")
        return 1
    for row in controls:
        if row.get("id") in {"MUT-DATETIME-NOW", "MUT-DICT-ORDER"} and not row.get(
            "goes_red"
        ):
            print(f"FAILED:ARC-0015-probe1 artifact {row.get('id')} not red")
            return 1
    rev = doc.get("reviewer") or {}
    miss = rev.get("uncaught_mutation") or {}
    if not miss.get("id") or not miss.get("why_suite_misses_it"):
        print("FAILED:ARC-0015-probe1 reviewer did not name an uncaught mutation")
        return 1
    print("SUCCESS:ARC-0015-probe1 mutation control datetime.now and dict-order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
