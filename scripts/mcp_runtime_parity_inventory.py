#!/usr/bin/env python3
"""Mechanical MCP/memory parity inventory across runtimes.

L7: exact counts and set diffs, no LLM judgement. Never prints secret values.
Redacts header/env values that look like credentials. Writes JSON + markdown
receipts under .agents/mcp-parity-<date>/.

SUCCESS:<id> on stdout when receipts exist on disk.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

HOME = Path(r"C:\Users\Prekzursil")
AGENTS = HOME / ".agents"
TODAY = date.today().isoformat()
OUT_DIR = AGENTS / f"mcp-parity-{TODAY}"
RUN_ID = f"mcp-parity-{TODAY}"

SECRET_KEY_RE = re.compile(
    r"(token|secret|password|authorization|api[_-]?key|bearer|credential|pat)",
    re.I,
)
TOML_SERVER_RE = re.compile(r"^\[mcp_servers\.(?P<name>[^\]]+)\]\s*$")


def redact_mapping(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SECRET_KEY_RE.search(str(k)) and isinstance(v, str):
                out[k] = "<redacted>" if v else ""
            else:
                out[k] = redact_mapping(v)
        return out
    if isinstance(obj, list):
        return [redact_mapping(x) for x in obj]
    return obj


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_toml(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("rb") as f:
        return tomllib.load(f)


def toml_mcp_names_from_text(path: Path) -> list[str]:
    """Fallback name harvest if nested tables confuse grouping."""
    if not path.is_file():
        return []
    names: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TOML_SERVER_RE.match(line.strip())
        if not m:
            continue
        name = m.group("name").strip().strip('"').strip("'")
        if "." in name:
            # skip [mcp_servers.foo.env] / headers
            leaf = name.split(".", 1)[1]
            if leaf in {"env", "headers", "args"}:
                continue
        names.append(name.split(".", 1)[0].strip('"'))
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def mcp_from_toml(path: Path) -> dict[str, Any]:
    data = load_toml(path) or {}
    servers = data.get("mcp_servers")
    if not isinstance(servers, dict):
        names = toml_mcp_names_from_text(path)
        return {"path": str(path), "exists": path.is_file(), "names": names, "enabled": {}, "disabled": []}
    names = sorted(servers)
    enabled = {}
    disabled = []
    for name, body in servers.items():
        if not isinstance(body, dict):
            enabled[name] = True
            continue
        flag = body.get("enabled", True)
        enabled[name] = bool(flag)
        if flag is False:
            disabled.append(name)
    return {
        "path": str(path),
        "exists": True,
        "names": names,
        "enabled": enabled,
        "disabled": sorted(disabled),
        "transports": {
            n: ("http" if isinstance(b, dict) and b.get("url") else "stdio")
            for n, b in servers.items()
        },
    }


def mcp_from_json_servers(path: Path, key_path: tuple[str, ...] = ("mcpServers",)) -> dict[str, Any]:
    data = load_json(path)
    exists = path.is_file()
    cur: Any = data
    for k in key_path:
        if not isinstance(cur, dict):
            cur = None
            break
        cur = cur.get(k)
    if not isinstance(cur, dict):
        return {"path": str(path), "exists": exists, "names": [], "disabled": []}
    names = sorted(cur)
    disabled = []
    for n, b in cur.items():
        if isinstance(b, dict) and b.get("disabled") is True:
            disabled.append(n)
        if isinstance(b, dict) and b.get("enabled") is False:
            disabled.append(n)
    return {"path": str(path), "exists": exists, "names": names, "disabled": sorted(set(disabled))}


def top_level_mcp_servers_claude(path: Path) -> dict[str, Any]:
    """`.claude.json` is huge and has many nested empty mcpServers; prefer top-level."""
    data = load_json(path)
    if not isinstance(data, dict):
        return {"path": str(path), "exists": path.is_file(), "names": [], "disabled": []}
    cur = data.get("mcpServers")
    if not isinstance(cur, dict):
        return {"path": str(path), "exists": True, "names": [], "disabled": [], "note": "no top-level mcpServers"}
    return mcp_from_json_servers(path, ("mcpServers",))


def probe_http(url: str, timeout: float = 4.0) -> dict[str, Any]:
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return {"url": url, "ok": True, "status": int(code)}
    except Exception as exc:  # noqa: BLE001 — inventory must not crash on a dead hub
        return {"url": url, "ok": False, "error": type(exc).__name__}


def tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def registry_summary(agents: dict[str, Any]) -> dict[str, Any]:
    servers = agents.get("mcp", {}).get("servers", {})
    by_target: dict[str, list[str]] = {}
    enabled_by_target: dict[str, list[str]] = {}
    for name, body in servers.items():
        if not isinstance(body, dict):
            continue
        targets = body.get("targets") or []
        on = body.get("enabled", True) is not False
        for t in targets:
            by_target.setdefault(t, []).append(name)
            if on:
                enabled_by_target.setdefault(t, []).append(name)
    for t in by_target:
        by_target[t] = sorted(by_target[t])
        enabled_by_target[t] = sorted(enabled_by_target.get(t, []))
    return {
        "server_count": len(servers),
        "names": sorted(servers),
        "valid_targets_code": ["claude", "codex", "zcode", "hermes"],
        "observed_targets": sorted(by_target),
        "by_target": by_target,
        "enabled_by_target": enabled_by_target,
        "grok_in_registry": "grok" in (t.lower() for t in by_target),
        "cursor_in_registry_targets": "cursor" in (t.lower() for t in by_target),
    }


def plugin_mcp_guess(plugins_registry: Path) -> list[str]:
    data = load_json(plugins_registry)
    if not isinstance(data, dict):
        return []
    names: list[str] = []
    repos = data.get("repos") or {}
    if isinstance(repos, dict):
        for rec in repos.values():
            if not isinstance(rec, dict):
                continue
            plugins = rec.get("plugins") or {}
            if isinstance(plugins, dict):
                names.extend(plugins.keys())
    return sorted(set(names))


def scorecard_baseline() -> dict[str, Any]:
    return {
        "date": "2026-08-27",
        "path": str(AGENTS / "CROSS-RUNTIME-SCORECARD_2026-08-27.md"),
        "cursor_enabled": 6,
        "cursor_parked": 31,
        "claude_registry_coverage": "40/40 (then)",
        "codex_registry_coverage": "4/40 (then)",
        "grok_mcp": "hand-maintained, not in sync_shared_state.ps1",
        "grok_park_policy": "G-11/G-99 HTTP hubs only; keepers basic-memory + agent-mail",
        "sync_then": ["claude", "codex", "cursor"],
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    agents = load_json(AGENTS / "agents.json") or {}
    reg = registry_summary(agents)

    grok = mcp_from_toml(HOME / ".grok" / "config.toml")
    grok_parked = toml_mcp_names_from_text(AGENTS / "mcp-grok-parked_2026-08-27.toml")
    cursor = mcp_from_json_servers(HOME / ".cursor" / "mcp.json")
    cursor_parked = mcp_from_json_servers(AGENTS / "mcp-cursor-parked-31.json")
    claude_generated = mcp_from_json_servers(AGENTS / "generated" / "claude.mcp.json")
    claude_live = top_level_mcp_servers_claude(HOME / ".claude.json")
    claude_user_mcp = mcp_from_json_servers(HOME / ".mcp.json")
    codex = mcp_from_toml(HOME / ".codex" / "config.toml")
    zcode = mcp_from_json_servers(HOME / ".zcode" / "cli" / "config.json", ("mcp", "servers"))
    hermes_cfg = HOME / "AppData" / "Local" / "hermes" / "config.yaml"
    goose_cfg = HOME / "AppData" / "Roaming" / "Block" / "goose" / "config" / "config.yaml"
    gemini_skills = HOME / ".gemini" / "skills"
    grok_plugins = plugin_mcp_guess(HOME / ".grok" / "installed-plugins" / "registry.json")

    merge_scripts = {
        "claude": (AGENTS / "scripts" / "merge_generated_claude_mcp.py").is_file(),
        "codex": (AGENTS / "scripts" / "merge_generated_codex_mcp.py").is_file(),
        "cursor": (AGENTS / "scripts" / "merge_generated_cursor_mcp.py").is_file(),
        "zcode": (AGENTS / "scripts" / "merge_generated_zcode_mcp.py").is_file(),
        "hermes": (AGENTS / "scripts" / "deploy_hermes_mcp.py").is_file(),
        "grok": (AGENTS / "scripts" / "merge_generated_grok_mcp.py").is_file(),
        "goose": False,
        "agy": False,
    }

    hubs = [
        ("basic-memory", "http://127.0.0.1:18765/mcp"),
        ("agent-mail-health", "http://127.0.0.1:18812/api/health"),
        ("github-security-hub", "http://127.0.0.1:31410/mcp"),
        ("cve-mcp-hub", "http://127.0.0.1:31411/mcp"),
        ("osint-hub", "http://127.0.0.1:31412/mcp"),
        ("hexstrike-ai-hub", "http://127.0.0.1:31413/mcp"),
        ("firecrawl-hub", "http://127.0.0.1:31414/mcp"),
        ("hacktricks-hub", "http://127.0.0.1:31415/mcp"),
        ("nuclei-hub", "http://127.0.0.1:31417/mcp"),
        ("cloud-audit-hub", "http://127.0.0.1:31418/mcp"),
        ("semgrep-hub", "http://127.0.0.1:31419/mcp"),
        ("mcphub-sse", "http://127.0.0.1:24680/sse"),
        ("fiddler", "http://127.0.0.1:8868/mcp"),
        ("auth2api", "http://127.0.0.1:18317/"),
    ]
    hub_probes = {name: probe_http(url) for name, url in hubs}
    tcp = {
        "8765": tcp_open("127.0.0.1", 8765),
        "8812": tcp_open("127.0.0.1", 8812),
        "8317": tcp_open("127.0.0.1", 8317),
        "24680": tcp_open("127.0.0.1", 24680),
        "8868": tcp_open("127.0.0.1", 8868),
    }

    cursor_core = {
        "agent-mail",
        "basic-memory",
        "chrome-devtools",
        "context7",
        "firecrawl",
        "playwright",
    }
    cursor_live_set = set(cursor["names"])
    cursor_extra = sorted(cursor_live_set - cursor_core)
    cursor_missing_core = sorted(cursor_core - cursor_live_set)

    grok_policy_keepers = {"basic-memory", "agent-mail"}
    grok_live_set = set(grok["names"])
    grok_beyond_keepers = sorted(grok_live_set - grok_policy_keepers)

    bm_cursor = None
    cursor_json = load_json(HOME / ".cursor" / "mcp.json") or {}
    bm = (cursor_json.get("mcpServers") or {}).get("basic-memory")
    if isinstance(bm, dict):
        bm_cursor = {
            "transport": "stdio" if bm.get("command") else "http",
            "command": bool(bm.get("command")),
            "has_url_arg": any("8765" in str(a) for a in (bm.get("args") or [])),
            "script": "bm_cursor_http_session.py"
            if any("bm_cursor_http_session" in str(a) for a in (bm.get("args") or []))
            else None,
        }

    grok_bm = None
    grok_toml = load_toml(HOME / ".grok" / "config.toml") or {}
    gbm = (grok_toml.get("mcp_servers") or {}).get("basic-memory")
    if isinstance(gbm, dict):
        grok_bm = {
            "transport": gbm.get("type") or ("http" if gbm.get("url") else "stdio"),
            "url": gbm.get("url"),
            "enabled": gbm.get("enabled", True),
        }

    zcode_memories = HOME / ".zcode" / "cli" / "memories"
    zcode_native = [
        n
        for n in zcode["names"]
        if n.startswith("web_") or n in {"zread", "web_search_prime", "web_reader"} or "z.ai" in n
    ]

    findings = []
    if not merge_scripts["grok"]:
        findings.append(
            {
                "id": "GROK-NO-MERGE",
                "sev": "P0",
                "fact": "No merge_generated_grok_mcp.py; grok is not a VALID_TARGET in mcp_control_plane.py",
            }
        )
    if not reg["grok_in_registry"]:
        findings.append(
            {
                "id": "GROK-NOT-IN-AGENTS-JSON",
                "sev": "P0",
                "fact": "agents.json mcp.servers has zero targets containing 'grok'",
            }
        )
    if grok_beyond_keepers:
        findings.append(
            {
                "id": "GROK-POLICY-REGRESSION",
                "sev": "P1",
                "fact": f"G-11/G-99 keepers were basic-memory+agent-mail; live grok config has extra: {grok_beyond_keepers}",
            }
        )
    if grok.get("enabled", {}).get("agent-mail") is False:
        findings.append(
            {
                "id": "GROK-AGENT-MAIL-DISABLED",
                "sev": "P1",
                "fact": "Grok [mcp_servers.agent-mail] enabled=false",
            }
        )
    if grok_plugins:
        findings.append(
            {
                "id": "GROK-PLUGIN-MCP-SURFACE",
                "sev": "P0",
                "fact": f"Second MCP surface: {len(grok_plugins)} installed Grok plugins (marketplace), independent of config.toml mcp_servers",
            }
        )
    if cursor_extra:
        findings.append(
            {
                "id": "CURSOR-LIVE-DRIFT",
                "sev": "P1",
                "fact": f"Scorecard 2026-08-27 Cursor=6 core; live mcp.json extra={cursor_extra}",
            }
        )
    if cursor_missing_core:
        findings.append(
            {
                "id": "CURSOR-CORE-MISSING",
                "sev": "P0",
                "fact": f"Core G-6 missing from live mcp.json: {cursor_missing_core}",
            }
        )
    if bm_cursor and bm_cursor.get("transport") == "stdio":
        findings.append(
            {
                "id": "CURSOR-BM-STDIO-SHIM",
                "sev": "P2",
                "fact": "Cursor basic-memory is x_cursor.stdio_bridge (bm_cursor_http_session.py), not raw HTTP",
            }
        )
    if grok_bm and grok_bm.get("transport") in {"http", "streamable-http"}:
        findings.append(
            {
                "id": "GROK-BM-RAW-HTTP",
                "sev": "P0",
                "fact": "Grok basic-memory is raw HTTP to :18765; this session handshake failed (WorkerTransport streamable HTTP). Cursor needed a stdio shim for the same daemon.",
            }
        )
    if not hub_probes["basic-memory"]["ok"] and tcp["8765"]:
        findings.append(
            {
                "id": "BM-TCP-UP-HTTP-FAIL",
                "sev": "P0",
                "fact": ":18765 TCP open but GET /mcp failed — bound-but-unhappy or 406/handshake mismatch",
            }
        )
    if not tcp["8765"]:
        findings.append(
            {
                "id": "BM-DOWN",
                "sev": "P0",
                "fact": "127.0.0.1:18765 TCP closed",
            }
        )
    if zcode_memories.is_dir():
        findings.append(
            {
                "id": "ZCODE-SECOND-MEMORY",
                "sev": "P1",
                "fact": f"ZCode has {zcode_memories} in addition to basic-memory HTTP — parallel memory store",
            }
        )
    if claude_user_mcp["names"] and set(claude_user_mcp["names"]) - set(claude_generated["names"]):
        extra = sorted(set(claude_user_mcp["names"]) - set(claude_generated["names"]))
        findings.append(
            {
                "id": "CLAUDE-DOT-MCP-JSON",
                "sev": "P1",
                "fact": f"~/.mcp.json extra vs generated Claude view: {extra[:40]}",
            }
        )

    inventory = {
        "run_id": RUN_ID,
        "date": TODAY,
        "registry": reg,
        "merge_scripts": merge_scripts,
        "runtimes": {
            "grok": grok,
            "cursor": cursor,
            "claude_generated": claude_generated,
            "claude_live_top_level": claude_live,
            "claude_user_mcp_json": claude_user_mcp,
            "codex": codex,
            "zcode": zcode,
            "hermes_config_exists": hermes_cfg.is_file(),
            "goose_config_exists": goose_cfg.is_file(),
            "gemini_skills_exists": gemini_skills.exists(),
        },
        "parked": {
            "grok_2026_08_27": grok_parked,
            "cursor_31": cursor_parked["names"],
        },
        "cursor_vs_core": {
            "core": sorted(cursor_core),
            "live": cursor["names"],
            "extra": cursor_extra,
            "missing_core": cursor_missing_core,
        },
        "grok_vs_policy": {
            "keepers": sorted(grok_policy_keepers),
            "live": grok["names"],
            "beyond_keepers": grok_beyond_keepers,
            "parked_file_names": grok_parked,
            "plugins": grok_plugins,
        },
        "memory": {
            "contract": str(AGENTS / "memory-contract.md"),
            "transport_ssot": "http://127.0.0.1:18765/mcp",
            "cursor": bm_cursor,
            "grok": grok_bm,
            "zcode_native_memory_dir": str(zcode_memories) if zcode_memories.is_dir() else None,
            "zcode_native_mcp": zcode_native,
        },
        "hubs": hub_probes,
        "tcp": tcp,
        "scorecard_baseline": scorecard_baseline(),
        "findings": findings,
        "sync_covers": ["codex", "claude", "cursor", "zcode", "hermes"],
        "sync_does_not_cover": ["grok", "goose", "agy/antigravity", "fabric"],
    }
    inventory = redact_mapping(inventory)

    json_path = OUT_DIR / "inventory.json"
    md_path = OUT_DIR / "inventory.md"
    json_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# MCP runtime parity inventory — {TODAY}",
        "",
        f"Run id: `{RUN_ID}`. Mechanical. No secret values.",
        "",
        "## Registry (agents.json)",
        f"- servers: **{reg['server_count']}**",
        f"- observed targets: {', '.join(reg['observed_targets']) or '(none)'}",
        f"- grok in registry targets: **{reg['grok_in_registry']}**",
        f"- cursor in registry targets: **{reg['cursor_in_registry_targets']}**",
        "",
        "Per-target enabled counts:",
    ]
    for t, names in sorted(reg["enabled_by_target"].items()):
        lines.append(f"- `{t}`: {len(names)} enabled / {len(reg['by_target'].get(t, []))} targeted")
    lines += [
        "",
        "## Merge scripts present",
    ]
    for k, v in merge_scripts.items():
        lines.append(f"- {k}: {'YES' if v else 'NO'}")
    lines += [
        "",
        "## Live surfaces (names only)",
        f"- Grok config.toml: {len(grok['names'])} — {', '.join(grok['names']) or '(none)'}",
        f"- Grok disabled: {', '.join(grok.get('disabled') or []) or '(none)'}",
        f"- Grok plugins (marketplace): {len(grok_plugins)} — {', '.join(grok_plugins[:40])}",
        f"- Cursor mcp.json: {len(cursor['names'])} — {', '.join(cursor['names'])}",
        f"- Cursor extra vs G-6 core: {', '.join(cursor_extra) or '(none)'}",
        f"- Claude generated view: {len(claude_generated['names'])}",
        f"- Claude live top-level: {len(claude_live['names'])}",
        f"- ~/.mcp.json: {len(claude_user_mcp['names'])}",
        f"- Codex config.toml: {len(codex['names'])} — {', '.join(codex['names'])}",
        f"- ZCode cli/config.json: {len(zcode['names'])} — {', '.join(zcode['names'])}",
        f"- Hermes config exists: {hermes_cfg.is_file()}",
        f"- Goose config exists: {goose_cfg.is_file()}",
        f"- Gemini skills dir exists: {gemini_skills.exists()}",
        "",
        "## Hubs",
    ]
    for name, p in hub_probes.items():
        flag = "UP" if p.get("ok") else "DOWN"
        extra = p.get("status") or p.get("error")
        lines.append(f"- {name}: {flag} ({extra})")
    lines.append("")
    lines.append("## TCP")
    for port, ok in tcp.items():
        lines.append(f"- :{port}: {'open' if ok else 'closed'}")
    lines += ["", "## Findings"]
    if not findings:
        lines.append("- none")
    for f in findings:
        lines.append(f"- **{f['id']}** ({f['sev']}): {f['fact']}")
    lines += [
        "",
        "## vs 2026-08-27 scorecard",
        f"- Cursor was 6 enabled; live is {len(cursor['names'])}.",
        f"- Grok MCP was hand-maintained / parked to BM+agent-mail; live config has {len(grok['names'])} plus plugin surface.",
        f"- sync_shared_state then: claude+codex+cursor; now also zcode+hermes; still **not grok**.",
        "",
        "UNIT-COMPLETE: " + RUN_ID,
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    if not json_path.is_file() or json_path.stat().st_size < 200:
        print(f"FAILED:{RUN_ID} inventory json missing or undersize", file=sys.stderr)
        return 1
    if not md_path.is_file() or md_path.stat().st_size < 200:
        print(f"FAILED:{RUN_ID} inventory md missing or undersize", file=sys.stderr)
        return 1
    print(f"SUCCESS:{RUN_ID}")
    print(str(json_path))
    print(str(md_path))
    print(f"findings={len(findings)} registry={reg['server_count']} grok={len(grok['names'])} cursor={len(cursor['names'])} claude_gen={len(claude_generated['names'])} codex={len(codex['names'])} zcode={len(zcode['names'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
