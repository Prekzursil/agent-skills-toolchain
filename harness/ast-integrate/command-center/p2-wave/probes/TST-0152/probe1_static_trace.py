#!/usr/bin/env python3
"""Probe 1: static source trace of every cockpit liveness field.

PASS: classify_agent has no mtime in control-flow tests; every rendered
liveness field traces to orchestrator/heartbeat/process, never file mtime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from ast_trace import scan_file  # noqa: E402
from fixtures import ACTIVE_AGENT, FINISHED_11H, HUNG_AGENT, MTIME_ONLY  # noqa: E402
from monitorcore.cockpit import deployed_cockpit  # noqa: E402
from monitorcore.liveness import (  # noqa: E402
    ACTIVE,
    FINISHED,
    STALLED,
    UNDECIDABLE,
    classify_agent,
)
from monitorcore.panes import BaselineSource  # noqa: E402

UNIT = "TST-0152"
LIVENESS_PY = REPO / "tools/monitorcore/monitorcore/liveness.py"
ALLOWED_SOURCES = {"orchestrator_state", "heartbeat", "process_signal"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def field_traces(pane: dict) -> list[dict]:
    traces = []
    live = pane.get("liveness") or {}
    traces.append(
        {
            "field": "agentmon.liveness.mtime_only_stall_banned",
            "value": live.get("mtime_only_stall_banned"),
            "source": "liveness-policy",
        }
    )
    for row in live.get("agents") or []:
        traces.append(
            {
                "field": f"agentmon.liveness.agents[{row.get('id')}].state",
                "value": row.get("state"),
                "source": row.get("source"),
                "sources_used": row.get("sources_used"),
                "mtime_used_as_predicate": row.get("mtime_used_as_predicate"),
                "stall_from_mtime_only": row.get("stall_from_mtime_only"),
            }
        )
    return traces


def main() -> int:
    if not LIVENESS_PY.is_file():
        return fail(f"missing {LIVENESS_PY}")
    static = scan_file(LIVENESS_PY)
    if not static["ok"]:
        return fail(f"mtime in classify_agent control flow: {static}")
    if not static.get("observational_copy_present"):
        return fail("observational mtime copy missing; cannot prove it is unused")

    source = BaselineSource(
        agents=[ACTIVE_AGENT, FINISHED_11H, HUNG_AGENT, MTIME_ONLY]
    )
    cockpit = deployed_cockpit(source=source)
    rendered = cockpit.render()
    agentmon = next(p for p in rendered["panes"] if p["id"] == "agentmon")
    traces = field_traces(agentmon)
    if len(traces) < 5:
        return fail(f"too few liveness fields traced: {len(traces)}")

    by_id = {r["id"]: r for r in (agentmon.get("liveness") or {}).get("agents") or []}
    expected = {
        "agent-live": ACTIVE,
        "agent-11h-finished": FINISHED,
        "agent-hung": STALLED,
        "mtime-only": UNDECIDABLE,
    }
    for aid, want in expected.items():
        row = by_id.get(aid)
        if row is None:
            return fail(f"missing classified agent {aid}")
        if row["state"] != want:
            return fail(f"{aid} state={row['state']!r} want={want!r} via={row.get('source')}")
        if row.get("mtime_used_as_predicate") is not False:
            return fail(f"{aid} marked mtime as predicate")
        if row.get("stall_from_mtime_only"):
            return fail(f"{aid} stall_from_mtime_only")
        if row["state"] == STALLED:
            used = set(row.get("sources_used") or [])
            if "orchestrator_state" not in used:
                return fail(f"{aid} stall without orchestrator_state")
            if not (used & {"heartbeat", "process_signal"}):
                return fail(f"{aid} stall without independent signal")
            if "mtime" in str(row.get("source")):
                return fail(f"{aid} stall source names mtime")

    for tr in traces:
        if tr["field"].endswith(".state"):
            src = str(tr.get("source") or "")
            if src in {"file_mtime", "mtime"} or src.startswith("mtime"):
                return fail(f"liveness field sourced from mtime: {tr}")
            used = set(tr.get("sources_used") or [])
            if used and not used.issubset(ALLOWED_SOURCES | {"orchestrator_state"}):
                # sources_used should only be orchestrator/heartbeat/process
                extra = used - ALLOWED_SOURCES
                if extra:
                    return fail(f"unexpected sources {extra} in {tr}")

    # Direct classifier agrees with pane (same code path).
    for rec, want in (
        (ACTIVE_AGENT, ACTIVE),
        (FINISHED_11H, FINISHED),
        (HUNG_AGENT, STALLED),
        (MTIME_ONLY, UNDECIDABLE),
    ):
        got = classify_agent(rec)
        if got["state"] != want:
            return fail(f"direct classify {rec['id']}={got['state']} want={want}")

    print(
        json.dumps(
            {
                "probe": "probe1-static-trace",
                "unit_id": UNIT,
                "pass": True,
                "static": static,
                "field_traces": traces,
                "classified": expected,
                "mtime_only_stall_banned": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0152-probe1 static liveness source trace; mtime-only stall absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
