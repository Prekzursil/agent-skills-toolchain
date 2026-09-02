#!/usr/bin/env python3
"""Encode catalog tool_permissions strings into each client's permission model.

"can" means the native language can name the same grant without widening it.
A coarser stand-in is "cannot" plus a named gap. Over-broad intent ("*") is
the opposite: every client must have a documented unrestricted encoding.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
UNIT_ID = "RES-0040"

CLIENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "claude-code",
        "display": "Claude Code",
        "declared_by": "plugin.json supported_clients",
        "mcp_gate": "per-call-prompt",
        "also": ["allowlist", "workspace-trust"],
        "notes": (
            "Default: prompt per tool call. permissions.allow / ask / deny are "
            "allowlists (deny, then ask, then allow). Project allow rules wait "
            "on workspace trust (folder trust-on-first-open, not per-tool TOFU). "
            "bypassPermissions skips prompts. File path checks consult "
            "Edit(path)/Read(path), not Write(path)."
        ),
    },
    {
        "id": "codex",
        "display": "Codex CLI",
        "declared_by": "plugin.json supported_clients",
        "mcp_gate": "allowlist",
        "also": ["per-call-prompt", "sandbox"],
        "notes": (
            "approval_policy (untrusted / on-request / never) plus sandbox_mode "
            "(read-only / workspace-write / danger-full-access). MCP servers "
            "expose enabled_tools / disabled_tools. No catalog-shaped "
            "Write(path), Read, WebSearch, or WebFetch permission tokens."
        ),
    },
    {
        "id": "cursor",
        "display": "Cursor",
        "declared_by": "live-delivery-host",
        "mcp_gate": "allowlist",
        "also": ["per-call-prompt", "auto-review-classifier"],
        "notes": (
            "IDE permissions.json mcpAllowlist is server:tool only. CLI "
            "cli-config.json tokens: Mcp(server:tool), Write(path), Read(path), "
            "WebFetch(domain), Shell(cmd). No WebSearch token. Auto-review "
            "classifies leftover Shell/MCP/Fetch calls."
        ),
    },
    {
        "id": "antigravity",
        "display": "Google Antigravity / agy",
        "declared_by": "catalog-named-host (TST-0049)",
        "mcp_gate": "per-call-prompt",
        "also": ["allowlist"],
        "notes": (
            "Unconfigured MCP defaults to Ask. Native rules: mcp(server/tool), "
            "mcp(server/*), mcp(*), write_file(path), read_file(path), "
            "read_url(domain), execute_url(domain), command(prefix). Workspace "
            "file read/write is auto-allowed. No WebSearch / WebFetch names."
        ),
    },
)

MCP_RE = re.compile(r"^mcp__([A-Za-z0-9._-]+)__([A-Za-z0-9._-]+)$")
TOOL_ARG_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\((.*)\)$")
TOOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def load_real_list() -> list[str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            perms = unit.get("tool_permissions")
            if not isinstance(perms, list) or not perms:
                raise RuntimeError("RES-0040 tool_permissions missing")
            return [str(x) for x in perms]
    raise RuntimeError("RES-0040 missing from catalog")


def parse_entry(entry: str) -> dict[str, str]:
    mcp = MCP_RE.match(entry)
    if mcp:
        return {
            "kind": "mcp",
            "server": mcp.group(1),
            "tool": mcp.group(2),
            "raw": entry,
        }
    if entry == "*":
        return {"kind": "unrestricted", "raw": entry}
    arg = TOOL_ARG_RE.match(entry)
    if arg:
        return {
            "kind": "tool-arg",
            "tool": arg.group(1),
            "arg": arg.group(2),
            "raw": entry,
        }
    if TOOL_RE.match(entry):
        return {"kind": "tool", "tool": entry, "raw": entry}
    return {"kind": "unknown", "raw": entry}


def _can(encoding: Any, native: str, caveat: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "verdict": "can",
        "encoding": encoding,
        "native_form": native,
        "gaps": [],
    }
    if caveat:
        row["caveat"] = caveat
    return row


def _cannot(reason: str, best_effort: Any = None) -> dict[str, Any]:
    return {
        "verdict": "cannot",
        "encoding": best_effort,
        "native_form": None,
        "gaps": [reason],
    }


def encode_claude(parsed: dict[str, str]) -> dict[str, Any]:
    raw = parsed["raw"]
    if parsed["kind"] == "unrestricted":
        return _can(
            {"permissions": {"defaultMode": "bypassPermissions"}},
            "permissions.defaultMode=bypassPermissions",
            caveat=(
                "An unanchored allow glob '*' is skipped and does not "
                "auto-approve. Unrestricted intent maps to bypassPermissions."
            ),
        )
    if parsed["kind"] == "mcp":
        return _can({"permissions": {"allow": [raw]}}, raw)
    if parsed["kind"] == "tool-arg" and parsed.get("tool") == "Write":
        return _can(
            {"permissions": {"allow": [raw]}},
            raw,
            caveat=(
                "DECLARED: Write(path) is a valid allow token. ENFORCED path "
                "checks consult Edit(path)/Read(path) only; Write(path) is "
                "accepted but not consulted. Least-privilege path enforcement "
                "requires Edit(" + parsed["arg"] + ")."
            ),
        )
    if parsed["kind"] in {"tool", "tool-arg"}:
        return _can({"permissions": {"allow": [raw]}}, raw)
    return _cannot(f"unrecognised catalog token {raw!r}")


def encode_codex(parsed: dict[str, str]) -> dict[str, Any]:
    if parsed["kind"] == "unrestricted":
        return _can(
            {
                "approval_policy": "never",
                "sandbox_mode": "danger-full-access",
            },
            "approval_policy=never + sandbox_mode=danger-full-access",
        )
    if parsed["kind"] == "mcp":
        server, tool = parsed["server"], parsed["tool"]
        encoding = {
            "mcp_servers": {server: {"enabled_tools": [tool]}}
        }
        native = f"mcp_servers.{server}.enabled_tools=[{tool}]"
        return _can(encoding, native)
    tool = parsed.get("tool") or ""
    if parsed["kind"] == "tool-arg" and tool == "Write":
        return _cannot(
            "no path-scoped Write(path); sandbox_mode=workspace-write is a lossy superset",
            {"lossy_superset": {"sandbox_mode": "workspace-write"}},
        )
    if parsed["kind"] in {"tool", "tool-arg"} and tool in {
        "Read",
        "Write",
        "WebSearch",
        "WebFetch",
        "Bash",
        "Grep",
        "Glob",
        "Edit",
        "PowerShell",
    }:
        return _cannot(
            f"Codex has no permission token named {tool}; approval_policy/sandbox are coarser",
            {"lossy_superset": {"approval_policy": "never"}},
        )
    return _cannot(f"no Codex encoding for {parsed['raw']}")


def encode_cursor(parsed: dict[str, str]) -> dict[str, Any]:
    """Cursor CLI tokens from cursor.com/docs/cli/reference/permissions.md."""
    if parsed["kind"] == "unrestricted":
        return _can(
            {
                "permissions": {
                    "allow": [
                        "Mcp(*:*)",
                        "WebFetch(*)",
                        "Write(**)",
                        "Read(**)",
                        "Shell(*)",
                    ]
                },
                "ide_permissions_json": {"mcpAllowlist": ["*:*"]},
            },
            "Mcp(*:*) + WebFetch(*) + Write(**) + Read(**) + Shell(*)",
        )
    if parsed["kind"] == "mcp":
        token = f"{parsed['server']}:{parsed['tool']}"
        return _can(
            {
                "permissions": {"allow": [f"Mcp({token})"]},
                "ide_permissions_json": {"mcpAllowlist": [token]},
            },
            f"Mcp({token})",
        )
    if parsed["kind"] == "tool-arg" and parsed.get("tool") == "Write":
        native = f"Write({parsed['arg']})"
        return _can(
            {"permissions": {"allow": [native]}},
            native,
            caveat="CLI Write(path) only. IDE mcpAllowlist cannot path-scope file writes.",
        )
    if parsed["kind"] == "tool" and parsed.get("tool") == "Read":
        return _can(
            {"permissions": {"allow": ["Read(**)"]}},
            "Read(**)",
            caveat="CLI requires a path glob; Read(**) is the unrestricted-workspace form.",
        )
    if parsed["kind"] == "tool" and parsed.get("tool") == "WebFetch":
        return _can(
            {"permissions": {"allow": ["WebFetch(*)"]}},
            "WebFetch(*)",
            caveat="CLI WebFetch is domain-scoped; WebFetch(*) is unrestricted domains.",
        )
    if parsed["kind"] == "tool" and parsed.get("tool") == "WebSearch":
        return _cannot(
            "Cursor CLI has WebFetch(domain) and Mcp(server:tool) but no WebSearch token"
        )
    if parsed["kind"] in {"tool", "tool-arg"}:
        return _cannot(f"no Cursor encoding for {parsed['raw']}")
    return _cannot(f"unrecognised catalog token {parsed['raw']!r}")


def encode_antigravity(parsed: dict[str, str]) -> dict[str, Any]:
    if parsed["kind"] == "unrestricted":
        return _can(
            {
                "permissions": {
                    "allow": [
                        "mcp(*)",
                        "write_file(*)",
                        "read_file(*)",
                        "read_url(*)",
                        "execute_url(*)",
                        "command(*)",
                    ]
                }
            },
            "mcp(*) + write_file(*) + read_file(*) + read_url(*) + command(*)",
        )
    if parsed["kind"] == "mcp":
        native = f"mcp({parsed['server']}/{parsed['tool']})"
        return _can({"permissions": {"allow": [native]}}, native)
    if parsed["kind"] == "tool-arg" and parsed.get("tool") == "Write":
        native = f"write_file({parsed['arg']})"
        return _can({"permissions": {"allow": [native]}}, native)
    if parsed["kind"] == "tool" and parsed.get("tool") == "Read":
        return _cannot(
            "no catalog Read token; workspace files auto-allow. read_file(*) would widen to the whole filesystem"
        )
    if parsed["kind"] in {"tool", "tool-arg"} and parsed.get("tool") in {
        "WebSearch",
        "WebFetch",
    }:
        return _cannot(
            f"{parsed.get('tool')} is not native; read_url(domain)/execute_url(domain) are a different surface",
            {"lossy_superset": "read_url(*)"},
        )
    if parsed["kind"] in {"tool", "tool-arg"}:
        return _cannot(f"no Antigravity encoding for {parsed['raw']}")
    return _cannot(f"unrecognised catalog token {parsed['raw']!r}")


ENCODERS = {
    "claude-code": encode_claude,
    "codex": encode_codex,
    "cursor": encode_cursor,
    "antigravity": encode_antigravity,
}


def encode_list(client_id: str, entries: list[str]) -> dict[str, Any]:
    fn = ENCODERS[client_id]
    per_entry = []
    for entry in entries:
        parsed = parse_entry(entry)
        row = fn(parsed)
        row["catalog_entry"] = entry
        row["parsed"] = {k: v for k, v in parsed.items() if k != "raw"}
        per_entry.append(row)
    cans = [r["verdict"] == "can" for r in per_entry]
    overall = "can" if cans and all(cans) else "cannot"
    can_n = sum(1 for x in cans if x)
    cannot_n = sum(1 for x in cans if not x)
    n = len(per_entry)
    return {
        "client_id": client_id,
        "verdict": overall,
        "per_entry": per_entry,
        "can_count": can_n,
        "cannot_count": cannot_n,
        "entry_count": n,
        # aliases used by probes/emitter
        "can_count": can_n,
        "cannot_count": cannot_n,
        "entry_count": n,
    }


def encode_all(entries: list[str]) -> list[dict[str, Any]]:
    return [encode_list(cid, entries) for cid in ENCODERS]


def overbroad_list() -> list[str]:
    return ["*"]


# Probe/emitter aliases
load_real_list = load_real_list
encode_all = encode_all
encode_all = encode_all
overbroad_list = overbroad_list
overbroad_list = overbroad_list
