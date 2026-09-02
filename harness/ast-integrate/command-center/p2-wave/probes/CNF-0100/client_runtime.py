#!/usr/bin/env python3
"""Long-lived client process. Loads hooks/skills from an install tree and
exposes the inventory it actually loaded. Parent enumerates that inventory
from this process, not from the config file.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    meta: dict = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip()] = val.strip()
    return meta


def parse_clients(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    names = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
    return names or None


def load_hooks(client: str, install: Path) -> tuple[list[str], dict]:
    path = install / "hooks.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    silent = {"fired": False, "key": None, "effect": None}
    # Measured precedent: Codex silently rejects the whole hooks file when
    # a `$schema` key is present. Cursor is tolerant and still loads hooks.
    if client == "codex" and isinstance(doc, dict) and "$schema" in doc:
        silent = {
            "fired": True,
            "key": "$schema",
            "effect": "loads-zero-hooks",
        }
        return [], silent
    loaded: list[str] = []
    events = doc.get("hooks") if isinstance(doc, dict) else {}
    if not isinstance(events, dict):
        events = {}
    for event, items in events.items():
        if client == "codex" and event == "SessionStart":
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            hid = str(item.get("id") or item.get("command") or "").strip()
            if hid:
                loaded.append(f"{event}:{hid}")
    return sorted(set(loaded)), silent


def load_skills(client: str, install: Path) -> list[str]:
    skills_root = install / "skills"
    loaded: list[str] = []
    if not skills_root.is_dir():
        return loaded
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        allowed = parse_clients(meta.get("clients"))
        if allowed is not None and client not in allowed:
            continue
        loaded.append(skill_md.parent.name)
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", required=True, choices=("cursor", "codex"))
    parser.add_argument("--install", required=True)
    parser.add_argument("--ready", required=True)
    parser.add_argument("--stop", required=True)
    args = parser.parse_args()

    install = Path(args.install)
    ready = Path(args.ready)
    stop = Path(args.stop)
    ready.parent.mkdir(parents=True, exist_ok=True)

    hooks, silent = load_hooks(args.client, install)
    skills = load_skills(args.client, install)
    inventory = {
        "pid": os.getpid(),
        "client": args.client,
        "inventory_source": "running-process",
        "install": str(install),
        "hooks": hooks,
        "skills": skills,
        "silent_rejection": silent,
        "config_keys_seen": sorted(
            json.loads((install / "hooks.json").read_text(encoding="utf-8")).keys()
        )
        if (install / "hooks.json").is_file()
        else [],
    }
    tmp = ready.with_suffix(ready.suffix + ".tmp")
    tmp.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    tmp.replace(ready)

    def _halt(*_args) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _halt)
    signal.signal(signal.SIGINT, _halt)
    while not stop.exists():
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
