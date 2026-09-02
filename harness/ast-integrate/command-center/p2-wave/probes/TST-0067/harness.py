#!/usr/bin/env python3
"""Live consumer-observation harness for TST-0067.

Windows `setx` is not on this Linux worktree. The same class is: a write to a
persistent store that the already-running session does not reload, so a child
spawned from that session still sees the OLD process environment.

Two independent consumer signals for an env var:
  1. the child process JSON (Python os.environ)
  2. /proc/<pid>/environ (kernel), captured while the child is still alive
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONSUMER = HERE / "consumer.py"

ENV_KEY = "TST0067_CONSUMER_VAR"
CONFIG_KEY = "planted.mcp.enabled"
OLD = "session-old-value"
NEW = "session-new-value"
ROOT_WRITE = "root-scope-write-inert"
PROJECT_WRITE = "project-scope-write-live"


def read_proc_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    out: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        k, _, v = item.partition(b"=")
        out[k.decode("utf-8", "replace")] = v.decode("utf-8", "replace")
    return out


def observe_child(
    *,
    env: dict[str, str],
    key: str,
    scope_file: str | Path | None = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    if not CONSUMER.is_file():
        raise FileNotFoundError(CONSUMER)
    handshake = Path(tempfile.mkdtemp(prefix="tst0067-hs-"))
    proc: subprocess.Popen[bytes] | None = None
    try:
        child_env = dict(env)
        child_env["TST0067_KEY"] = key
        child_env["TST0067_HANDSHAKE"] = str(handshake)
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        if scope_file is not None:
            child_env["TST0067_SCOPE_FILE"] = str(scope_file)
        proc = subprocess.Popen(
            [sys.executable, "-B", str(CONSUMER)],
            cwd=str(REPO),
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pid_path = handshake / "pid"
        report_path = handshake / "consumer.json"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if pid_path.is_file() and report_path.is_file():
                break
            if proc.poll() is not None:
                err = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
                raise RuntimeError(
                    f"consumer exited early rc={proc.returncode} stderr={err[-1500:]}"
                )
            time.sleep(0.01)
        else:
            proc.kill()
            raise TimeoutError("consumer handshake")
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        kernel = read_proc_environ(pid)
        userspace = json.loads(report_path.read_text(encoding="utf-8"))
        (handshake / "done").write_text("ok\n", encoding="utf-8")
        stdout_b, stderr_b = proc.communicate(timeout=timeout)
        kernel_val = kernel.get(key)
        user_val = userspace.get("os_environ")
        return {
            "pid": pid,
            "rc": proc.returncode,
            "userspace_os_environ": user_val,
            "kernel_proc_environ": kernel_val,
            "signals_agree": user_val == kernel_val,
            "scope_file": userspace.get("scope_file") or None,
            "scope_file_exists": userspace.get("scope_file_exists"),
            "scope_value": userspace.get("scope_value"),
            "scope_keys": userspace.get("scope_keys") or [],
            "read_persistent_store": userspace.get("read_persistent_store"),
            "stderr_tail": (stderr_b or b"").decode("utf-8", "replace")[-500:],
            "stdout_tail": (stdout_b or b"").decode("utf-8", "replace")[-500:],
        }
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        shutil.rmtree(handshake, ignore_errors=True)


def base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop(ENV_KEY, None)
    env.pop("TST0067_KEY", None)
    env.pop("TST0067_HANDSHAKE", None)
    env.pop("TST0067_SCOPE_FILE", None)
    return env


def write_json(path: Path, doc: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    back = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "written": doc,
        "setter_self_read": back,
    }


def measure_persistent_miss_and_session_hit() -> dict[str, Any]:
    """setx-class miss + session-injected child hit, same run.

    Persistent analog: write NEW into a store file. Do not mutate this process
    environment. A child spawned from the current session still sees unset/OLD.
    Session hit: the same NEW value is placed in the child env at spawn.
    """
    store_dir = Path(tempfile.mkdtemp(prefix="tst0067-store-"))
    try:
        store = store_dir / "persistent.env.json"
        setter = write_json(store, {ENV_KEY: NEW})
        parent_session = os.environ.get(ENV_KEY)
        env = base_env()
        child_from_session = observe_child(env=env, key=ENV_KEY)
        injected = dict(env)
        injected[ENV_KEY] = NEW
        child_injected = observe_child(env=injected, key=ENV_KEY)
        miss = {
            "mechanism": "persistent-store-file analog of setx (no session reload)",
            "variable": ENV_KEY,
            "value_written": NEW,
            "setter_self_read": setter["setter_self_read"].get(ENV_KEY),
            "parent_os_environ": parent_session,
            "consumer_userspace": child_from_session["userspace_os_environ"],
            "consumer_kernel": child_from_session["kernel_proc_environ"],
            "consumer_pid": child_from_session["pid"],
            "signals_agree": child_from_session["signals_agree"],
            "writer_consumer_agree": setter["setter_self_read"].get(ENV_KEY)
            == child_from_session["userspace_os_environ"],
            "setter_only_would_pass": setter["setter_self_read"].get(ENV_KEY) == NEW,
        }
        hit = {
            "mechanism": "child env overlay at spawn (session-visible to THIS child)",
            "variable": ENV_KEY,
            "value_written": NEW,
            "parent_os_environ_unchanged": os.environ.get(ENV_KEY) == parent_session,
            "consumer_userspace": child_injected["userspace_os_environ"],
            "consumer_kernel": child_injected["kernel_proc_environ"],
            "consumer_pid": child_injected["pid"],
            "signals_agree": child_injected["signals_agree"],
            "writer_consumer_agree": NEW == child_injected["userspace_os_environ"],
        }
        ok = (
            child_from_session["rc"] == 0
            and child_injected["rc"] == 0
            and child_from_session["signals_agree"] is True
            and child_injected["signals_agree"] is True
            and miss["setter_self_read"] == NEW
            and miss["consumer_userspace"] is None
            and miss["consumer_kernel"] is None
            and miss["writer_consumer_agree"] is False
            and miss["setter_only_would_pass"] is True
            and hit["consumer_userspace"] == NEW
            and hit["consumer_kernel"] == NEW
            and hit["writer_consumer_agree"] is True
            and hit["parent_os_environ_unchanged"] is True
        )
        return {
            "pass": ok,
            "persistent_miss": miss,
            "session_hit": hit,
            "store_path_basename": store.name,
        }
    finally:
        shutil.rmtree(store_dir, ignore_errors=True)


def measure_wrong_scope_inert() -> dict[str, Any]:
    """Root-scope write is inert for a project-scoped consumer; project write is live."""
    root = Path(tempfile.mkdtemp(prefix="tst0067-scope-"))
    try:
        root_file = root / "root" / "settings.json"
        project_file = root / "project" / "settings.json"
        write_json(root_file, {CONFIG_KEY: ROOT_WRITE, "noise": "root-only"})
        write_json(project_file, {CONFIG_KEY: OLD})
        env = base_env()
        after_root = observe_child(env=env, key=CONFIG_KEY, scope_file=project_file)
        project_setter = write_json(project_file, {CONFIG_KEY: PROJECT_WRITE})
        after_project = observe_child(env=env, key=CONFIG_KEY, scope_file=project_file)
        # Consumer handed the root file by mistake would see ROOT_WRITE; that is
        # a different consumer. The project consumer must not.
        inert = {
            "mechanism": "write at root settings; consumer opens project settings only",
            "key": CONFIG_KEY,
            "value_written_at_root": ROOT_WRITE,
            "setter_self_read_root": json.loads(root_file.read_text(encoding="utf-8")).get(
                CONFIG_KEY
            ),
            "consumer_scope_file": after_root["scope_file"],
            "consumer_scope_value": after_root["scope_value"],
            "consumer_pid": after_root["pid"],
            "signals_agree_env_unset": after_root["signals_agree"]
            and after_root["userspace_os_environ"] is None,
            "writer_consumer_agree": ROOT_WRITE == after_root["scope_value"],
            "detected_inert": after_root["scope_value"] != ROOT_WRITE
            and after_root["scope_value"] == OLD,
            "setter_only_would_pass": json.loads(root_file.read_text(encoding="utf-8")).get(
                CONFIG_KEY
            )
            == ROOT_WRITE,
        }
        live = {
            "mechanism": "write at the scope the consumer actually opens (project)",
            "key": CONFIG_KEY,
            "value_written_at_project": PROJECT_WRITE,
            "setter_self_read_project": project_setter["setter_self_read"].get(CONFIG_KEY),
            "consumer_scope_file": after_project["scope_file"],
            "consumer_scope_value": after_project["scope_value"],
            "consumer_pid": after_project["pid"],
            "writer_consumer_agree": PROJECT_WRITE == after_project["scope_value"],
        }
        ok = (
            after_root["rc"] == 0
            and after_project["rc"] == 0
            and inert["detected_inert"] is True
            and inert["writer_consumer_agree"] is False
            and inert["setter_only_would_pass"] is True
            and live["writer_consumer_agree"] is True
            and Path(str(after_root["scope_file"])).name == "settings.json"
            and "root" not in Path(str(after_root["scope_file"])).parts[-2:]
        )
        # last clause: consumer path ends with project/settings.json not root/settings.json
        ok = bool(
            ok
            and Path(str(after_root["scope_file"])).parent.name == "project"
            and Path(str(after_project["scope_file"])).parent.name == "project"
        )
        return {
            "pass": ok,
            "wrong_scope_inert": inert,
            "correct_scope_live": live,
            "consumers": [
                {
                    "name": "env-child",
                    "reads": "process environment at spawn (os.environ and /proc/pid/environ)",
                    "does_not_read": "persistent store file; root settings.json",
                },
                {
                    "name": "project-settings-child",
                    "reads": "TST0067_SCOPE_FILE (project/settings.json)",
                    "does_not_read": "root/settings.json unless that path is handed over",
                },
                {
                    "name": "setter",
                    "reads": "the file it just wrote",
                    "does_not_read": "the consumer process; agreement with itself is not evidence",
                },
            ],
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def measure_detector_control() -> dict[str, Any]:
    """Setter-self-agreement would green an inert write; consumer observation does not."""
    miss = measure_persistent_miss_and_session_hit()
    scope = measure_wrong_scope_inert()
    persistent = miss["persistent_miss"]
    session = miss["session_hit"]
    inert = scope["wrong_scope_inert"]
    live = scope["correct_scope_live"]

    setter_false_green_persistent = bool(
        persistent["setter_only_would_pass"] and not persistent["writer_consumer_agree"]
    )
    setter_false_green_scope = bool(
        inert["setter_only_would_pass"] and not inert["writer_consumer_agree"]
    )
    consumer_true_green_session = bool(session["writer_consumer_agree"])
    consumer_true_green_project = bool(live["writer_consumer_agree"])
    ok = (
        miss["pass"]
        and scope["pass"]
        and setter_false_green_persistent
        and setter_false_green_scope
        and consumer_true_green_session
        and consumer_true_green_project
    )
    return {
        "pass": ok,
        "control": (
            "A probe that only compares the setter to itself PASSES on the "
            "persistent-store write and the root-scope write. A probe that reads "
            "the consumer process FAILS those claims (inert / session miss) and "
            "PASSES only when the child actually observed the new value."
        ),
        "persistent_setter_false_green": setter_false_green_persistent,
        "scope_setter_false_green": setter_false_green_scope,
        "session_consumer_true_green": consumer_true_green_session,
        "project_consumer_true_green": consumer_true_green_project,
        "persistent_pair": {
            "written": persistent["value_written"],
            "setter_self_read": persistent["setter_self_read"],
            "consumer_userspace": persistent["consumer_userspace"],
            "consumer_kernel": persistent["consumer_kernel"],
        },
        "scope_pair": {
            "written_at_root": inert["value_written_at_root"],
            "setter_self_read_root": inert["setter_self_read_root"],
            "consumer_scope_value": inert["consumer_scope_value"],
        },
        "session_pair": {
            "written": session["value_written"],
            "consumer_userspace": session["consumer_userspace"],
            "consumer_kernel": session["consumer_kernel"],
        },
        "project_pair": {
            "written_at_project": live["value_written_at_project"],
            "consumer_scope_value": live["consumer_scope_value"],
        },
    }
