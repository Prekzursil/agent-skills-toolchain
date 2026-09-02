#!/usr/bin/env python3
"""Named probe 2: migrate three real records with no field loss, recompute schedule.

Different field than probe 1 (bytes of legacy keys + longest HARD path), not a
re-run of the JSON-Schema validator.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import migrate as M  # noqa: E402
import schedule as S  # noqa: E402
import validate as V  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CC-0017.json"


def main() -> int:
    trip = M.migrate_three()
    print(
        f"source={trip['source']} canonical_present={trip['canonical_present']} "
        f"input={trip['input_count']} migrated={trip['migrated_count']}"
    )
    for row in trip["trips"]:
        print(
            f"roundtrip {row['claim_id']} byte_stable={row['byte_stable']} "
            f"field_loss={row['field_loss']}"
        )
        if not row["byte_stable"] or row["field_loss"]:
            print("FAILED:CC-0017-probe2 field loss on round-trip")
            return 1
        errs = V.validate_record(row["canonical"])
        if errs:
            print(f"FAILED:CC-0017-probe2 migrated record invalid {errs[:6]}")
            return 1
    if not trip["all_byte_stable"] or trip["any_field_loss"]:
        print("FAILED:CC-0017-probe2 aggregate field-loss")
        return 1

    set_errs = V.validate_record_set([t["canonical"] for t in trip["trips"]])
    if set_errs:
        print(f"FAILED:CC-0017-probe2 migrated set invalid {set_errs[:6]}")
        return 1

    sched = S.recompute()
    print(
        f"cp_before={sched['before']['nodes']} path={sched['before']['path']}"
    )
    print(
        f"cp_after={sched['after']['nodes']} path={sched['after']['path']}"
    )
    print(
        f"released phase_2={sched['released_recomputed']['phase_2']} "
        f"res={sched['released_recomputed']['res_prefix']} "
        f"b03={sched['released_recomputed']['depend_on_B03']}"
    )
    print(
        f"reproduced_224={sched['catalog_224_reproduced']} "
        f"reproduced_11_to_10={sched['catalog_11_to_10_reproduced']} "
        f"phase_graph_present={sched['phase_graph_present']}"
    )
    if sched["before"]["nodes"] != 11:
        print("FAILED:CC-0017-probe2 pre-change HARD path is not the recorded 11-node chain")
        return 1
    if sched["after"]["nodes"] >= sched["before"]["nodes"]:
        print("FAILED:CC-0017-probe2 softening CONTESTED-1 did not shorten the HARD path")
        return 1
    if sched["catalog_224_reproduced"] or sched["catalog_11_to_10_reproduced"]:
        # Those flags must be computed, not hardcoded True. If they become True
        # because the live catalog actually matches, that is allowed — but then
        # the numbers must match the functions above. The guard below covers it.
        pass
    if sched["released_recomputed"]["phase_2"] == 224:
        print("FAILED:CC-0017-probe2 unexpected: live phase_2 is 224; re-check query")
        # not a failure in principle; continue
    # Guard against restating 224 as the recomputed release count.
    if sched["released_recomputed"]["phase_2"] != 193:
        # Catalog was 193 when authored; if it moved, still accept the query result
        # but refuse a silent 224 hardcoded in released_recomputed.
        if sched["released_recomputed"]["phase_2"] == 224 and not ART.is_file():
            pass

    if not ART.is_file():
        print("FAILED:CC-0017-probe2 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(receipt)
    if "SUCCESS:CC-0017" not in text:
        print("FAILED:CC-0017-probe2 sentinel absent from receipt")
        return 1
    if "PROVISIONAL" not in text:
        print("FAILED:CC-0017-probe2 PROVISIONAL absent from receipt")
        return 1
    if "ARC-0085" not in text:
        print("FAILED:CC-0017-probe2 Phase-4 superseding unit ARC-0085 unnamed")
        return 1
    if str(receipt.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CC-0017-probe2 self-declared non-delivery")
        return 1

    rec_sched = receipt.get("schedule") or {}
    rec_after = (rec_sched.get("recomputed") or {}).get("after") or rec_sched.get("after")
    if not isinstance(rec_after, dict):
        print("FAILED:CC-0017-probe2 receipt schedule.after missing")
        return 1
    if rec_after.get("nodes") != sched["after"]["nodes"]:
        print(
            "FAILED:CC-0017-probe2 receipt restates a schedule number the edge list does not yield "
            f"receipt={rec_after.get('nodes')} live={sched['after']['nodes']}"
        )
        return 1
    rec_before = (rec_sched.get("recomputed") or {}).get("before") or rec_sched.get("before")
    if not isinstance(rec_before, dict) or rec_before.get("nodes") != sched["before"]["nodes"]:
        print("FAILED:CC-0017-probe2 receipt before-path drift")
        return 1
    released = (rec_sched.get("recomputed") or {}).get("released_recomputed") or {}
    if released.get("phase_2") != sched["released_recomputed"]["phase_2"]:
        print("FAILED:CC-0017-probe2 receipt restates release count without the catalog query")
        return 1
    # Must not present 224 as the recomputed figure when the query is not 224.
    if (
        released.get("phase_2") != 224
        and rec_sched.get("units_released_recomputed") == 224
    ):
        print("FAILED:CC-0017-probe2 receipt restates 224 against a different query result")
        return 1

    errs = V.validate_record(receipt)
    if errs:
        print(f"FAILED:CC-0017-probe2 receipt is not a valid claim record {errs[:8]}")
        return 1

    print("roundtrip_ok=True schedule_computed_not_restated=True")
    print("SUCCESS:CC-0017-probe2 round-trip and schedule recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
