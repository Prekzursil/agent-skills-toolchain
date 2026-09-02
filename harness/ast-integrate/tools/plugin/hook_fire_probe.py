"""Live hook-fire probe: execute hooks.json commands and observe a sentinel."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Report:
    verdict: str
    sentinel_observed: bool
    hook_id: str
    inventory_loaded: list
    trigger_count: int
    extra_keys: list
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def as_dict(self) -> dict[str, Any]:
        return self.to_dict()


def filesystem_only_verdict(config_dir: Path) -> str:
    root = Path(config_dir)
    if (root / "hooks.json").is_file() and (root / "scripts" / "emit_sentinel.py").is_file():
        return "FIRED"
    return "NOT-FIRED"


def run_probe(config_dir: Path, work_dir: Path | None = None) -> Report:
    root = Path(config_dir)
    work = Path(work_dir) if work_dir is not None else root / ".work"
    work.mkdir(parents=True, exist_ok=True)
    hooks_path = root / "hooks.json"
    doc = json.loads(hooks_path.read_text(encoding="utf-8"))
    extra = [k for k in doc.keys() if k not in {"hooks"}]
    if extra:
        return Report(
            verdict="NOT-FIRED",
            sentinel_observed=False,
            hook_id="",
            inventory_loaded=[],
            trigger_count=0,
            extra_keys=extra,
        )
    events = doc.get("hooks") or {}
    inventory: list[str] = []
    commands: list[tuple[str, str]] = []
    for _event, entries in events.items():
        for entry in entries or []:
            hid = str(entry.get("id") or "hook.pre-tool")
            inventory.append(hid)
            for hook in entry.get("hooks") or []:
                cmd = str(hook.get("command") or "")
                if cmd:
                    commands.append((hid, cmd))
    nonce = secrets.token_hex(8)
    sentinel = work / "sentinel.txt"
    if sentinel.exists():
        sentinel.unlink()
    trigger_count = 0
    last_id = inventory[0] if inventory else "hook.pre-tool"
    for hid, cmd in commands:
        last_id = hid
        script = (root / cmd).resolve()
        env = os.environ.copy()
        env["HOOK_FIRE_NONCE"] = nonce
        env["HOOK_FIRE_SENTINEL_PATH"] = str(sentinel)
        env["HOOK_FIRE_ID"] = hid
        proc = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        if proc.returncode == 0:
            trigger_count += 1
    observed = False
    if sentinel.is_file():
        text = sentinel.read_text(encoding="utf-8", errors="replace")
        observed = nonce in text and "HOOK_FIRED" in text
    fired = observed and trigger_count >= 1 and last_id in inventory
    return Report(
        verdict="FIRED" if fired else "NOT-FIRED",
        sentinel_observed=observed,
        hook_id=last_id,
        inventory_loaded=inventory,
        trigger_count=trigger_count,
        extra_keys=extra,
    )
