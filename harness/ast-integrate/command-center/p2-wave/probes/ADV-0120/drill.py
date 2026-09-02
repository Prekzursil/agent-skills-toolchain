"""Disposable-profile uninstall drill for ADV-0120.

Probe 1 inventories unrelated *files*. Probe 2 actually loads hooks / MCP /
settings / skills. A shared JSON document left present but emptied is the
split: inventory can stay green while load goes red.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.payload import census_tree  # noqa: E402
from plugin.uninstall import (  # noqa: E402
    UninstallError,
    naive_empty_shared_json,
    uninstall_plugin,
)

UNIT = "ADV-0120"
VICTIM = "victim-pkg"
UNRELATED_HOOK_IDS = ("tp-session", "tp-guard")
UNRELATED_MCP_ID = "tp-mcp"
UNRELATED_SKILL_ID = "tp-skill"
UNRELATED_THEME = "third-party.dark"
VICTIM_HOOK_ID = "victim-session"
VICTIM_MCP_ID = "victim-mcp"

HOOK_SCRIPT = """\
import os
from pathlib import Path
log = Path(os.environ["HOST_LOAD_LOG"])
hid = os.environ["HOOK_ID"]
with log.open("a", encoding="utf-8") as fh:
    fh.write(f"HOOK-LOAD-MARKER\\thook_id={hid}\\n")
"""

MCP_SCRIPT = """\
import os
from pathlib import Path
log = Path(os.environ["HOST_LOAD_LOG"])
sid = os.environ["MCP_ID"]
with log.open("a", encoding="utf-8") as fh:
    fh.write(f"MCP-LOAD-MARKER\\tserver_id={sid}\\n")
"""

SKILL_BODY = """\
# tp-skill
SKILL-LOAD-MARKER id=tp-skill
Unrelated third-party skill. Must still load after victim uninstall.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _dump(path: Path, doc: Any) -> None:
    _write(path, json.dumps(doc, indent=2, sort_keys=True) + "\n")


def unrelated_file_rels() -> tuple[str, ...]:
    return (
        "plugins/third-party-hooks/hooks/tp_session.py",
        "plugins/third-party-hooks/hooks/tp_guard.py",
        "plugins/third-party-mcp/mcp/tp_mcp.py",
        "plugins/third-party-skills/skills/tp-skill/SKILL.md",
    )


def victim_file_rels() -> tuple[str, ...]:
    return (
        f"plugins/{VICTIM}/plugin.json",
        f"plugins/{VICTIM}/hooks/victim_session.py",
        f"plugins/{VICTIM}/mcp/victim_mcp.py",
    )


def build_claim() -> dict:
    return {
        "plugin_name": VICTIM,
        "claimed_paths": list(victim_file_rels()),
        "claimed_json": [
            {
                "file": "host/hooks.json",
                "array_path": ["hooks", "SessionStart"],
                "match_key": "id",
                "match_value": VICTIM_HOOK_ID,
            },
            {
                "file": "host/mcp.json",
                "object_path": ["mcpServers"],
                "key": VICTIM_MCP_ID,
            },
            {
                "file": "host/settings.json",
                "object_path": ["plugins"],
                "key": VICTIM,
            },
        ],
    }


def seed_profile(profile: Path) -> dict:
    profile.mkdir(parents=True, exist_ok=True)
    _dump(
        profile / ".disposable-profile.json",
        {
            "disposable": True,
            "unit_id": UNIT,
            "never_live_profile": True,
        },
    )
    _dump(
        profile / f"plugins/{VICTIM}/plugin.json",
        {
            "name": VICTIM,
            "version": "1.0.0",
            "permissions": [f"fs:write:plugins/{VICTIM}"],
        },
    )
    _write(profile / f"plugins/{VICTIM}/hooks/victim_session.py", HOOK_SCRIPT)
    _write(profile / f"plugins/{VICTIM}/mcp/victim_mcp.py", MCP_SCRIPT)
    _write(profile / "plugins/third-party-hooks/hooks/tp_session.py", HOOK_SCRIPT)
    _write(profile / "plugins/third-party-hooks/hooks/tp_guard.py", HOOK_SCRIPT)
    _write(profile / "plugins/third-party-mcp/mcp/tp_mcp.py", MCP_SCRIPT)
    _write(
        profile / "plugins/third-party-skills/skills/tp-skill/SKILL.md",
        SKILL_BODY,
    )

    py = sys.executable
    _dump(
        profile / "host" / "hooks.json",
        {
            "version": 1,
            "hooks": {
                "SessionStart": [
                    {
                        "id": "tp-session",
                        "hook": "plugins/third-party-hooks/hooks/tp_session.py",
                    },
                    {
                        "id": VICTIM_HOOK_ID,
                        "hook": f"plugins/{VICTIM}/hooks/victim_session.py",
                    },
                    {
                        "id": "tp-guard",
                        "hook": "plugins/third-party-hooks/hooks/tp_guard.py",
                    },
                ]
            },
        },
    )
    _dump(
        profile / "host" / "mcp.json",
        {
            "mcpServers": {
                UNRELATED_MCP_ID: {
                    "command": py,
                    "args": [
                        "-B",
                        str(profile / "plugins/third-party-mcp/mcp/tp_mcp.py"),
                    ],
                },
                VICTIM_MCP_ID: {
                    "command": py,
                    "args": [
                        "-B",
                        str(profile / f"plugins/{VICTIM}/mcp/victim_mcp.py"),
                    ],
                },
            }
        },
    )
    _dump(
        profile / "host" / "settings.json",
        {
            "theme": {"id": UNRELATED_THEME, "value": "obsidian"},
            "plugins": {
                "third-party-hooks": {"enabled": True},
                VICTIM: {"enabled": True},
                "third-party-mcp": {"enabled": True},
                "third-party-skills": {"enabled": True},
            },
            "skills": [
                {
                    "id": UNRELATED_SKILL_ID,
                    "path": "plugins/third-party-skills/skills/tp-skill/SKILL.md",
                }
            ],
        },
    )
    claim = build_claim()
    _dump(profile / f".uninstall-claim-{VICTIM}.json", claim)
    return claim


def inventory_unrelated(profile: Path) -> dict[str, str]:
    """File-level census of unrelated component artifacts only."""
    out: dict[str, str] = {}
    for rel in unrelated_file_rels():
        path = profile / rel
        if not path.is_file():
            out[rel] = "MISSING"
            continue
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        out[rel] = hashlib.sha256(raw).hexdigest()
    return out


def shared_docs_exist(profile: Path) -> dict[str, bool]:
    return {
        "host/hooks.json": (profile / "host" / "hooks.json").is_file(),
        "host/mcp.json": (profile / "host" / "mcp.json").is_file(),
        "host/settings.json": (profile / "host" / "settings.json").is_file(),
    }


def boot_host(profile: Path) -> dict:
    """Load unrelated hooks, MCP, settings, and skills. Markers, not listings."""
    log = profile / "host-load.log"
    log.write_text("", encoding="utf-8")
    hook_ids: list[str] = []
    mcp_ids: list[str] = []
    errors: list[str] = []

    try:
        hooks_doc = json.loads(
            (profile / "host" / "hooks.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": f"hooks-unreadable:{exc}",
            "hook_ids": [],
            "mcp_ids": [],
        }
    try:
        mcp_doc = json.loads(
            (profile / "host" / "mcp.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": f"mcp-unreadable:{exc}",
            "hook_ids": [],
            "mcp_ids": [],
        }
    try:
        settings = json.loads(
            (profile / "host" / "settings.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": f"settings-unreadable:{exc}",
            "hook_ids": [],
            "mcp_ids": [],
        }

    env_base = os.environ.copy()
    env_base["HOST_LOAD_LOG"] = str(log)
    env_base["PYTHONDONTWRITEBYTECODE"] = "1"

    for _event, rows in (hooks_doc.get("hooks") or {}).items():
        for row in rows or []:
            hid = str(row.get("id") or "")
            rel = str(row.get("hook") or "")
            script = profile / rel
            if not script.is_file():
                errors.append(f"hook-missing:{hid}")
                continue
            env = env_base.copy()
            env["HOOK_ID"] = hid
            try:
                proc = subprocess.run(
                    [sys.executable, "-B", str(script)],
                    cwd=str(profile),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"hook-exec:{hid}:{exc}")
                continue
            if proc.returncode != 0:
                errors.append(f"hook-rc:{hid}:{proc.returncode}")

    for sid, spec in (mcp_doc.get("mcpServers") or {}).items():
        command = str((spec or {}).get("command") or "")
        args = [str(a) for a in ((spec or {}).get("args") or [])]
        env = env_base.copy()
        env["MCP_ID"] = str(sid)
        try:
            proc = subprocess.run(
                [command, *args],
                cwd=str(profile),
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"mcp-exec:{sid}:{exc}")
            continue
        if proc.returncode != 0:
            errors.append(f"mcp-rc:{sid}:{proc.returncode}")

    text = log.read_text(encoding="utf-8") if log.is_file() else ""
    for line in text.splitlines():
        if line.startswith("HOOK-LOAD-MARKER\t"):
            parts = dict(
                token.split("=", 1)
                for token in line.split("\t")[1:]
                if "=" in token
            )
            hid = parts.get("hook_id")
            if hid and hid not in hook_ids:
                hook_ids.append(hid)
        elif line.startswith("MCP-LOAD-MARKER\t"):
            parts = dict(
                token.split("=", 1)
                for token in line.split("\t")[1:]
                if "=" in token
            )
            sid = parts.get("server_id")
            if sid and sid not in mcp_ids:
                mcp_ids.append(sid)

    theme = (settings.get("theme") or {}).get("id")
    plugin_keys = sorted((settings.get("plugins") or {}).keys())
    skill_ok = False
    for row in settings.get("skills") or []:
        if str(row.get("id")) != UNRELATED_SKILL_ID:
            continue
        skill_path = profile / str(row.get("path") or "")
        if skill_path.is_file() and "SKILL-LOAD-MARKER" in skill_path.read_text(
            encoding="utf-8"
        ):
            skill_ok = True

    unrelated_hooks = [h for h in UNRELATED_HOOK_IDS if h in hook_ids]
    unrelated_mcp = UNRELATED_MCP_ID in mcp_ids
    unrelated_plugin = (
        "third-party-hooks" in plugin_keys and "third-party-mcp" in plugin_keys
    )
    exec_failed = any(
        e.startswith("hook-exec:")
        or e.startswith("hook-rc:")
        or e.startswith("mcp-exec:")
        or e.startswith("mcp-rc:")
        for e in errors
    )
    ok = (
        set(unrelated_hooks) == set(UNRELATED_HOOK_IDS)
        and unrelated_mcp
        and theme == UNRELATED_THEME
        and unrelated_plugin
        and skill_ok
        and not exec_failed
    )
    return {
        "ok": ok,
        "hook_ids": hook_ids,
        "mcp_ids": mcp_ids,
        "unrelated_hooks_loaded": unrelated_hooks,
        "unrelated_mcp_loaded": unrelated_mcp,
        "unrelated_theme": theme,
        "unrelated_skill_loaded": skill_ok,
        "plugin_keys": plugin_keys,
        "errors": errors,
        "log": text,
    }


def _diff_inventory(before: dict[str, str], after: dict[str, str]) -> dict:
    removed = sorted(
        k for k in before if after.get(k) == "MISSING" or k not in after
    )
    modified = sorted(
        k
        for k in before
        if k in after and after[k] != "MISSING" and after[k] != before[k]
    )
    return {
        "removed": removed,
        "modified": modified,
        "intact": not removed and not modified,
        "before": before,
        "after": after,
    }


def _run_one(profile: Path, mode: str) -> dict:
    claim = seed_profile(profile)
    before_files = inventory_unrelated(profile)
    before_boot = boot_host(profile)
    if mode == "production":
        result = uninstall_plugin(profile, claim)
    elif mode == "naive-empty":
        result = naive_empty_shared_json(profile)
    else:
        raise ValueError(mode)
    after_files = inventory_unrelated(profile)
    after_boot = boot_host(profile)
    inv = _diff_inventory(before_files, after_files)
    victim_present = any((profile / rel).is_file() for rel in victim_file_rels())
    return {
        "mode": mode,
        "uninstall": result,
        "pre_boot": {
            "ok": before_boot["ok"],
            "unrelated_hooks_loaded": before_boot["unrelated_hooks_loaded"],
            "unrelated_mcp_loaded": before_boot["unrelated_mcp_loaded"],
            "unrelated_skill_loaded": before_boot["unrelated_skill_loaded"],
            "hook_ids": before_boot["hook_ids"],
            "mcp_ids": before_boot["mcp_ids"],
        },
        "post_boot": {
            "ok": after_boot["ok"],
            "unrelated_hooks_loaded": after_boot["unrelated_hooks_loaded"],
            "unrelated_mcp_loaded": after_boot["unrelated_mcp_loaded"],
            "unrelated_skill_loaded": after_boot["unrelated_skill_loaded"],
            "hook_ids": after_boot["hook_ids"],
            "mcp_ids": after_boot["mcp_ids"],
            "plugin_keys": after_boot["plugin_keys"],
            "theme": after_boot.get("unrelated_theme"),
            "errors": after_boot["errors"],
        },
        "inventory": inv,
        "shared_docs_exist_after": shared_docs_exist(profile),
        "victim_files_remain": victim_present,
        "full_census_keys_after": sorted(census_tree(profile)),
    }


def _escape_and_live_refusals() -> dict:
    with tempfile.TemporaryDirectory(prefix="adv0120-refuse-") as tmp:
        root = Path(tmp)
        seed_profile(root)
        claim = build_claim()
        bad = dict(claim)
        bad["claimed_paths"] = ["../outside.txt"]
        escape_refused = False
        try:
            uninstall_plugin(root, bad)
        except UninstallError:
            escape_refused = True
        live = Path(tmp) / "not-a-profile"
        live.mkdir()
        live_refused = False
        try:
            uninstall_plugin(live, claim)
        except UninstallError:
            live_refused = True
        return {
            "path_escape_refused": escape_refused,
            "unmarked_profile_refused": live_refused,
        }


def measure() -> dict:
    refusals = _escape_and_live_refusals()
    parent = Path(tempfile.mkdtemp(prefix="adv0120-drill-"))
    try:
        prod = _run_one(parent / "production", "production")
        naive = _run_one(parent / "naive-empty", "naive-empty")
    finally:
        shutil.rmtree(parent, ignore_errors=True)

    production_inventory_ok = bool(prod["inventory"]["intact"])
    production_load_ok = bool(prod["post_boot"]["ok"])
    pre_load_ok = bool(prod["pre_boot"]["ok"]) and bool(naive["pre_boot"]["ok"])
    naive_inventory_ok = bool(naive["inventory"]["intact"])
    naive_load_ok = bool(naive["post_boot"]["ok"])
    victim_gone = prod["victim_files_remain"] is False
    shared_remain = all(prod["shared_docs_exist_after"].values())
    naive_split = naive_inventory_ok and (not naive_load_ok)

    passed = (
        pre_load_ok
        and production_inventory_ok
        and production_load_ok
        and victim_gone
        and shared_remain
        and naive_split
        and refusals["path_escape_refused"]
        and refusals["unmarked_profile_refused"]
    )
    return {
        "unit_id": UNIT,
        "disposable_profile": True,
        "live_profile_touched": False,
        "production": prod,
        "naive_empty": naive,
        "refusals": refusals,
        "pre_uninstall_host_ok": pre_load_ok,
        "production_inventory_intact": production_inventory_ok,
        "production_host_load_ok": production_load_ok,
        "production_victim_removed": victim_gone,
        "production_shared_docs_remain": shared_remain,
        "naive_inventory_intact": naive_inventory_ok,
        "naive_host_load_ok": naive_load_ok,
        "naive_split_inventory_pass_load_fail": naive_split,
        "pass": passed,
    }
