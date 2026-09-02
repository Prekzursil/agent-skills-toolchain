#!/usr/bin/env python3
"""Probe 2: planted AGENTS.md channel + event-log attribution (process entry point)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import autoload as AL  # noqa: E402
import attribution as AT  # noqa: E402
import common as C  # noqa: E402
import load_probe as LP  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0139-probe2 {msg}")
    return 1


def main() -> int:
    planted = AL.planted_channel_test()
    if not planted.get("ran"):
        return fail(f"planted-config did not run {planted}")
    if not planted.get("binary_autoload_set_confirmed"):
        return fail("agent binary missing AGENTS.md in auto-load set")
    if not planted.get("marker_observed"):
        return fail("planted AGENTS.md marker was not auto-loaded")
    if not planted.get("negative_control_silent"):
        return fail("negative control still showed the marker")
    if not planted.get("decoy_readme_silent"):
        return fail("README.md decoy was treated as an instruction file")

    attr = AT.run_attribution()
    if not attr.get("reconstructed"):
        return fail(f"attribution control failed {attr.get('control')}")
    unattr = attr.get("unattributed") or []
    # Independent entry point: process table, not settings files.
    # G-1 remesure re-runs this probe without a guaranteed outer agent
    # session, so the load-bearing check is a probe-spawned control
    # re-found in /proc (same pattern as probe1's beacon). Pre-existing
    # cursor-agent rows are recorded honestly and are not a pass gate.
    with LP.proc_table_control() as (token, beacon_pid):
        rows = LP.iter_proc_cmdlines()
        control_hits = [(pid, cmd) for pid, cmd in rows if token in cmd]
        if not control_hits:
            return fail(
                "process-table re-enumeration missed the live control process"
            )
        if not any(pid == beacon_pid for pid, _cmd in control_hits):
            return fail(
                f"process-table control pid={beacon_pid} not in /proc hits"
            )
        agent_procs = LP.workspace_agent_rows(rows)

    art = C.REPO / C.OUT_REL
    if art.is_file():
        raw = art.read_text(encoding="utf-8")
        doc = json.loads(raw)
        errs = C.schema_errors(doc)
        if errs:
            return fail(f"artifact schema {errs[0]}")
        for garbage in (
            {},
            {"totally": "unrelated", "passing_tests": 999999},
            {"unit_id": "ADV-0139", "state": "SUCCESS"},
        ):
            if not C.schema_errors(garbage):
                return fail("schema accepted garbage")
        if C.COMPLETION_SENTINEL not in raw:
            return fail("completion_sentinel missing from artifact")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        loaded = [
            c
            for c in C.report_components(doc)
            if isinstance(c, dict) and c.get("load_verdict") == "LOADED"
        ]
        if not loaded:
            return fail("no LOADED components in artifact")
        for comp in loaded:
            kinds = {
                s.get("kind")
                for s in (comp.get("load_signals") or [])
                if isinstance(s, dict) and s.get("observed")
            }
            if "config" not in kinds or not (kinds & {"process", "session-log"}):
                return fail(f"loaded {comp.get('name')} missing two-signal evidence")
        unattr_list = C.report_unattributed(doc)
        if not isinstance(unattr_list, list):
            return fail("unattributed missing")
        print(f"artifact_ok loaded={len(loaded)} unattributed={len(unattr_list)}")

    payload = {
        "planted": planted,
        "attribution": {
            "reconstructed": attr["reconstructed"],
            "control_artifact": attr["control_artifact"],
            "unattributed_n": len(unattr),
        },
        "process_review": {
            "entry_point": "process-table",
            "control_token": LP.PROC_REVIEW_TOKEN,
            "control_reenumerated": True,
            "agent_processes": len(agent_procs),
            "workspace_hits": sum(1 for p in agent_procs if p["has_workspace"]),
            "outer_agent_optional": True,
        },
    }
    (HERE / "probe2-planted.raw.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "planted_marker_observed=True negative_silent=True "
        f"decoy_readme_silent=True attribution_reconstructed=True "
        f"unattributed={len(unattr)} process_agents={len(agent_procs)}"
    )
    print("SUCCESS:ADV-0139-probe2 planted-config channel and attribution control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
