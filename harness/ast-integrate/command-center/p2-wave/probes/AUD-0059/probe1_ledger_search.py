#!/usr/bin/env python3
"""Probe 1: search hook logs and event ledger for per-hook fire records.

Mechanically different from probe 2 (which triggers hooks). Known-present
planted fires must be found in BOTH parsers before live absence is reported.
A silent fixture must produce zero fires. Schema must reject garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_util as SU  # noqa: E402
import search as S  # noqa: E402

ART = REPO / "command-center/audit/AUD-0059-hook-firing-evidence.json"
SENTINEL = (
    "SUCCESS:AUD-0059 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0059-probe1 {msg}")
    return 1


def main() -> int:
    result = S.run_search()
    ctrl = result["detector_control"]
    print(
        json.dumps(
            {
                "probe": "probe1-ledger-search",
                "registered_ids": ctrl["registered_ids"],
                "planted_both_ids": ctrl["planted_both_ids"],
                "silent_union_ids": ctrl["silent_union_ids"],
                "known_present_fired": ctrl["known_present_fired"],
                "silent_fixture_empty": ctrl["silent_fixture_empty"],
                "live_present_count": result["live"]["inventory"]["present_count"],
                "live_log_present_count": result["live"].get("log_present_count"),
                "live_registered_n": result["live_registered_n"],
                "live_hit_ids": result["live"]["hit_ids"],
                "per_hook_live_turn_evidence": result["per_hook_live_turn_evidence"],
                "per_live_registered_turn_evidence": result[
                    "per_live_registered_turn_evidence"
                ],
                "pass": result["pass"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not ctrl["known_present_ran_first"]:
        return fail("known-present did not run first")
    if not ctrl["known_present_fired"]:
        return fail("planted fire records not found in both log and ledger parsers")
    if not ctrl["silent_fixture_empty"]:
        return fail(f"silent fixture produced hits {ctrl['silent_union_ids']}")
    if not ctrl["absence_reported_only_after"]:
        return fail("absence reported before known-present control")
    if not result["pass"]:
        return fail("searcher detector-control failed")

    garbage_n = SU.rejects_garbage()
    if garbage_n < 1:
        return fail("schema accepted garbage (vacuous schema)")
    print(f"schema_vacuity garbage_errors={garbage_n}")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("completion sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    errs = SU.errors_for(doc)
    if errs:
        print("schema_errors", errs[:8])
        return fail("artifact does not parse against output_schema")
    report = doc.get("report") or {}
    if report.get("kind") != "audit-detector-control":
        return fail("report.kind is not audit-detector-control")
    art_ctrl = report.get("detector_control") or {}
    if art_ctrl.get("known_present_fired") is not True:
        return fail("artifact detector_control.known_present_fired is not true")
    if art_ctrl.get("silent_fixture_empty") is not True:
        return fail("artifact detector_control.silent_fixture_empty is not true")
    ext = doc.get("extensions") or {}
    art_live = (ext.get("live_search") or {}).get("inventory") or {}
    if "present_count" not in art_live:
        return fail("artifact live_search.inventory.present_count missing")
    if int(art_live["present_count"]) != int(
        result["live"]["inventory"]["present_count"]
    ):
        return fail("artifact live present_count drifted from re-run")
    if len(ext.get("live_registered_ids") or []) != int(result["live_registered_n"]):
        return fail("artifact live_registered_ids drifted from re-run")
    print("SUCCESS:AUD-0059-probe1 ledger-search known-present then silent then live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
