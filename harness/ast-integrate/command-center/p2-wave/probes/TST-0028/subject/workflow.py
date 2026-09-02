#!/usr/bin/env python3
"""Isolated-build subject for TST-0028 record/replay.

Stdlib only. The harness copies this directory into two materialised builds
and runs this file as a script so a planted edit in one build cannot leak
into the other via shared imports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

PLAN_MARKER = "accept-v1"

HERE = Path(__file__).resolve().parent
TASK_PATH = HERE / "fixtures" / "task.json"
NET_HOST = "192.0.2.1"
NET_PORT = 1
NET_TIMEOUT_S = 0.25
CRED_NAME = "TST0028_LIVE_TOKEN"


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_obj(obj: Any) -> str:
    return digest_text(canon(obj))


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_task() -> dict[str, Any]:
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def plan_decision(task: dict[str, Any]) -> dict[str, Any]:
    items = list(task.get("items") or [])
    action = "expand" if len(items) > 2 else "passthrough"
    return {
        "action": action,
        "item_count": len(items),
        "marker": PLAN_MARKER,
        "task_id": task.get("id"),
    }


def local_digest(task: dict[str, Any], plan: dict[str, Any]) -> str:
    return digest_obj({"plan": plan, "task": task})


def fetch_external() -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        with socket.create_connection((NET_HOST, NET_PORT), timeout=NET_TIMEOUT_S):
            elapsed = time.monotonic() - t0
            return {
                "status": "unexpected-success",
                "reason": "network",
                "host": NET_HOST,
                "port": NET_PORT,
                "elapsed_ms": round(elapsed * 1000, 1),
            }
    except OSError as exc:
        elapsed = time.monotonic() - t0
        return {
            "status": "blocked",
            "reason": "network",
            "host": NET_HOST,
            "port": NET_PORT,
            "error_type": type(exc).__name__,
            "elapsed_ms": round(elapsed * 1000, 1),
        }


def credential_gate() -> dict[str, Any]:
    present = CRED_NAME in os.environ and bool(os.environ.get(CRED_NAME))
    return {
        "status": "ok" if present else "blocked",
        "reason": "credential",
        "credential_present": present,
        "credential_name": CRED_NAME,
    }


def stamp_clock(frozen_unix_ns: int | None) -> dict[str, Any]:
    unix_ns = int(frozen_unix_ns) if frozen_unix_ns is not None else time.time_ns()
    return {
        "status": "ok",
        "reason": "clock",
        "unix_ns": unix_ns,
        "frozen": frozen_unix_ns is not None,
    }


def gui_capture() -> dict[str, Any]:
    display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    return {
        "status": "blocked",
        "reason": "GUI",
        "display_present": bool(display),
        "detail": (
            "UI capture is not replayable without a live GUI session. "
            "This step records the block; it does not screenshot."
        ),
    }


def compose_report(task: dict[str, Any], plan: dict[str, Any], digest: str) -> dict[str, Any]:
    return {
        "task_id": task.get("id"),
        "plan": plan,
        "digest_sha256": digest,
        "item_ids": [str(item.get("id")) for item in (task.get("items") or [])],
    }


def write_artifact(art_dir: Path, rel: str, raw: bytes) -> dict[str, Any]:
    path = art_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": rel, "sha256": digest_bytes(raw), "bytes": len(raw.replace(b"\r\n", b"\n"))}


def semantic_artifacts(art_index: dict[str, dict[str, Any]]) -> dict[str, str]:
    keep = ("digest.txt", "report.json")
    return {k: art_index[k]["sha256"] for k in keep if k in art_index}


def semantic_trace(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in steps:
        if step.get("semantic"):
            out.append(
                {
                    "id": step["id"],
                    "decision_sha256": digest_obj(step.get("decision")),
                    "decision": step.get("decision"),
                }
            )
    return out


def run_record(art_dir: Path) -> dict[str, Any]:
    task = load_task()
    steps: list[dict[str, Any]] = []
    art_index: dict[str, dict[str, Any]] = {}
    tool_calls: list[dict[str, Any]] = []

    load_decision = {
        "task_id": task.get("id"),
        "item_count": len(list(task.get("items") or [])),
    }
    steps.append(
        {
            "id": "load_inputs",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": load_decision,
            "tool_calls": [
                {"tool": "read_file", "path": "fixtures/task.json", "class": "local"}
            ],
        }
    )
    tool_calls.append({"step": "load_inputs", "tool": "read_file", "class": "local"})

    plan = plan_decision(task)
    steps.append(
        {
            "id": "plan",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": plan,
            "tool_calls": [{"tool": "plan", "class": "local", "marker": PLAN_MARKER}],
        }
    )
    tool_calls.append({"step": "plan", "tool": "plan", "class": "local"})

    digest = local_digest(task, plan)
    art_index["digest.txt"] = write_artifact(
        art_dir, "digest.txt", (digest + "\n").encode("utf-8")
    )
    steps.append(
        {
            "id": "digest_tool",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": {"digest_sha256": digest},
            "tool_calls": [{"tool": "sha256", "class": "local"}],
            "artifacts": [art_index["digest.txt"]],
        }
    )
    tool_calls.append({"step": "digest_tool", "tool": "sha256", "class": "local"})

    net = fetch_external()
    steps.append(
        {
            "id": "fetch_external",
            "reason": "network",
            "reason_class": "network",
            "semantic": False,
            "outcome": net.get("status"),
            "decision": net,
            "tool_calls": [
                {
                    "tool": "socket.create_connection",
                    "class": "network",
                    "host": NET_HOST,
                    "port": NET_PORT,
                }
            ],
        }
    )
    tool_calls.append(
        {"step": "fetch_external", "tool": "socket.create_connection", "class": "network"}
    )

    cred = credential_gate()
    steps.append(
        {
            "id": "credential_gate",
            "reason": "credential",
            "reason_class": "credential",
            "semantic": False,
            "outcome": cred.get("status"),
            "decision": cred,
            "tool_calls": [
                {"tool": "env_probe", "class": "credential", "name": CRED_NAME}
            ],
        }
    )
    tool_calls.append({"step": "credential_gate", "tool": "env_probe", "class": "credential"})

    clock = stamp_clock(None)
    steps.append(
        {
            "id": "stamp_clock",
            "reason": "clock",
            "reason_class": "clock",
            "semantic": True,
            "outcome": "ok",
            "decision": {"unix_ns": clock["unix_ns"], "frozen_on_replay": True},
            "tool_calls": [{"tool": "time.time_ns", "class": "clock"}],
        }
    )
    tool_calls.append({"step": "stamp_clock", "tool": "time.time_ns", "class": "clock"})

    gui = gui_capture()
    steps.append(
        {
            "id": "gui_capture",
            "reason": "GUI",
            "reason_class": "gui",
            "semantic": False,
            "outcome": gui.get("status"),
            "decision": gui,
            "tool_calls": [{"tool": "display_probe", "class": "gui"}],
        }
    )
    tool_calls.append({"step": "gui_capture", "tool": "display_probe", "class": "gui"})

    report = compose_report(task, plan, digest)
    raw_report = (canon(report) + "\n").encode("utf-8")
    art_index["report.json"] = write_artifact(art_dir, "report.json", raw_report)
    steps.append(
        {
            "id": "compose_report",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": {"report_sha256": art_index["report.json"]["sha256"]},
            "tool_calls": [{"tool": "write_file", "class": "local", "path": "report.json"}],
            "artifacts": [art_index["report.json"]],
        }
    )
    tool_calls.append({"step": "compose_report", "tool": "write_file", "class": "local"})

    return {
        "schema": "tst0028-recording-v1",
        "unit_id": "TST-0028",
        "mode": "record",
        "inputs": {"task": task},
        "frozen_clock_unix_ns": clock["unix_ns"],
        "plan_marker": PLAN_MARKER,
        "steps": steps,
        "tool_calls": tool_calls,
        "artifact_set": semantic_artifacts(art_index),
        "artifact_index": art_index,
        "decision_trace": semantic_trace(steps),
    }


def run_replay(art_dir: Path, recording: dict[str, Any], *, offline: bool) -> dict[str, Any]:
    task = (recording.get("inputs") or {}).get("task") or load_task()
    frozen = recording.get("frozen_clock_unix_ns")
    steps: list[dict[str, Any]] = []
    art_index: dict[str, dict[str, Any]] = {}
    tool_calls: list[dict[str, Any]] = []

    load_decision = {
        "task_id": task.get("id"),
        "item_count": len(list(task.get("items") or [])),
    }
    steps.append(
        {
            "id": "load_inputs",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": load_decision,
            "tool_calls": [{"tool": "read_recording", "class": "local"}],
        }
    )
    tool_calls.append({"step": "load_inputs", "tool": "read_recording", "class": "local"})

    plan = plan_decision(task)
    steps.append(
        {
            "id": "plan",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": plan,
            "tool_calls": [{"tool": "plan", "class": "local", "marker": PLAN_MARKER}],
        }
    )
    tool_calls.append({"step": "plan", "tool": "plan", "class": "local"})

    digest = local_digest(task, plan)
    art_index["digest.txt"] = write_artifact(
        art_dir, "digest.txt", (digest + "\n").encode("utf-8")
    )
    steps.append(
        {
            "id": "digest_tool",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": {"digest_sha256": digest},
            "tool_calls": [{"tool": "sha256", "class": "local"}],
            "artifacts": [art_index["digest.txt"]],
        }
    )
    tool_calls.append({"step": "digest_tool", "tool": "sha256", "class": "local"})

    steps.append(
        {
            "id": "fetch_external",
            "reason": "network",
            "reason_class": "network",
            "semantic": False,
            "outcome": "not_replayed",
            "decision": {
                "skipped": True,
                "reason": "network",
                "detail": "offline replay does not open sockets",
            },
            "tool_calls": [],
        }
    )

    steps.append(
        {
            "id": "credential_gate",
            "reason": "credential",
            "reason_class": "credential",
            "semantic": False,
            "outcome": "not_replayed",
            "decision": {
                "skipped": True,
                "reason": "credential",
                "detail": "offline replay does not read live credentials",
            },
            "tool_calls": [],
        }
    )

    clock = stamp_clock(int(frozen) if frozen is not None else None)
    steps.append(
        {
            "id": "stamp_clock",
            "reason": "clock",
            "reason_class": "clock",
            "semantic": True,
            "outcome": "ok",
            "decision": {"unix_ns": clock["unix_ns"], "frozen_on_replay": True},
            "tool_calls": [{"tool": "frozen_clock", "class": "clock"}],
        }
    )
    tool_calls.append({"step": "stamp_clock", "tool": "frozen_clock", "class": "clock"})

    steps.append(
        {
            "id": "gui_capture",
            "reason": "GUI",
            "reason_class": "gui",
            "semantic": False,
            "outcome": "not_replayed",
            "decision": {
                "skipped": True,
                "reason": "GUI",
                "detail": "offline replay does not capture a UI surface",
            },
            "tool_calls": [],
        }
    )

    report = compose_report(task, plan, digest)
    raw_report = (canon(report) + "\n").encode("utf-8")
    art_index["report.json"] = write_artifact(art_dir, "report.json", raw_report)
    steps.append(
        {
            "id": "compose_report",
            "reason": None,
            "reason_class": "local",
            "semantic": True,
            "outcome": "ok",
            "decision": {"report_sha256": art_index["report.json"]["sha256"]},
            "tool_calls": [{"tool": "write_file", "class": "local", "path": "report.json"}],
            "artifacts": [art_index["report.json"]],
        }
    )
    tool_calls.append({"step": "compose_report", "tool": "write_file", "class": "local"})

    return {
        "schema": "tst0028-recording-v1",
        "unit_id": "TST-0028",
        "mode": "replay",
        "offline": offline,
        "inputs": {"task": task},
        "frozen_clock_unix_ns": clock["unix_ns"],
        "plan_marker": PLAN_MARKER,
        "steps": steps,
        "tool_calls": tool_calls,
        "artifact_set": semantic_artifacts(art_index),
        "artifact_index": art_index,
        "decision_trace": semantic_trace(steps),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record", "replay"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--recording", default="")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    art_dir = Path(args.artifacts_dir)
    art_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "record":
        doc = run_record(art_dir)
    else:
        rec_path = Path(args.recording)
        recording = json.loads(rec_path.read_text(encoding="utf-8"))
        doc = run_replay(art_dir, recording, offline=bool(args.offline))
    write_json(Path(args.out), doc)
    print(canon({"mode": doc["mode"], "plan_marker": doc["plan_marker"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
