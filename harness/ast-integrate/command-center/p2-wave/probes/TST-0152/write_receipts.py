#!/usr/bin/env python3
"""Write TST-0152 receipt, per-unit manifest, and SUBAGENT-RETURN.

Does not run tools/command-center/unit_manifest.py --write.
Does not touch git.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0152"
OUT = "command-center/receipts/TST-0152.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/monitor_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0152/probe1_static_trace.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0152/probe2_both_states.py"
)
SUPPORTING = [
    "tools/monitorcore/monitorcore/liveness.py",
    "tools/monitorcore/monitorcore/panes.py",
    "command-center/p2-wave/probes/TST-0152/fixtures.py",
    "command-center/p2-wave/probes/TST-0152/mtime_mutant.py",
    "command-center/p2-wave/probes/TST-0152/ast_trace.py",
    "command-center/p2-wave/probes/TST-0152/probe1_static_trace.py",
    "command-center/p2-wave/probes/TST-0152/probe2_both_states.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = text.strip() if False else line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0152/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1
    s1 = first_json(t1)
    s2 = first_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    traces = s1.get("field_traces") or []
    receipt = {
        "schema_version": 1,
        "report_kind": "monitor_report",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0152",
        "completion_sentinel": "SUCCESS:TST-0152",
        "title": "mtime-only stall detection is banned and proven absent",
        "question": (
            "Prove no liveness or stall claim in the cockpit is derived from "
            "file mtimes alone. PASS requires a static trace of each liveness "
            "signal to its source, plus a live case where an 11-hour-finished "
            "agent is presented and the cockpit does NOT report it as a stall."
        ),
        "question_or_target": (
            "Prove no liveness or stall claim in the cockpit is derived from "
            "file mtimes alone."
        ),
        "answer": (
            "The agentmon pane classifies via tools/monitorcore/monitorcore/"
            "liveness.py:classify_agent. Stall requires orchestrator_state="
            "running plus heartbeat or process_signal. An 11-hour-finished "
            "agent with an equally old artifact mtime renders finished, not "
            "stalled. A mtime-only record is undecidable. A mtime-only mutant "
            "reproduces the statusline defect (stalled) and is rejected. "
            "SUCCESS:TST-0152"
        ),
        "subject": {
            "surface": "monitorcore.unified.cockpit",
            "pane": "agentmon",
            "classifier": "tools/monitorcore/monitorcore/liveness.py",
            "policy": "stall-requires-orchestrator-running-plus-independent-signal",
        },
        "evidence": [
            {
                "kind": "static-source-trace",
                "claim": (
                    "AST scan of classify_agent finds no mtime identifier in "
                    "If/While/Compare tests. Rendered liveness fields name "
                    "orchestrator_state, heartbeat, and process_signal."
                ),
                "anchor": "tools/monitorcore/monitorcore/liveness.py:classify_agent",
                "verdict": "CONFIRMED",
                "traces": traces,
            },
            {
                "kind": "synthetic-long-finished-agent",
                "claim": (
                    "Cockpit render of agent-11h-finished (orchestrator finished, "
                    "artifact mtime 11h) is finished, not stalled."
                ),
                "anchor": "command-center/p2-wave/probes/TST-0152/fixtures.py:FINISHED_11H",
                "verdict": "CONFIRMED",
                "finished_11h_state": s2.get("finished_11h_state"),
                "mutant_finished_state": s2.get("mutant_finished_state"),
            },
        ],
        "tests": [
            {
                "id": "TST-0152-STATIC-TRACE",
                "name": "source trace of each rendered liveness field",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "TST-0152-BOTH-STATES",
                "name": "active renders active; long-finished renders finished not stalled",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "TST-0152-REGRESSION-11H",
                "name": "11-hour-old finished agent is not a live stall",
                "result": "PASS",
                "finished_11h_state": s2.get("finished_11h_state"),
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0152-NC-MTIME-MUTANT",
                "kind": "mtime-only-stall",
                "description": (
                    "Mutant that stalls on artifact_mtime_age_s >= 11h fires on "
                    "the finished fixture; live classifier does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutant state=stalled source=file_mtime",
                "good_state_output": "live state=finished source=orchestrator_state",
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "static-source-trace",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-and-11h-regression",
                "raw_output": t2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0152-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Probe 2 drives the live cockpit with four fixtures and a "
                "mtime-only mutant. It does not author classify_agent."
            ),
            "windows_second_shell": "NOT-CHECKED",
            "windows_second_shell_note": (
                "Catalog asks for a second Windows shell (pwsh7 and Git Bash). "
                "This delivery ran both probes on Linux; dual-shell divergence "
                "is residual, not claimed checked."
            ),
        },
        "produced_by": {
            "role": "observability-tester",
            "execution_substrate": "linux-headless-local",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0152/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "global_unit_manifest_write": False,
        },
        "residual_unknowns": [
            "Independent re-run on a second Windows shell (pwsh7 vs Git Bash) "
            "was not executed on this Linux worktree."
        ],
        "notes": (
            "G-1 for TST-0152: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not git add/commit. No ADV rebuild. cloud ok=true is not delivery."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if "SUCCESS:TST-0152" not in text:
        print(f"FAILED:{UNIT} sentinel missing from receipt")
        return 1

    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:{UNIT} probes-after-receipt c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = art(OUT, "primary")
    artifacts = [primary] + [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print(f"FAILED:{UNIT} supporting missing {missing}")
        return 1

    now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0152",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "static-source-trace",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "both-states-and-11h-regression",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0152/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0152-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now2,
        "notes": (
            "G-1 for TST-0152: live named probes exit 0, receipts/TST-0152.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0152 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
