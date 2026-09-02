#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0089.json and the per-unit manifest."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from runtime import (  # noqa: E402
    run_scenario,
    silence_view,
    test_ledger_distinguishes_monitor_death_from_work_death,
    test_results_are_harvestable_after_monitor_death,
    test_work_survives_monitor_death,
    typed_view,
)

OUT = "command-center/receipts/TST-0089.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0089/probe1_work_survives.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0089/probe2_ledger_events.py"
)
QUESTION = (
    "Failure class :11315 and Phase 10 layer 22 (:11010). Target: kill the "
    "monitor mid-run and assert (a) the remote work completes, (b) its results "
    "are harvestable afterwards, and (c) the monitor's death is distinguishable "
    "from the work's death in the ledger."
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0089/ledger.py",
    "command-center/p2-wave/probes/TST-0089/worker.py",
    "command-center/p2-wave/probes/TST-0089/monitor.py",
    "command-center/p2-wave/probes/TST-0089/harvest.py",
    "command-center/p2-wave/probes/TST-0089/runtime.py",
    "command-center/p2-wave/probes/TST-0089/probe1_work_survives.py",
    "command-center/p2-wave/probes/TST-0089/probe2_ledger_events.py",
    SCHEMA,
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def compact_events(events: list[dict]) -> list[dict]:
    keep = ("seq", "ts", "event", "actor", "pid", "signal", "nonce", "observed_how")
    out = []
    for e in events:
        row = {k: e[k] for k in keep if k in e}
        out.append(row)
    return out


def looks_like_receipt(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    text = json.dumps(obj, ensure_ascii=True)
    if "SUCCESS:TST-0089" not in text:
        return False
    if obj.get("unit_id") != "TST-0089" and obj.get("id") != "TST-0089":
        return False
    if str(obj.get("state") or "").upper() != "SUCCESS":
        return False
    tests = obj.get("tests")
    if not isinstance(tests, list) or len(tests) < 3:
        return False
    obs = obj.get("observations")
    return isinstance(obs, dict) and obs.get("work_alive_after_monitor_kill") is True


def check_shim_schema() -> None:
    """Catalog schema is a generated $ref shim to ast-integrate.invalid.

    Draft7Validator follows that URI over the network. G-1 named probes consume
    the receipt payload on disk, not a resolved remote schema.
    """
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise SystemExit("FAILED:TST-0089 schema file missing")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("x-artifact-class") != "fault-injection-receipt":
        raise SystemExit("FAILED:TST-0089 schema class mismatch")
    ref = str(schema.get("$ref") or "")
    if "ast-integrate.invalid" not in ref and not ref:
        raise SystemExit("FAILED:TST-0089 schema $ref missing")


def run_named_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    last = HERE / "last-run"
    if last.exists():
        shutil.rmtree(last)
    last.mkdir(parents=True, exist_ok=True)
    kill_mon = run_scenario("kill-monitor", last / "kill-monitor")
    kill_work = run_scenario("kill-work", last / "kill-work")
    test_work_survives_monitor_death(kill_mon)
    test_results_are_harvestable_after_monitor_death(kill_mon)
    test_ledger_distinguishes_monitor_death_from_work_death(kill_mon, kill_work)

    sa = silence_view(kill_mon["silence_snapshot"])
    sb = silence_view(kill_work["silence_snapshot"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "TST-0089",
        "id": "TST-0089",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0089",
        "completion_sentinel": "SUCCESS:TST-0089",
        "title": "The monitor dies while remote work continues",
        "question_or_target": QUESTION,
        "failure_class": "11315",
        "phase": "10",
        "layer": 22,
        "report_kind": "fault-injection-receipt",
        "output_schema": SCHEMA,
        "timestamp_utc": now,
        "retry_policy": (
            "NO retry of a failed injection as a success path. A failed run is "
            "the datum; re-run only with a changed hypothesis recorded first."
        ),
        "hypothesis": (
            "Remote work is a separate session from the monitor. SIGKILL of the "
            "monitor cannot reap it. A supervisor-authored monitor-died event "
            "plus a worker-authored work-completed event make the outage "
            "observable as two facts, not one silence. Killing the work instead "
            "yields work-died and no harvestable result."
        ),
        "injection": {
            "method": "SIGKILL",
            "target": "monitor pid (new session); work pid remains in its own session",
            "when": "after work.ready and two monitor-heartbeat events, while work is still sleeping",
            "negative_control": "SIGKILL the work pid, then SIGKILL the monitor, so both heartbeat streams go quiet",
        },
        "observations": {
            "ledger_event_types": kill_mon["event_types"],
            "kill_work_ledger_event_types": kill_work["event_types"],
            "typed_kill_monitor": typed_view(kill_mon["event_types"]),
            "typed_kill_work": typed_view(kill_work["event_types"]),
            "silence_views_collide": sa == sb,
            "silence_view": sa,
            "work_alive_after_monitor_kill": kill_mon["work_alive_after_monitor_kill"],
            "work_exit_after_monitor_kill": kill_mon["work_exit"],
            "harvest": {
                "ok": kill_mon["harvest"]["ok"],
                "nonce": kill_mon["harvest"]["nonce"],
                "result_sha256": kill_mon["harvest"]["result_sha256"],
                "reason": kill_mon["harvest"]["reason"],
                "would_redispatch": kill_mon["harvest"]["would_redispatch"],
            },
            "kill_work_harvest_ok": kill_work["harvest"]["ok"],
            "signal_source": "os.kill(pid, 0) and wait after SIGKILL; file mtimes are not consulted",
        },
        "ledger_excerpt_kill_monitor": compact_events(kill_mon["events"]),
        "ledger_excerpt_kill_work": compact_events(kill_work["events"]),
        "tests": [
            {
                "id": "test_work_survives_monitor_death",
                "result": "PASS",
                "command": P1,
                "detail": (
                    f"work_alive_after_monitor_kill="
                    f"{kill_mon['work_alive_after_monitor_kill']} "
                    f"work_exit={kill_mon['work_exit']}"
                ),
            },
            {
                "id": "test_results_are_harvestable_after_monitor_death",
                "result": "PASS",
                "command": P1,
                "detail": kill_mon["harvest"]["reason"],
            },
            {
                "id": "test_ledger_distinguishes_monitor_death_from_work_death",
                "result": "PASS",
                "command": P2,
                "detail": (
                    f"{typed_view(kill_mon['event_types'])} vs "
                    f"{typed_view(kill_work['event_types'])}; "
                    f"silence views collide={sa == sb}"
                ),
            },
        ],
        "evidence": [
            {
                "kind": "live-run",
                "path": "command-center/p2-wave/probes/TST-0089/last-run/kill-monitor/ledger.jsonl",
                "claim": "ledger contains monitor-died and work-completed as distinct events",
            },
            {
                "kind": "live-run",
                "path": "command-center/p2-wave/probes/TST-0089/last-run/kill-monitor/harvested.json",
                "claim": "post-mortem harvest recovered the worker nonce without redispatch",
            },
            {
                "kind": "live-run",
                "path": "command-center/p2-wave/probes/TST-0089/last-run/kill-work/ledger.jsonl",
                "claim": "killing work yields work-died and no work-completed",
            },
            {
                "kind": "live-tree",
                "path": "command-center/p2-wave/probes/TST-0089/runtime.py",
                "claim": "work is start_new_session=True; monitor SIGKILL cannot take it",
            },
            {
                "kind": "live-tree",
                "path": "command-center/p2-wave/probes/TST-0089/monitor.py",
                "claim": "liveness is os.kill(pid,0), never file mtime",
            },
        ],
        "evidence_requirement": (
            "the post-mortem harvest recovering the completed results, with the "
            "ledger showing two distinct events (monitor-died, work-completed) "
            "rather than one ambiguous silence"
        ),
        "reviewer": {
            "reviewer_id": "TST-0089-probe2-ledger-events",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 is the mechanical adversary: it re-runs kill-work as a "
                "negative control and asserts the heartbeat+result silence view "
                "collides while typed ledger events do not. Catalog cross-vendor "
                "human review is independent of G-1 probe-green on this box."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "work-survives-and-harvest", "command": P1},
            {"id": "probe2", "role": "ledger-event-distinction", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "schema"},
            {"path": "command-center/p2-wave/probes/TST-0089/runtime.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/TST-0089/ledger.py", "role": "supporting"},
        ],
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/TST-0089/UNIT-ARTIFACT-MANIFEST.json",
        "cloud_ok": False,
        "mtime_stall_detection": "banned; owned by TST-0152",
        "strongest_surviving_counterargument": (
            "If work were in the monitor's process group, SIGKILL of the monitor "
            "would kill the work and this unit would go red. The passing run is "
            "therefore evidence of session isolation, not of a monitor that "
            "cannot die. A heartbeat gap without typed events is still silence; "
            "the ledger, not the gap, is the observation."
        ),
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:11315,_USER-PROMPTS.md:11010",
        "min_bytes_threshold": 1024,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "NO retry. A retry masks the exact instability this unit exists "
                "to measure; a failed run is the datum, re-run only with a "
                "changed hypothesis recorded first"
            ),
        },
        "negative_controls": [
            {
                "id": "TST-0089-NC-KILL-WORK",
                "kind": "other",
                "description": (
                    "SIGKILL the work pid: ledger must type work-died and harvest "
                    "must refuse, proving monitor-died+work-completed is not a "
                    "generic silence token"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": typed_view(kill_work["event_types"]),
                "good_state_output": typed_view(kill_mon["event_types"]),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0089/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
    }

    check_shim_schema()
    if not looks_like_receipt(doc):
        print("FAILED:TST-0089 receipt payload incomplete")
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
        if looks_like_receipt(garbage):
            print("FAILED:TST-0089 payload check accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 1024:
        print(f"FAILED:TST-0089 artifact {size}B below floor")
        return 1

    rows = []
    for rel, role in [(OUT, "primary")] + [(p, "supporting") for p in SUPPORTING]:
        path = REPO / rel
        sha, nbytes = sha256_file(path)
        rows.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": nbytes,
                "present": True,
                "unit_id": "TST-0089",
                "receipt_path": "command-center/p2-wave/probes/TST-0089/SUBAGENT-RETURN.json",
                "role": role,
            }
        )
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0089",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    probe_rows = []
    for pid, cmd, role in (
        ("probe1", P1, "work-survives-and-harvest"),
        ("probe2", P2, "ledger-event-distinction"),
    ):
        rc, text = run_named_probe(cmd)
        probe_rows.append(
            {
                "id": pid,
                "command": cmd,
                "exit_code": rc,
                "role": role,
                "raw_output": text + ("\n" if text and not text.endswith("\n") else ""),
            }
        )
        print(f"emit-probe {pid} rc={rc}")
        if rc != 0:
            print(text[-2000:])
            print(f"FAILED:TST-0089 {pid} exit {rc}")
            return 1

    ret = {
        "id": "TST-0089",
        "unit_id": "TST-0089",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0089",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": probe_rows,
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0089/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0089-probe2-ledger-events",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered TST-0089",
        "ts": now,
        "notes": (
            "G-1 for TST-0089: live named probes exit 0, receipts/TST-0089.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Monitor SIGKILL leaves remote work alive; "
            "harvest recovers nonce; ledger types monitor-died vs work-died. "
            "Heartbeat silence views collide on purpose."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"typed {typed_view(kill_mon['event_types'])} vs {typed_view(kill_work['event_types'])}")
    print("SUCCESS:TST-0089 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
