#!/usr/bin/env python3
"""IMP-0438 measure: sixteen-row mutation table + honesty about M16.

Writes sixteen-row-table.json and battery-summary.json under this probe dir.
Does NOT invent an adversarial 17th review.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402

OUT_TABLE = HERE / "sixteen-row-table.json"
OUT_SUMMARY = HERE / "battery-summary.json"


def main() -> int:
    armed = B.run_battery(B.MUTATIONS, disarm=False)
    disarmed = B.run_battery(B.MUTATIONS, disarm=True)
    m17 = B.run_battery([B.SEVENTEENTH], disarm=False, include_control=False)
    m17_soft = B.run_battery([B.SEVENTEENTH], disarm=True, include_control=False)

    if armed["caught"] != 16 or armed["survivor_ids"]:
        print("FAILED:armed battery not 16/16", armed["survivor_ids"])
        return 1
    if armed["control"]["exit_code"] != 0:
        print("FAILED:CONTROL red under armed battery")
        return 1
    m01 = next(r for r in armed["rows"] if r["id"] == "M01")
    if not m01["caught"] or not m01["claimed_check_in_output"]:
        print("FAILED:control mutation M01 not caught with REACH-1 attribution")
        return 1

    by_a = {r["id"]: r for r in armed["rows"]}
    by_d = {r["id"]: r for r in disarmed["rows"]}
    table = []
    for spec in B.MUTATIONS:
        mid = spec["id"]
        soft = by_d[mid]
        hard = by_a[mid]
        row = {
            "id": mid,
            "name": spec["name"],
            "claimed_check": spec["claimed_check"],
            "historical_survivor": bool(spec.get("historical_survivor")),
            "pre_fix": {
                "surface": "disarmed --no-require-complete (tip)",
                "caught": soft["caught"],
                "exit_code": soft["exit_code"],
                "result": "CAUGHT" if soft["caught"] else "SURVIVES",
                "claimed_check_in_output": soft["claimed_check_in_output"],
            },
            "post_fix": {
                "surface": "bare CI / armed default",
                "caught": hard["caught"],
                "exit_code": hard["exit_code"],
                "result": "CAUGHT" if hard["caught"] else "SURVIVES",
                "claimed_check_in_output": hard["claimed_check_in_output"],
            },
        }
        if mid == "M16":
            row["honesty"] = {
                "catalog_historical_pre_fix": "SURVIVES (exit 0 under bare CI before IMP-0436/0437)",
                "tip_disarmed_measured": (
                    f"CAUGHT exit={soft['exit_code']} via V-DEFAULTS "
                    "(IMP-0436 always-on); historical sole-survivor-when-disarmed "
                    "claim is REFUTED on this tip and not invented as exit 0"
                ),
                "closed_by": [
                    "IMP-0436:V-DEFAULTS",
                    "IMP-0437:require_complete_default",
                ],
            }
        table.append(row)

    m16 = by_a["M16"]
    m17a = m17["rows"][0]
    m17d = m17_soft["rows"][0]

    summary = {
        "unit": "IMP-0438",
        "battery_size": 16,
        "armed_caught": armed["caught"],
        "armed_survivors": armed["survivor_ids"],
        "disarmed_caught": disarmed["caught"],
        "disarmed_survivors": disarmed["survivor_ids"],
        "control_exit_armed": armed["control"]["exit_code"],
        "m01_still_caught": m01["caught"],
        "surviving_mutation_closed": {
            "id": "M16",
            "name": "delete-entire-defaults-block",
            "named_before_fix": True,
            "historical_pre_fix": "SURVIVES",
            "tip_armed_post_fix": "CAUGHT" if m16["caught"] else "SURVIVES",
            "tip_armed_exit": m16["exit_code"],
            "tip_disarmed_exit": by_d["M16"]["exit_code"],
            "unprotected_behavior_historical": (
                "V-FIELDS only appended violations when require_complete was True; "
                "bare CI defaulted that flag to False, so deleting catalog.defaults "
                "printed SUCCESS while Prompt Two fields were unresolved."
            ),
        },
        "known_expansion_control_m17": {
            "id": "M17",
            "role": "known-expansion-control-not-adversarial-review",
            "armed_caught": m17a["caught"],
            "armed_exit": m17a["exit_code"],
            "disarmed_caught": m17d["caught"],
            "disarmed_exit": m17d["exit_code"],
            "note": (
                "M17 is retained as a regression control. Catalog "
                "reviewer_requirement still demands an adversarial refuter design "
                "a novel seventeenth mutation the battery has never seen; M17 does "
                "not satisfy that gate."
            ),
        },
        "adversarial_17th_slot": {
            "status": "AWAITING",
            "reserved_for": "adversarial-refuter novel mutation",
            "known_ids_excluded": [m["id"] for m in B.MUTATIONS] + ["M17"],
        },
        "ok": bool(
            armed["caught"] == 16
            and not armed["survivor_ids"]
            and armed["control"]["exit_code"] == 0
            and m01["caught"]
            and m16["caught"]
            and m17a["caught"]
        ),
    }

    OUT_TABLE.write_text(
        json.dumps({"unit": "IMP-0438", "rows": table}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    OUT_SUMMARY.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": summary["ok"],
                "armed": f"{armed['caught']}/16",
                "disarmed_survivors": disarmed["survivor_ids"],
                "m16_armed": m16["exit_code"],
                "m16_disarmed": by_d["M16"]["exit_code"],
                "m17_armed": m17a["exit_code"],
                "table": str(OUT_TABLE.relative_to(B.REPO)),
            },
            indent=2,
        )
    )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
