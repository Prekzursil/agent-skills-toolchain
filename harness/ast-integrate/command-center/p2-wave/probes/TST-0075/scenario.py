#!/usr/bin/env python3
"""Known-good install tree and one seeded breakage per health sub-check."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from health import SUBCHECK_IDS, _sha256_file

HOOKS = ("pre-tool", "post-tool")
SKILLS = ("council",)
MCP = ("local-tools",)
VERSION = "1.4.2"
SENTINELS = {
    "pre-tool": "hook-sentinel-pre-tool-tst0075",
    "post-tool": "hook-sentinel-post-tool-tst0075",
}
MCP_NONCE = {"local-tools": "mcp-nonce-local-tools-tst0075"}
ROUTER_NONCE = "router-nonce-tst0075"
ROUTER_ENDPOINT = "http://127.0.0.1:9/health"


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def materialize_good(root: Path) -> Path:
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    plugin = {
        "name": "phase5-plugin",
        "version": VERSION,
        "hooks": list(HOOKS),
        "skills": list(SKILLS),
        "mcp_servers": list(MCP),
        "router_endpoint": ROUTER_ENDPOINT,
    }
    _write_json(root / "plugin.json", plugin)

    _write_json(
        root / "hooks" / "manifest.json",
        {"hooks": [{"id": hid, "path": f"hooks/{hid}.json"} for hid in HOOKS]},
    )
    for hid in HOOKS:
        _write_json(
            root / "hooks" / f"{hid}.json",
            {"id": hid, "sentinel": SENTINELS[hid], "enabled": True},
        )
        _write_json(
            root / "hooks" / "runtime" / f"{hid}.loaded.json",
            {"hook_id": hid, "sentinel": SENTINELS[hid], "loaded": True},
        )

    skill_md = root / "skills" / "council" / "SKILL.md"
    _write_text(
        skill_md,
        "# council\n\nFour-voice static prompt skill. Not executable policy.\n",
    )
    _write_json(
        root / "skills" / "registry.json",
        {"skills": [{"id": "council", "path": "skills/council/SKILL.md"}]},
    )
    _write_json(
        root / "skills" / "runtime" / "council.registered.json",
        {
            "skill_id": "council",
            "body_sha256": _sha256_file(skill_md),
            "registered": True,
        },
    )

    _write_json(
        root / "mcp" / "servers.json",
        {
            "servers": [
                {
                    "id": "local-tools",
                    "endpoint": "stdio:local-tools",
                    "nonce": MCP_NONCE["local-tools"],
                }
            ]
        },
    )
    _write_json(
        root / "mcp" / "runtime" / "local-tools.pong.json",
        {
            "server_id": "local-tools",
            "nonce": MCP_NONCE["local-tools"],
            "ok": True,
        },
    )

    _write_json(
        root / "router" / "listen.json",
        {"endpoint": ROUTER_ENDPOINT, "nonce": ROUTER_NONCE},
    )
    _write_json(
        root / "router" / "runtime" / "pong.json",
        {"nonce": ROUTER_NONCE, "ok": True},
    )

    (root / "ledger").mkdir()
    _write_text(root / "ledger" / "README.md", "ledger root — writes land here\n")

    blob = root / "cache" / "objects" / "payload.bin"
    _write_bytes(blob, b"cache-object-bytes-tst0075\n")
    _write_json(
        root / "cache" / "index.json",
        {"files": {"cache/objects/payload.bin": _sha256_file(blob)}},
    )

    hashed = {
        "hooks/pre-tool.json": _sha256_file(root / "hooks" / "pre-tool.json"),
        "skills/council/SKILL.md": _sha256_file(skill_md),
    }
    _write_json(root / "deploy" / "installed-version.json", {"version": VERSION})
    _write_json(root / "deploy" / "manifest.json", {"files": hashed})
    return root


BREAKAGE_KIND = {
    "hooks_loaded": "delete runtime loaded markers; hook files remain",
    "skills_registered": "delete runtime registration markers; SKILL.md remains",
    "mcp_reachable": "stale MCP pong nonce; servers.json unchanged",
    "router_responding": "stale router pong nonce; listen.json unchanged",
    "ledger_writable": "replace ledger directory with a regular file",
    "cache_valid": "mutate cache object bytes without updating index",
    "deploy_in_sync": "plugin.json version drifted from installed-version.json",
}


def seed_breakage(root: Path, subcheck: str) -> None:
    root = Path(root)
    if subcheck == "hooks_loaded":
        runtime = root / "hooks" / "runtime"
        if runtime.is_dir():
            shutil.rmtree(runtime)
        return
    if subcheck == "skills_registered":
        runtime = root / "skills" / "runtime"
        if runtime.is_dir():
            shutil.rmtree(runtime)
        return
    if subcheck == "mcp_reachable":
        pong = root / "mcp" / "runtime" / "local-tools.pong.json"
        doc = json.loads(pong.read_text(encoding="utf-8"))
        doc["nonce"] = "stale-" + str(doc.get("nonce"))
        pong.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        return
    if subcheck == "router_responding":
        pong = root / "router" / "runtime" / "pong.json"
        doc = json.loads(pong.read_text(encoding="utf-8"))
        doc["nonce"] = "stale-" + str(doc.get("nonce"))
        pong.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        return
    if subcheck == "ledger_writable":
        ledger = root / "ledger"
        if ledger.is_dir():
            shutil.rmtree(ledger)
        ledger.write_text("not-a-directory\n", encoding="utf-8")
        return
    if subcheck == "cache_valid":
        blob = root / "cache" / "objects" / "payload.bin"
        blob.write_bytes(blob.read_bytes() + b"TAMPER\n")
        return
    if subcheck == "deploy_in_sync":
        plugin_path = root / "plugin.json"
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        plugin["version"] = "9.9.9-drift"
        plugin_path.write_text(json.dumps(plugin, indent=2, sort_keys=True) + "\n")
        return
    raise ValueError(f"unknown subcheck breakage {subcheck}")


def clone_and_break(good: Path, dest: Path, subcheck: str) -> Path:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(good, dest)
    seed_breakage(dest, subcheck)
    return dest
