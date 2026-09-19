# Stateless deployment: merge SSOT registry (agents.json) MCP servers into
# Hermes config.yaml mcp_servers (HTTP-hub-only transport policy, G-1 decision 2026-09-03).
# Idempotent: derives the Hermes entry set from agents.json every run; preserves all
# non-hermes sections and any manually-added mcp_servers entries (never listed in agents.json).
# Registry servers WITHOUT a 'hermes' target are REMOVED from config.yaml if they were
# previously deployed (so re-targeting in agents.json flows through).

import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(r"C:\Users\Prekzursil\.agents")
REGISTRY = ROOT / "agents.json"
HERMES_HOME = pathlib.Path(r"C:\Users\Prekzursil\AppData\Local\hermes")
CONFIG = HERMES_HOME / "config.yaml"
BACKUP_DIR = HERMES_HOME / "backups"

# HTTP transports only (G-1). stdio servers are NOT deployed to Hermes even when
# target-listed; they must be fronted by a hub (e.g. cyberstrike mcp-proxy supervisor)
# before they can gain a 'hermes' target.
ALLOWED_TRANSPORTS = {"url"}


def load_registry_servers() -> dict:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return reg["mcp"]["servers"]


def http_entry_for(name: str, srv: dict) -> dict | None:
    """Build a Hermes mcp_servers entry from a registry server. HTTP only."""
    url = srv.get("url")
    if not url:
        return None
    entry = {"url": url}
    headers = srv.get("headers")
    if isinstance(headers, dict) and headers:
        entry["headers"] = headers
    return entry


def serialize_server(name: str, e: dict, indent: str = "  ") -> list[str]:
    lines = [f"{indent}{name}:"]
    lines.append(f"{indent}  url: {json.dumps(e['url'])}")
    if "headers" in e:
        lines.append(f"{indent}  headers:")
        for k, v in e["headers"].items():
            lines.append(f"{indent}    {k}: {json.dumps(v)}")
    if "timeout" in e:
        lines.append(f"{indent}  timeout: {int(e['timeout'])}")
    return lines


def main() -> int:
    servers = load_registry_servers()
    desired: dict[str, dict] = {}
    for name, srv in servers.items():
        if "hermes" not in (srv.get("targets") or []):
            continue
        if srv.get("enabled") is False:
            continue
        entry = http_entry_for(name, srv)
        if entry is None:
            # stdio or unknown transport: not deployable under G-1 policy
            print(f"SKIP (non-HTTP transport): {name}")
            continue
        desired[name] = entry

    text = CONFIG.read_text(encoding="utf-8")
    m = re.search(r"^mcp_servers:\s*$", text, re.M)
    if not m:
        # insert before 'toolsets:' anchor or append
        t = re.search(r"^toolsets:", text, re.M)
        insert_at = t.start() if t else len(text)
        text = text[:insert_at] + "mcp_servers:\n" + text[insert_at:]
        m = re.search(r"^mcp_servers:\s*$", text, re.M)

    start = m.end()
    # find end of the mcp_servers block (next top-level key)
    rest = text[start:]
    em = re.search(r"^[a-zA-Z_][\w-]*:.*$", rest, re.M)
    end = start + (em.start() if em else len(rest))

    # Parse existing entries to preserve manual (non-registry) ones
    existing_block = text[start:end]
    manual: dict[str, dict] = {}
    for mm in re.finditer(r"^  ([\w-]+):\n((?:    .*\n?)*)", existing_block, re.M):
        nm = mm.group(1)
        if nm in servers:  # registry-listed: replaced by desired state
            continue
        # preserve verbatim: keep raw lines
        manual[nm] = mm.group(0)

    body_lines = []
    for name in sorted(desired) :
        body_lines += serialize_server(name, desired[name])
    for name, raw in manual.items():
        body_lines += raw.rstrip("\n").split("\n")

    new_block = ("\n".join(body_lines) + "\n") if body_lines else ""
    new_text = text[:start] + "\n" + new_block + text[end:]

    # backup + write
    BACKUP_DIR.mkdir(exist_ok=True)
    import datetime
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(CONFIG, BACKUP_DIR / f"config.yaml.bak-{stamp}")
    CONFIG.write_text(new_text, encoding="utf-8")
    print(f"SUCCESS:hermes-mcp-deploy servers={len(desired)} manual={len(manual)}")
    for name in sorted(desired):
        print(f"  {name} -> {desired[name]['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
