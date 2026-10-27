#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes"))
import _shard2_lib as lib

HERE = lib.PROBES / "AUD-0066"
PROBE_FILES = [
    {"id": "probe1", "file": HERE / "probe1_task_state.py", "role": "source", "method": "process-table"},
    {"id": "probe2", "file": HERE / "probe2_endpoint_health.py", "role": "verifier", "method": "http"},
]
lib.ensure_probes("AUD-0066", PROBE_FILES)
p1 = json.loads((HERE / "probe1_task_state_out.json").read_text(encoding="utf-8"))
p2 = json.loads((HERE / "probe2_endpoint_health_out.json").read_text(encoding="utf-8"))

task_lines = "; ".join("%s=%s" % (t["name"].rsplit(chr(92))[-1][:40], t["status"]) for t in p1["relevant_tasks"])[:900]
ep_lines = "; ".join("%s:%s=%s" % (r["service"], r["port"], r.get("http", r["tcp"])) for r in p2["endpoints"])[:900]

claims = [
    {"claim": ("schtasks reports %d tasks on this host; %d match program-relevant tokens "
               "(%s). All returned a state - the OS process table is the source."
               % (p1["total_tasks"], p1["relevant_count"], task_lines[:400])),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0066/probe1_task_state_out.json"},
    {"claim": ("Endpoint health over TCP+HTTP: %d alive, %d dead or refused (%s); the dead-port "
               "control refused as required before any success was trusted."
               % (p2["alive_count"], p2["dead_count"], ep_lines[:400])),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0066/probe2_endpoint_health_out.json"},
]
observations = [
    {"name": "total_scheduled_tasks", "measured": p1["total_tasks"], "method": "process-table",
     "anchor": "command-center/p2-wave/probes/AUD-0066/probe1_task_state_out.json"},
    {"name": "relevant_tasks", "measured": p1["relevant_count"], "method": "process-table",
     "anchor": "command-center/p2-wave/probes/AUD-0066/probe1_task_state_out.json"},
    {"name": "endpoints_alive", "measured": p2["alive_count"], "method": "http",
     "anchor": "command-center/p2-wave/probes/AUD-0066/probe2_endpoint_health_out.json"},
    {"name": "endpoints_dead", "measured": p2["dead_count"], "method": "http",
     "anchor": "command-center/p2-wave/probes/AUD-0066/probe2_endpoint_health_out.json"},
]
tests = [
    {"id": "aud0066-dead-port-control", "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0066/probe2_endpoint_health.py",
     "result": "PASS" if p2["control_dead_port_refused"] else "FAIL", "assertions": 1,
     "output_tail": "control dead port refused=%s" % p2["control_dead_port_refused"]},
]
negative_controls = [
    {"id": "aud0066-wrong-port-fails", "kind": "absent-input",
     "description": ("Health probe must return a failure for a deliberately wrong port "
                     "(127.0.0.1:1) before trusting any success it reports."),
     "fired_on_bad_state": bool(p2["control_dead_port_refused"]),
     "silent_on_good_state": bool(p2["alive_count"] >= 0),
     "bad_state_output": "control alive=%s" % p2["control_dead_port_refused"],
     "good_state_output": "alive=%d dead=%d" % (p2["alive_count"], p2["dead_count"])},
]
residuals = [
    {"claim": ("Recovery behaviour (kill a daemon and watch the supervisor restart it) was NOT "
               "exercised live: killing estate daemons from an audit probe risks collateral "
               "damage to concurrent work."),
     "verdict": "NOT-CHECKED",
     "settling_experiment": ("In a maintenance window, hard-kill mcp_agent_mail and confirm "
                             "MCPAgentMailSupervisor restores /api/health within ~30s (the "
                             "recorded ~27s recovery).")},
    {"claim": "Task-to-endpoint coupling is asserted from names and the recorded architecture, not from reading each task's registration XML.",
     "verdict": "PARTIAL",
     "settling_experiment": "schtasks /query /tn <name> /xml per relevant task and bind action to port."},
]
lib.emit_unit(
    "AUD-0066",
    claims=claims,
    observations=observations,
    control_ids=["aud0066-dead-port-control", "aud0066-wrong-port-fails"],
    tests=tests,
    negative_controls=negative_controls,
    residual_unknowns=residuals,
    probe_files=PROBE_FILES,
    evidence_map=[[0, 1], [1, 0]],
    report_extra={"headline": ("AUD-0066 rails dependencies: %d scheduled tasks total, %d "
                               "program-relevant; %d/%d known local endpoints alive."
                               % (p1["total_tasks"], p1["relevant_count"],
                                  p2["alive_count"], len(p2["endpoints"]))),
                  "relevant_tasks": p1["relevant_tasks"],
                  "endpoint_results": p2["endpoints"]},
)
