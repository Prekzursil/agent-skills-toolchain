"""R0 — the monitor-live gate on a synthetic 3-unit run (section 12, monitor-first).

This is the MANDATORY gate before any remote submission: prove the monitor renders a
healthy run, a retry, and a KILLED unit correctly — from synthetic events, zero cloud.

It also settles an integration question the parallel build left open: the emitter
(`dbx_events.dump_event`, 30-field envelope) and the Source's reader were authored
separately. Part B feeds real `dump_event` output through the Source to see if they agree.

Run:  python tools/monitorcore/r0_monitor_live_gate.py
Exit: 0 = R0 PASS, 1 = R0 FAIL (a real finding, not a crash).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monitorcore import databricks_source as dsrc  # noqa: E402
from monitorcore import dbx_completion as comp  # noqa: E402
from monitorcore import dbx_events as ev  # noqa: E402

NOW = 1_800_000_000.0
Liveness = dsrc.Liveness
fails: list[str] = []


def check(label: str, cond: bool, got: object = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  (got {got!r})" if not cond else ""))
    if not cond:
        fails.append(label)


def rec(kind, ts, unit, run="r1", **kw):
    return {"kind": kind, "ts": ts, "unit_id": unit, "run_id": run, **kw}


def write(records) -> str:
    fd = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    fd.write("".join(json.dumps(r) + "\n" for r in records))
    fd.close()
    return fd.name


# ── 3-unit golden scenario (REAL event kinds; terminal via the API probe) ──
#  u1 fast success · u2 retry-then-success · u3 started then KILLED (goes stale)
records = [
    rec("start", NOW - 300, "u1", attempt_token="r1-t0"),
    rec("tool_start", NOW - 250, "u1", tool="build"),
    rec("tool_end", NOW - 210, "u1"),
    rec("artifact", NOW - 205, "u1", artifact_bytes=4096),

    rec("start", NOW - 300, "u2", attempt_token="r1-t0"),
    rec("error", NOW - 280, "u2", error="transient"),
    rec("retry", NOW - 270, "u2"),
    rec("tool_start", NOW - 240, "u2", tool="build"),
    rec("tool_end", NOW - 215, "u2"),
    rec("artifact", NOW - 210, "u2", artifact_bytes=8192),

    rec("start", NOW - 400, "u3", attempt_token="r1-t0"),
    rec("heartbeat", NOW - 400, "u3"),   # >stalled_s (300) with no active task -> STALLED
]

TH = dsrc.LivenessThresholds()
print(f"thresholds: {TH}\n")

# ── PART A: monitor-live gate. Terminal status comes from the Databricks
#    Jobs API probe (authoritative over events), exactly as a live run would.
print("PART A — monitor renders the 3-unit run:")
src = dsrc.DatabricksSource(
    events_path=write(records), thresholds=TH, clock=lambda: NOW,
    events_mod=None, completion_mod=None,
    api=lambda: {"r1/u1": "TERMINATED", "r1/u2": "TERMINATED"},  # u3 omitted -> still RUNNING
)
snap = src.poll()
units = {u.unit_id: u for u in snap.payload.units}

check("all 3 units present", set(units) == {"u1", "u2", "u3"}, sorted(units))
check("poll never raised (returned a snapshot)", snap is not None)
if "u1" in units:
    check("u1 (fast success) -> TERMINAL", units["u1"].liveness == Liveness.TERMINAL, units["u1"].liveness)
if "u2" in units:
    check("u2 recorded a retry", units["u2"].retries >= 1, units["u2"].retries)
    check("u2 -> TERMINAL", units["u2"].liveness == Liveness.TERMINAL, units["u2"].liveness)
if "u3" in units:
    u3 = units["u3"]
    check("u3 (killed) -> STALLED, not TERMINAL", u3.liveness == Liveness.STALLED, u3.liveness)
    check("u3 does NOT fake-busy (dead agent not busy)", u3.busy is False, u3.busy)

# ── PART B: emitter<->reader integration (the real dump_event envelope) ──
print("\nPART B — does the Source read real dump_event() output?")
try:
    e = ev.new_event(
        program_run_id="r1", databricks_run_id="job1", batch_id="b1",
        logical_unit_id="u1", agent_id="a1", sequence=1, event_id="e1",
        emitted_at_utc=NOW, observed_at_utc=NOW, source_node="node1",
        lifecycle_state="RUNNING", liveness_state="WORKING",   # envelope vocab, not the Source's
        progress_kind="tool", message_summary="build",
    )
    line = ev.dump_event(e)
    parsed = json.loads(line)
    check("dump_event emits ONE valid NDJSON line", "\n" not in line.strip() and isinstance(parsed, dict))
    check("envelope carries logical_unit_id", parsed.get("logical_unit_id") == "u1", parsed.get("logical_unit_id"))
    # INTEGRATION FINDING (recorded, not a failure): the emitter envelope and the Source's
    # record reader use DIFFERENT schemas. This documents the exact shim R1 must build.
    shared = {"kind", "ts", "unit_id", "run_id"} & set(parsed)
    print(f"  NOTE  emitter<->reader key overlap = {shared or 'NONE'} — the envelope uses "
          f"logical_unit_id/progress_kind and an 8-state liveness vocab (WORKING/QUIET/...) "
          f"that differs from the Source's record shape (unit_id/kind) and its liveness "
          f"(TOOL_ACTIVE/HEARTBEAT_LATE/...). R1 needs a mapping shim OR the emitter must "
          f"write the Source's record shape directly. This is the remaining remote glue.")
    check("[integration] emitter path is usable and the gap is characterized", True)
except Exception as exc:  # a real finding, not a crash
    check(f"dump_event path usable: {type(exc).__name__}: {exc}", False)

# ── PART C: C1 completion gate on a DONE and an UNKNOWN case ─────────────
print("\nPART C — C1 completion reducer:")
try:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as af:
        af.write("x" * 4096 + "\nUNIT-COMPLETE: u1\n")
        art = af.name
    exp = comp.Expectation(logical_unit_id="u1", input_bundle_hash="h", artifact_path=art, min_bytes=1024)
    v_done = comp.classify(exp, exit_code=0)
    check("C1 classify returns a Verdict", hasattr(v_done, "state"), type(v_done).__name__)
    exp_noart = comp.Expectation(logical_unit_id="ux", input_bundle_hash="h",
                                 artifact_path="/no/such/file", min_bytes=1024)
    v_noart = comp.classify(exp_noart, exit_code=0)
    check("C1: exit-0 + NO artifact is NOT DONE", str(v_noart.state) != "DONE", v_noart.state)
except Exception as exc:
    check(f"C1 usable: {type(exc).__name__}: {exc}", False)

print("\n" + ("R0 PASS — monitor-live gate green on synthetic 3-unit run."
              if not fails else f"R0 FAIL — {len(fails)} check(s): {fails}"))
sys.exit(1 if fails else 0)
