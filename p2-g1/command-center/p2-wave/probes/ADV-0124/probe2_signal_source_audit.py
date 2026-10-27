#!/usr/bin/env python3
"""Probe 2: signal-source audit (mechanically different from the matrix).

If any state is inferred from file mtimes alone it is structurally
undecidable. Heartbeat-only projections of dead-monitor+live-work and
SIGSTOP stall collide; /proc state T separates them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from common import OUT_REL, REPO, SENTINEL, UNIT_ID  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    live = E.run_matrix()
    audit = live["source_audit"]
    printable = {
        "probe": "probe2-signal-source-audit",
        "unit_id": UNIT_ID,
        "pass": live["pass"],
        "mtime_used_any": live["mtime_used_any"],
        "source_audit_clean": audit["clean"],
        "classify_has_mtime_param": audit["classify_has_mtime_param"],
        "heartbeat_only_s2_s4_collide": live["heartbeat_only_s2_s4_collide"],
        "mtime_only_s3_s4_collide": live["mtime_only_s3_s4_collide"],
        "mtime_s1_silent": live["mtime_s1_silent"],
        "heartbeat_false_dead_on_s2": live["heartbeat_false_dead_on_s2"],
        "heartbeat_s1_silent": live["heartbeat_s1_silent"],
        "proc_s2_vs_s4": live["proc_s2_vs_s4"],
        "production_absent": live["production_absent"]["all_absent"],
    }
    print(json.dumps(printable, sort_keys=True, default=str))
    if live["mtime_used_any"]:
        return fail("monitor consulted file mtime")
    if not audit["clean"] or audit["classify_has_mtime_param"]:
        return fail("monitor source still admits mtime")
    if not live["heartbeat_only_s2_s4_collide"]:
        return fail("heartbeat-only S2/S4 did not collide")
    if not live["mtime_only_s3_s4_collide"]:
        return fail("mtime-only finished vs stalled did not collide")
    if not live["mtime_s1_silent"]:
        return fail("mtime-only was not silent on plainly-running")
    if not live["heartbeat_false_dead_on_s2"]:
        return fail("heartbeat-only did not false-dead S2")
    if not live["heartbeat_s1_silent"]:
        return fail("heartbeat-only was not silent on S1")
    if not live["proc_s2_vs_s4"]["distinct_when_proc_admitted"]:
        return fail("/proc did not separate S2 from S4")
    if not live["pass"]:
        return fail("live audit matrix did not pass")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    src = doc.get("source_audit") or {}
    if src.get("clean") is not True:
        return fail("artifact source_audit.clean is not true")
    if doc.get("mtime_used_any") is not False:
        return fail("artifact mtime_used_any is not false")
    nc = {n.get("id"): n for n in (doc.get("negative_controls") or [])}
    for nid in (
        "NC-SINGLE-SIGNAL-FALSE-DEAD",
        "NC-MTIME-AUDITOR-SENSITIVITY",
    ):
        row = nc.get(nid) or {}
        if not row.get("fired_on_bad_state") or not row.get("silent_on_good_state"):
            return fail(f"{nid} missing both-states")
    print(
        "SUCCESS:ADV-0124-probe2 signal-source audit "
        "mtime_clean heartbeat-only-collides mtime-only-collides"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
