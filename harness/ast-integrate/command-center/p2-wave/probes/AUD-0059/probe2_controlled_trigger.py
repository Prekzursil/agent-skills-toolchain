#!/usr/bin/env python3
"""Probe 2: controlled trigger + both-states disable/enable.

Disable one hook in a scratch config: trigger produces NO effect.
Re-enable: trigger produces an observable effect (inject / block / ledger).
A sibling hook on the same event must still fire while the target is disabled.
Log silence alone is not accepted as a fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import dispatch as D  # noqa: E402
import live_trigger as L  # noqa: E402
import schema_util as SU  # noqa: E402

ART = REPO / "command-center/audit/AUD-0059-hook-firing-evidence.json"
SENTINEL = (
    "SUCCESS:AUD-0059 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0059-probe2 {msg}")
    return 1


def main() -> int:
    result = D.run_trigger()
    live = L.run_live()
    bs = result["both_states"]
    print(
        json.dumps(
            {
                "probe": "probe2-controlled-trigger",
                "both_states_pass": bs["pass"],
                "disabled_produced_no_effect": bs["disabled_produced_no_effect"],
                "enabled_produced_effect": bs["enabled_produced_effect"],
                "verbatim_disabled": bs["verbatim_disabled"],
                "verbatim_enabled": bs["verbatim_enabled"],
                "sibling_id": bs["sibling_id"],
                "sibling_still_fired_while_target_disabled": bs[
                    "sibling_still_fired_while_target_disabled"
                ],
                "unknown_event_silent": result["unknown_event_silent"],
                "isolated_heartbeat": live["isolated_heartbeat"].get(
                    "observable_effect"
                ),
                "committed_windows_root": live["committed_manifest"].get(
                    "windows_root_on_linux"
                ),
                "subjects": [
                    {
                        "id": s["id"],
                        "event": s["event"],
                        "observable_effect": s["controlled_trigger"]["observable_effect"],
                        "two_signals": s["controlled_trigger"]["two_signals"],
                        "effect": s["controlled_trigger"]["effect"],
                    }
                    for s in result["subjects"]
                ],
                "pass": result["pass"] and live["pass"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not bs["disabled_produced_no_effect"]:
        return fail("disabled hook still produced an effect")
    if not bs["enabled_produced_effect"]:
        return fail("enabled hook produced no observable effect")
    if not bs["sibling_still_fired_while_target_disabled"]:
        return fail("disabling one hook silenced the whole event")
    if not result["unknown_event_silent"]:
        return fail("unknown event produced hook rows")
    if not result["all_hooks_observable"]:
        return fail("at least one registered hook lacked a two-signal effect")
    if not result["pass"]:
        return fail("controlled trigger both-states failed")
    if not live["isolated_heartbeat"].get("observable_effect"):
        return fail("isolated live heartbeat produced no inject-context")
    if not live["committed_manifest"].get("ran"):
        return fail("committed-manifest dispatcher trigger did not run")

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
    art_bs = report.get("both_states") or {}
    if art_bs.get("pass") is not True:
        return fail("artifact both_states.pass is not true")
    if art_bs.get("disabled_produced_no_effect") is not True:
        return fail("artifact missing disabled silence")
    if art_bs.get("enabled_produced_effect") is not True:
        return fail("artifact missing enabled fire")
    ext = doc.get("extensions") or {}
    subjects = ext.get("subjects") or []
    if len(subjects) < 4:
        return fail(f"artifact subjects {len(subjects)} < 4")
    for sub in subjects:
        trig = sub.get("controlled_trigger") or {}
        if trig.get("observable_effect") is not True:
            return fail(f"artifact subject {sub.get('id')} has no observable effect")
        if sub.get("live_turn_evidence") not in {"FOUND", "ABSENT", "NOT-CHECKED"}:
            return fail(f"artifact subject {sub.get('id')} live_turn_evidence invalid")
    obs = {o.get("name"): o.get("measured") for o in report.get("observations") or []}
    if obs.get("isolated_heartbeat_injects_health_banner") is not True:
        return fail("artifact missing isolated heartbeat observation")
    print("SUCCESS:AUD-0059-probe2 both-states disable-silent enable-fire two-signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
