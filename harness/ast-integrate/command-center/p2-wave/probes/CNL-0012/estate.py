"""Live vendor reachability + mounted-server inventory. READ-ONLY. No secret values."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from redact import classify_secret, credential_env_names

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DECLARED_VENDORS = ("anthropic", "openai")
VENDOR_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY"),
    "openai": ("OPENAI_API_KEY", "OPENAI_API_KEY_CODEX", "CODEX_API_KEY"),
    "cursor": ("CURSOR_API_KEY", "CURSOR_API_TOKEN"),
}
VENDOR_HOST = {
    "anthropic": "api.anthropic.com",
    "openai": "api.openai.com",
    "xai": "api.x.ai",
}
MCP_CANDIDATES = [
    Path.home() / ".cursor" / "mcp.json",
    Path.home() / ".cursor" / "mcp.json.json",
    REPO / ".cursor" / "mcp.json",
    REPO / ".mcp.json",
    Path.home() / ".claude.json",
    Path.home() / ".claude" / "settings.json",
]
CLI_CONFIG = Path.home() / ".cursor" / "cli-config.json"


def tcp443(host: str, timeout: float = 4.0) -> dict:
    try:
        sock = socket.create_connection((host, 443), timeout=timeout)
        sock.close()
        return {"ok": True, "error": None}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def http_get(url: str, headers: dict | None = None, timeout: float = 8.0) -> dict:
    hdrs = {"User-Agent": "CNL-0012-reachability/1"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": int(resp.status), "error": None}
    except urllib.error.HTTPError as exc:
        return {"status": int(exc.code), "error": "HTTPError"}
    except Exception as exc:
        return {"status": None, "error": type(exc).__name__}


def _first_present(names: tuple[str, ...]) -> tuple[str | None, dict]:
    for name in names:
        cls = classify_secret(os.environ.get(name))
        if cls["present"]:
            return name, cls
    empty = classify_secret(None)
    return None, empty


def _auth_probe(vendor: str, present_name: str | None) -> dict:
    val = os.environ.get(present_name) if present_name else None
    if not val or not val.strip():
        return {"status": None, "error": "credential-absent"}
    token = val.strip()
    if vendor == "anthropic":
        return http_get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": token,
                "anthropic-version": "2023-06-01",
            },
        )
    if vendor == "openai":
        return http_get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": "Bearer " + token},
        )
    return {"status": None, "error": "no-auth-probe"}


def session_from_cli() -> dict:
    if not CLI_CONFIG.is_file():
        return {
            "present": False,
            "model_id": None,
            "display_name": None,
            "vendor": None,
            "transport": None,
            "source": str(CLI_CONFIG),
        }
    data = json.loads(CLI_CONFIG.read_text(encoding="utf-8"))
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    selected = data.get("selectedModel") if isinstance(data.get("selectedModel"), dict) else {}
    model_id = model.get("modelId") or selected.get("modelId")
    display = model.get("displayName")
    return {
        "present": True,
        "model_id": model_id,
        "display_name": display,
        "vendor": "cursor",
        "transport": "in-session",
        "source": "~/.cursor/cli-config.json",
        "bytes": CLI_CONFIG.stat().st_size,
        "auth_fields_read": False,
    }


def mcp_inventory() -> dict:
    files = []
    servers: list[str] = []
    for path in MCP_CANDIDATES:
        row = {
            "path": str(path),
            "exists": path.is_file(),
            "size": path.stat().st_size if path.is_file() else 0,
            "server_names": [],
        }
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                data = None
            if isinstance(data, dict):
                block = data.get("mcpServers") or data.get("mcp_servers") or {}
                if isinstance(block, dict):
                    names = sorted(str(k) for k in block.keys())
                    row["server_names"] = names
                    servers.extend(names)
        files.append(row)
    return {
        "signal": "mounted-server-inventory",
        "config_files": files,
        "server_names": sorted(set(servers)),
        "codex_mounted": any("codex" in n.lower() for n in servers),
        "openai_mcp_mounted": any("openai" in n.lower() or "codex" in n.lower() for n in servers),
    }


def process_inventory() -> dict:
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid,comm"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        text = proc.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        text = ""
    hits = []
    for line in text.splitlines()[1:]:
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid, comm = parts
        low = comm.lower()
        if any(tok in low for tok in ("mcp", "codex", "claude")):
            hits.append({"pid": pid, "comm": comm})
    return {
        "signal": "process-table-comm-only",
        "hits": hits,
        "codex_process": any("codex" in h["comm"].lower() for h in hits),
        "mcp_process": any("mcp" in h["comm"].lower() for h in hits),
    }


def vendor_row(vendor: str) -> dict:
    env_names = VENDOR_ENV.get(vendor, ())
    present_name, cred = _first_present(env_names)
    host = VENDOR_HOST.get(vendor)
    net = tcp443(host) if host else {"ok": None, "error": "no-host"}
    unauth = (
        http_get(f"https://{host}/v1/models")
        if host
        else {"status": None, "error": "no-host"}
    )
    auth = _auth_probe(vendor, present_name) if vendor in ("anthropic", "openai") else {
        "status": None,
        "error": "skipped",
    }
    if vendor == "cursor":
        reachable = bool(cred.get("present"))
    else:
        reachable = bool(cred.get("present") and auth.get("status") == 200)
    return {
        "vendor": vendor,
        "declared": vendor in DECLARED_VENDORS,
        "credential_env_checked": list(env_names),
        "credential_env_hit": present_name,
        "credential": cred,
        "network_tcp443": net,
        "http_unauthenticated_models": unauth,
        "http_authenticated_models": auth,
        "reachable": reachable,
    }


def reachable_entries(doc: dict) -> list[dict]:
    entries = []
    session = doc.get("session") or {}
    if session.get("present") and session.get("model_id"):
        cursor_cred = (doc.get("vendors") or {}).get("cursor") or {}
        if (cursor_cred.get("credential") or {}).get("present"):
            entries.append(
                {
                    "vendor": "cursor",
                    "model": session["model_id"],
                    "transport": "in-session",
                    "source": session.get("source"),
                }
            )
    for vendor, row in (doc.get("vendors") or {}).items():
        if not row.get("reachable"):
            continue
        models = row.get("models") or []
        transports = ["api"]
        for model in models:
            for transport in transports:
                entries.append(
                    {
                        "vendor": vendor,
                        "model": model,
                        "transport": transport,
                        "source": "auth-probe",
                    }
                )
    return entries


def measure() -> dict:
    vendors = {
        "anthropic": vendor_row("anthropic"),
        "openai": vendor_row("openai"),
        "cursor": vendor_row("cursor"),
    }
    mcp = mcp_inventory()
    procs = process_inventory()
    session = session_from_cli()
    doc = {
        "probe": "CNL-0012-live-estate",
        "declared_vendors": list(DECLARED_VENDORS),
        "session": session,
        "vendors": vendors,
        "mcp_inventory": mcp,
        "process_inventory": procs,
        "credential_env_names_present": [
            n for n in credential_env_names() if classify_secret(os.environ.get(n))["present"]
        ],
        "signals": [
            "env-credential-presence+http-auth-or-unauth-status",
            "mounted-server-inventory+process-comm",
        ],
        "catalog_named_transports": {
            "anthropic_in_session": session.get("vendor") == "anthropic",
            "openai_via_codex_mcp": bool(mcp.get("codex_mounted") or procs.get("codex_process")),
        },
        "production_select_explicit": {
            "path": "tools/council/participants/select_explicit.py",
            "present": (REPO / "tools/council/participants/select_explicit.py").is_file(),
        },
    }
    doc["reachable_entries"] = reachable_entries(doc)
    return doc


def dump(path: Path, doc: dict) -> None:
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    measured = measure()
    dump(HERE / "probe1-reachability.raw.json", measured)
    print(json.dumps(measured, indent=2, sort_keys=True, ensure_ascii=True))
