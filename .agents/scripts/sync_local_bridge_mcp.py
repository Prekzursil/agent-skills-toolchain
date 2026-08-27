import json
from pathlib import Path

import mcp_control_plane as control

PROJECT_ROOT = Path(r"C:\Users\Prekzursil")
AGENTS_JSON = PROJECT_ROOT / '.agents' / 'agents.json'
BRIDGE_MCP = PROJECT_ROOT / '.claude-runtime' / 'local-mcp-marketplace' / 'plugins' / 'local-mcp-bridge' / '.mcp.json'


def export_server(defn: dict) -> dict:
    transport = defn.get('transport', 'stdio')
    out: dict = {}
    if transport == 'http':
        out['url'] = defn['url']
        if defn.get('headers'):
            out['headers'] = defn['headers']
    else:
        out['command'] = defn['command']
        out['args'] = defn.get('args', [])
    if defn.get('env'):
        out['env'] = defn['env']
    if defn.get('cwd'):
        out['cwd'] = defn['cwd']
    return out


def main() -> int:
    if not BRIDGE_MCP.exists():
        print(f'skip: bridge MCP file missing: {BRIDGE_MCP}')
        return 0
    config = json.loads(AGENTS_JSON.read_text(encoding='utf-8'))
    control.validate_registry(config)
    agents = control.select_target_servers(
        config,
        'claude',
        plugin_provided=control.CLAUDE_PLUGIN_PROVIDED_SERVERS,
    )
    existing = json.loads(BRIDGE_MCP.read_text(encoding='utf-8'))
    updated = {}
    for name in existing.keys():
        server = agents.get(name)
        if not server:
            continue
        if not server.get('enabled', True):
            continue
        targets = server.get('targets', [])
        if 'claude' not in targets:
            continue
        updated[name] = export_server(server)
    control.atomic_write_json(BRIDGE_MCP, updated)
    print(f'SUCCESS:mcp-local-bridge managed={len(updated)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
