#!/usr/bin/env python3
"""Replay two real task shapes through A7 gates. Write JSON + event TSV.

Task T-ADD-SKILL: actually write a skill, grant, signature, and workflow in
scratch, then count declarations / signing steps / approval gates.

Task T-EXEC-DELETE: estate-local reads plus a Delete of a unit-owned scratch
file (the irreversible class). Replay records the owner prompt then performs
the delete only on that scratch file.

Two signals (must agree or the unit is BLOCKED, not a picked winner):
  1. Python field prompt_count_after on replay.json tasks
  2. Bash field event_kind in replay-events.tsv (OWNER_TASK|OWNER_PROMPT)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import a7_model as M  # noqa: E402

REPLAY_JSON = HERE / "replay.json"
EVENTS_TSV = HERE / "replay-events.tsv"
LAST_ADD = HERE / "fixtures" / "last-add"


def _event(task: str, seq: int, kind: str, tool: str, control: str) -> dict:
    return {
        "task_id": task,
        "seq": seq,
        "event_kind": kind,
        "tool": tool,
        "control": control,
    }


def replay_add(scratch: Path) -> dict:
    task = "T-ADD-SKILL"
    events: list[dict] = []
    seq = 0
    events.append(_event(task, seq, "OWNER_TASK", "-", "baseline"))
    seq += 1
    added = M.write_capability(scratch / "add")
    session_grants = {"Read", "Grep", "Glob", "Write"}
    extra_prompts = 0
    for tool in ("Read", "Write", "Write", "Write"):
        decision = M.choke_point(tool, session_grants, apply_theater=False)
        for kind in decision["event_kinds"]:
            events.append(
                _event(task, seq, kind, tool, ",".join(decision["controls"]))
            )
            seq += 1
            extra_prompts += 1
        events.append(
            _event(
                task,
                seq,
                "GATE_" + decision["decision"],
                tool,
                ",".join(decision["controls"]),
            )
        )
        seq += 1
    events.append(_event(task, seq, "SIGN_STEP", "sign.artifact_provenance", "sign.artifact_provenance"))
    seq += 1
    events.append(_event(task, seq, "SCAN_STEP", "scan.secret_free_bundle", "scan.secret_free_bundle"))
    seq += 1
    events.append(_event(task, seq, "BOUND_STEP", "bound.injection_wf_council", "bound.injection_wf_council"))
    owner_after = 1 + extra_prompts
    return {
        "id": task,
        "title": "Add one estate-local discovery skill with least-privilege grant",
        "prompt_count_before": 1,
        "prompt_count_after": owner_after,
        "owner_turns": owner_after,
        "permission_declarations": added["permission_declarations"],
        "signing_steps": added["signing_steps"],
        "approval_gates": added["approval_gates"],
        "added": {
            k: added[k]
            for k in (
                "capability_id",
                "tools",
                "signature_hex",
                "secret_scan",
                "injection_keys_good",
                "injection_keys_planted",
                "planted_injection_caught",
                "latency_ms",
            )
        },
        "events": events,
        "scratch_grant": added["paths"]["grant"],
    }


def replay_exec(scratch: Path) -> dict:
    task = "T-EXEC-DELETE"
    events: list[dict] = []
    seq = 0
    events.append(_event(task, seq, "OWNER_TASK", "-", "baseline"))
    seq += 1
    target = scratch / "exec" / "unit-owned-scratch.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("arc-0046 scratch; safe to delete\n", encoding="utf-8")
    session_grants = {"Read", "Grep", "Glob", "Bash", "Write", "Delete"}
    extra_prompts = 0
    for tool in ("Read", "Grep", "Bash", "Delete"):
        decision = M.choke_point(tool, session_grants, apply_theater=False)
        for kind in decision["event_kinds"]:
            events.append(
                _event(task, seq, kind, tool, ",".join(decision["controls"]))
            )
            seq += 1
            extra_prompts += 1
        events.append(
            _event(
                task,
                seq,
                "GATE_" + decision["decision"],
                tool,
                ",".join(decision["controls"]),
            )
        )
        seq += 1
    if target.is_file():
        target.unlink()
    owner_after = 1 + extra_prompts
    return {
        "id": task,
        "title": "Estate-local scan then delete a unit-owned scratch file",
        "prompt_count_before": 1,
        "prompt_count_after": owner_after,
        "owner_turns": owner_after,
        "permission_declarations": 0,
        "signing_steps": 0,
        "approval_gates": extra_prompts,
        "deleted_scratch": True,
        "events": events,
    }


def persist_last_add(add_scratch: Path) -> None:
    if LAST_ADD.exists():
        shutil.rmtree(LAST_ADD)
    LAST_ADD.mkdir(parents=True, exist_ok=True)
    src = add_scratch / "add"
    if not src.is_dir():
        return
    for rel in (
        Path("grants") / "skill.local-scan.json",
        Path("skills") / "skill.local-scan" / "SKILL.md",
        Path("workflows") / "wf.local-scan.discovery-only.json",
        Path("signatures") / "skill.local-scan.hmac-sha256",
    ):
        s = src / rel
        d = LAST_ADD / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)


def write_events_tsv(tasks: list[dict]) -> None:
    lines = ["task_id\tseq\tevent_kind\ttool\tcontrol"]
    for task in tasks:
        for ev in task["events"]:
            lines.append(
                f"{ev['task_id']}\t{ev['seq']}\t{ev['event_kind']}\t"
                f"{ev['tool']}\t{ev['control']}"
            )
    EVENTS_TSV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_owner_from_events(events: list[dict]) -> int:
    return sum(
        1
        for ev in events
        if ev["event_kind"] in {"OWNER_TASK", "OWNER_PROMPT"}
    )


def run_replay() -> dict:
    with tempfile.TemporaryDirectory(prefix="arc0046-") as tmp:
        scratch = Path(tmp)
        add = replay_add(scratch)
        exe = replay_exec(scratch)
        persist_last_add(scratch)
        tasks = [add, exe]
        for t in tasks:
            t["owner_turns_from_events"] = count_owner_from_events(t["events"])
        write_events_tsv(tasks)
        slim = []
        for t in tasks:
            row = {k: v for k, v in t.items() if k != "events"}
            row["event_count"] = len(t["events"])
            slim.append(row)
        doc = {
            "unit_id": "ARC-0046",
            "tasks": slim,
            "events_tsv": "command-center/p2-wave/probes/ARC-0046/replay-events.tsv",
            "last_add": "command-center/p2-wave/probes/ARC-0046/fixtures/last-add",
            "signal_python_field": "prompt_count_after",
            "signal_bash_field": "event_kind",
        }
        REPLAY_JSON.write_text(
            json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return {"raw_tasks": tasks, "doc": doc}


def bash_owner_counts() -> dict[str, int]:
    """Second signal: count OWNER_* rows per task from the TSV (event_kind)."""
    import subprocess

    script = r"""
set -euo pipefail
awk -F '\t' 'NR>1 && ($3=="OWNER_TASK" || $3=="OWNER_PROMPT") { c[$1]++ }
END { for (k in c) print k, c[k] }' "$1"
"""
    p = subprocess.run(
        ["bash", "-c", script, "bash", str(EVENTS_TSV)],
        capture_output=True,
        text=True,
        check=True,
    )
    out: dict[str, int] = {}
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[0]] = int(parts[1])
    return out


def main() -> int:
    result = run_replay()
    py = {t["id"]: t["prompt_count_after"] for t in result["doc"]["tasks"]}
    sh = bash_owner_counts()
    disagree = []
    for tid, pv in py.items():
        sv = sh.get(tid)
        if sv != pv:
            disagree.append({"task": tid, "prompt_count_after": pv, "owner_turns_bash": sv})
    print(json.dumps({"python": py, "bash": sh, "disagree": disagree}, sort_keys=True))
    if disagree:
        print("BLOCKED:ARC-0046 two signals disagree")
        return 2
    print("SUCCESS:ARC-0046-replay signals-agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
