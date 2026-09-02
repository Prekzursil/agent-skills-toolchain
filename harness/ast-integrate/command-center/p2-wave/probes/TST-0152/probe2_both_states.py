#!/usr/bin/env python3
"""Probe 2: both-states control plus the 11-hour-finished statusline regression.

Known-good: live agent renders active; 11h-finished renders finished, not stalled.
Known-broken: mtime-only mutant reports the finished agent as stalled.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from fixtures import ACTIVE_AGENT, ELEVEN_H_S, FINISHED_11H, HUNG_AGENT, MTIME_ONLY  # noqa: E402
from mtime_mutant import classify_mtime_only  # noqa: E402
from monitorcore.cockpit import deployed_cockpit  # noqa: E402
from monitorcore.liveness import ACTIVE, FINISHED, STALLED, UNDECIDABLE  # noqa: E402
from monitorcore.panes import BaselineSource  # noqa: E402

UNIT = "TST-0152"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def by_id(pane: dict) -> dict:
    rows = ((pane.get("liveness") or {}).get("agents")) or []
    return {r["id"]: r for r in rows}


def main() -> int:
    source = BaselineSource(agents=[ACTIVE_AGENT, FINISHED_11H, HUNG_AGENT, MTIME_ONLY])
    cockpit = deployed_cockpit(source=source)
    pane = next(p for p in cockpit.render()["panes"] if p["id"] == "agentmon")
    rows = by_id(pane)

    live = rows.get("agent-live")
    done = rows.get("agent-11h-finished")
    hung = rows.get("agent-hung")
    mtime = rows.get("mtime-only")
    if not live or not done or not hung or not mtime:
        return fail(f"missing rows {sorted(rows)}")

    if live["state"] != ACTIVE:
        return fail(f"live agent rendered {live['state']!r} not {ACTIVE}")
    if ELEVEN_H_S != live.get("observational_mtime_age_s"):
        return fail("live fixture must carry the 11h mtime so mtime-alone would misfire")
    if done["state"] != FINISHED:
        return fail(f"11h-finished rendered {done['state']!r} not {FINISHED}")
    if done["state"] == STALLED:
        return fail("11h-finished rendered as stall (statusline regression)")
    if hung["state"] != STALLED:
        return fail(f"hung agent rendered {hung['state']!r} not {STALLED}")
    if "orchestrator_state" not in (hung.get("sources_used") or []):
        return fail("hung stall missing orchestrator_state")
    if not hung.get("independent_signals"):
        return fail("hung stall missing independent signal")
    if mtime["state"] != UNDECIDABLE:
        return fail(f"mtime-only record rendered {mtime['state']!r} not {UNDECIDABLE}")

    mutant_done = classify_mtime_only(FINISHED_11H)
    mutant_live = classify_mtime_only(ACTIVE_AGENT)
    mutant_mtime = classify_mtime_only(MTIME_ONLY)
    fired = (
        mutant_done["state"] == STALLED
        and mutant_done.get("stall_from_mtime_only") is True
        and mutant_mtime["state"] == STALLED
        and mutant_live["state"] == STALLED
    )
    if not fired:
        return fail(f"mtime mutant did not reproduce the statusline defect: {mutant_done}")
    if mutant_done["state"] == done["state"]:
        return fail("live classifier matched the mtime mutant on the 11h-finished fixture")
    if mutant_live["state"] == live["state"]:
        # mutant also stalls the live agent (old mtime); live classifier must differ
        if live["state"] != ACTIVE:
            return fail("live classifier failed to keep the old-mtime live agent active")

    text = "\n".join(pane.get("lines") or [])
    if "agent-11h-finished=finished" not in text:
        return fail(f"cockpit text missing finished render: {text!r}")
    if "agent-live=active" not in text:
        return fail(f"cockpit text missing active render: {text!r}")
    if "agent-11h-finished=stalled" in text:
        return fail("cockpit text reports 11h-finished as stalled")

    print(
        json.dumps(
            {
                "probe": "probe2-both-states",
                "unit_id": UNIT,
                "pass": True,
                "active_state": live["state"],
                "finished_11h_state": done["state"],
                "hung_state": hung["state"],
                "mtime_only_state": mtime["state"],
                "mutant_finished_state": mutant_done["state"],
                "mutant_fired_statusline_defect": True,
                "live_differs_from_mutant": mutant_done["state"] != done["state"],
                "eleven_h_s": ELEVEN_H_S,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0152-probe2 both-states + 11h-finished not stalled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
