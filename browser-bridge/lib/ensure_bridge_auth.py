#!/usr/bin/env python3
"""Ensure chromeBridge tokens exist in ~/.agents/local.json. Never prints secrets."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

AGENT_EXTENSION_ID = "bdccimcedobipcmhcikcnakjdemiechj"
LOCAL_JSON = Path.home() / ".agents" / "local.json"
LIVE_ID_FILE = (
    Path.home() / ".agents" / "browser-bridge" / "extension-live" / "EXTENSION_ID"
)


def _atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        raise SystemExit("FAILED:ensure-bridge-auth local.json is not an object")
    return data


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and len(value.strip()) >= 16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("agent", "live"), default="agent")
    args = parser.parse_args()

    data = _read_json(LOCAL_JSON)
    bridge = data.get("chromeBridge")
    if not isinstance(bridge, dict):
        bridge = {}

    created = []
    if not _nonempty_str(bridge.get("agentToken")):
        bridge["agentToken"] = secrets.token_urlsafe(32)
        created.append("agentToken")
    if not _nonempty_str(bridge.get("liveToken")):
        bridge["liveToken"] = secrets.token_urlsafe(32)
        created.append("liveToken")

    bridge["agentExtensionId"] = AGENT_EXTENSION_ID
    live_id = ""
    if LIVE_ID_FILE.is_file():
        live_id = LIVE_ID_FILE.read_text(encoding="utf-8").strip()
    if live_id:
        bridge["liveExtensionId"] = live_id
    elif not isinstance(bridge.get("liveExtensionId"), str) or not bridge.get(
        "liveExtensionId"
    ):
        bridge["liveExtensionId"] = ""

    data["chromeBridge"] = bridge
    if created or True:
        # Always rewrite so agentExtensionId stays pinned even if an older file lacked it.
        LOCAL_JSON.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(LOCAL_JSON, data)

    extension_id = (
        bridge["agentExtensionId"]
        if args.mode == "agent"
        else bridge.get("liveExtensionId", "")
    )
    port = 8770 if args.mode == "agent" else 8790
    meta = {
        "ok": True,
        "mode": args.mode,
        "port": port,
        "extensionId": extension_id,
        "tokenPresent": _nonempty_str(
            bridge.get("agentToken" if args.mode == "agent" else "liveToken")
        ),
        "createdFields": created,
        "localJson": str(LOCAL_JSON),
        "gitignored": True,
    }
    json.dump(meta, sys.stdout)
    sys.stdout.write("\n")
    return 0 if meta["tokenPresent"] and (args.mode == "agent" or extension_id) else 1


if __name__ == "__main__":
    raise SystemExit(main())
