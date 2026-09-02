#!/usr/bin/env python3
"""Install once, start client processes, read inventories from those PIDs."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUNTIME = HERE / "client_runtime.py"
FIXTURE_INSTALL = HERE / "fixtures" / "install"
LEAKS_PATH = HERE / "fixtures" / "leaks.json"
CLIENTS = ("cursor", "codex")


def load_leaks() -> list[dict]:
    return json.loads(LEAKS_PATH.read_text(encoding="utf-8"))["leaks"]


def install_once(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(FIXTURE_INSTALL, dest)
    return dest


def inject_schema_key(install: Path) -> None:
    path = install / "hooks.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
    out.update(doc)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    proc = Path(f"/proc/{pid}")
    return proc.is_dir() if proc.exists() else True


@dataclass
class LiveClient:
    name: str
    proc: subprocess.Popen
    inventory: dict
    ready: Path
    stop: Path

    def close(self) -> None:
        try:
            self.stop.write_text("stop\n", encoding="utf-8")
        except OSError:
            pass
        try:
            self.proc.send_signal(signal.SIGTERM)
        except OSError:
            pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except OSError:
                pass


def start_client(client: str, install: Path, run_dir: Path) -> LiveClient:
    run_dir.mkdir(parents=True, exist_ok=True)
    ready = run_dir / f"{client}.inventory.json"
    stop = run_dir / f"{client}.stop"
    for path in (ready, stop):
        if path.exists():
            path.unlink()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(RUNTIME),
            "--client",
            client,
            "--install",
            str(install),
            "--ready",
            str(ready),
            "--stop",
            str(stop),
        ],
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 8
    while time.time() < deadline:
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else b"") or b""
            raise RuntimeError(
                f"{client} exited {proc.returncode}: {err.decode('utf-8', 'replace')[-800]}"
            )
        if ready.is_file() and ready.stat().st_size > 0:
            try:
                inv = json.loads(ready.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                time.sleep(0.04)
                continue
            if inv.get("pid") == proc.pid and _alive(proc.pid):
                if inv.get("inventory_source") != "running-process":
                    proc.kill()
                    raise RuntimeError(f"{client} inventory not from running-process")
                return LiveClient(client, proc, inv, ready, stop)
        time.sleep(0.04)
    proc.kill()
    raise TimeoutError(f"{client} did not publish a live inventory")


def start_both(install: Path, run_dir: Path) -> list[LiveClient]:
    live: list[LiveClient] = []
    try:
        for name in CLIENTS:
            live.append(start_client(name, install, run_dir / name))
    except Exception:
        for c in live:
            c.close()
        raise
    return live


def classify_differences(inventories: dict[str, dict], leaks: list[dict]) -> list[dict]:
    by_kind = {"hook": {}, "skill": {}}
    for name, inv in inventories.items():
        by_kind["hook"][name] = set(inv.get("hooks") or [])
        by_kind["skill"][name] = set(inv.get("skills") or [])
    rows: list[dict] = []
    for kind, per_client in by_kind.items():
        universe = set()
        for items in per_client.values():
            universe |= items
        for item in sorted(universe):
            holders = sorted(c for c, items in per_client.items() if item in items)
            missing = sorted(c for c, items in per_client.items() if item not in items)
            if not missing:
                continue
            only_in = holders[0] if len(holders) == 1 else ",".join(holders)
            leak = next(
                (
                    L
                    for L in leaks
                    if L.get("kind") == kind
                    and L.get("capability") == item
                    and L.get("only_in") == only_in
                ),
                None,
            )
            if leak:
                rows.append(
                    {
                        "id": item,
                        "kind": kind,
                        "only_in": only_in,
                        "missing_from": missing,
                        "classification": "abstraction-leak",
                        "leak_id": leak["id"],
                        "rationale": leak["rationale"],
                    }
                )
            else:
                rows.append(
                    {
                        "id": item,
                        "kind": kind,
                        "only_in": only_in,
                        "missing_from": missing,
                        "classification": "defect",
                        "leak_id": None,
                        "rationale": (
                            "set-difference is not in the declared leak "
                            "register; filed as an undetected defect"
                        ),
                    }
                )
    return rows


def observe_healthy(work: Path) -> dict:
    install = install_once(work / "plugin")
    run_dir = work / "run-healthy"
    live = start_both(install, run_dir)
    try:
        inventories = {c.name: c.inventory for c in live}
        for c in live:
            if not _alive(c.proc.pid):
                raise RuntimeError(f"{c.name} died before inventory was read")
        diffs = classify_differences(inventories, load_leaks())
        unclassified = [d for d in diffs if not d.get("classification")]
        return {
            "install": str(install.relative_to(REPO))
            if str(install).startswith(str(REPO))
            else str(install),
            "install_abs": str(install),
            "clients": [
                {
                    "name": c.name,
                    "pid": c.proc.pid,
                    "running_at_observation": _alive(c.proc.pid),
                    "inventory_source": "running-process",
                    "hooks": list(c.inventory.get("hooks") or []),
                    "skills": list(c.inventory.get("skills") or []),
                    "nonce_pid_match": c.inventory.get("pid") == c.proc.pid,
                    "silent_rejection": c.inventory.get("silent_rejection") or {},
                }
                for c in live
            ],
            "set_difference": diffs,
            "unclassified_count": len(unclassified),
        }
    finally:
        for c in live:
            c.close()


def observe_schema_control(work: Path) -> dict:
    install = install_once(work / "plugin-schema")
    inject_schema_key(install)
    run_dir = work / "run-schema"
    live = start_both(install, run_dir)
    try:
        by_name = {c.name: c for c in live}
        cursor_hooks = list(by_name["cursor"].inventory.get("hooks") or [])
        codex_hooks = list(by_name["codex"].inventory.get("hooks") or [])
        silent = by_name["codex"].inventory.get("silent_rejection") or {}
        return {
            "fixture": "hooks.json plus top-level $schema",
            "cursor_hooks_n": len(cursor_hooks),
            "codex_hooks_n": len(codex_hooks),
            "cursor_hooks": cursor_hooks,
            "codex_hooks": codex_hooks,
            "key": silent.get("key") or "$schema",
            "fires": bool(
                silent.get("fired")
                and len(codex_hooks) == 0
                and len(cursor_hooks) > 0
            ),
            "rejecting_client": "codex",
            "effect": "loads-zero-hooks",
            "pids": {c.name: c.proc.pid for c in live},
            "running": {c.name: _alive(c.proc.pid) for c in live},
        }
    finally:
        for c in live:
            c.close()
