"""mcp-ssot.json audit-fix 2026-09-29."""
import json
import shutil

P = r'D:\opt\cyberstrike-mcp\mcp-ssot.json'
shutil.copy2(P, P + '.bak-auditfix-20260929')
d = json.load(open(P, encoding='utf-8'))
rows = {b['name']: b for b in d['backends']}
changes = []

# 1. hexstrike: kind=rpc (stub) -> kind=mcp-stdio via the launcher.
#    The HTTP API now binds 127.0.0.1:18888 (estate env HEXSTRIKE_HOST/PORT);
#    the launcher ensures it is up and bridges framed stdio MCP to it.
hs = rows['hexstrike']
hs.pop('rpc', None)
hs['kind'] = 'mcp-stdio'
hs['entry'] = 'hexstrike_mcp_launcher.py'
hs['command'] = ['C:\\Python314\\python.exe', 'D:\\opt\\hexstrike-ai\\hexstrike_mcp_launcher.py']
hs['note'] = ('HexStrike AI local API - 150+ offensive tools. audit-fix 2026-09-29: moved from the '
              'never-invocable kind=rpc row to a managed mcp-stdio worker via the framed-stdio bridge '
              'hexstrike_mcp_launcher.py (paths fixed to repo/). Server binds 127.0.0.1 only on the estate '
              'port 18888 (HEXSTRIKE_PORT env; hexstrike_server.py patched to honor HEXSTRIKE_HOST instead of '
              'hardcoded 0.0.0.0). Install root D:/opt/hexstrike-ai (pinned ref 8333779 + local loopback patch).')
changes.append('hexstrike -> mcp-stdio launcher')

# 2. decepticon x3: kind=rpc -> kind=mcp-http (gateway is a one-shot MCP client)
for name, port, tools in (
    ('decepticon-recon', 3001, 'nmap/curl/dig/whois'),
    ('decepticon-initial-access', 3002, 'hydra/searchsploit'),
    ('decepticon-terminal', 3003, 'sessioned command execution, dual-mode kali/local'),
):
    b = rows[name]
    b.pop('rpc', None)
    b['kind'] = 'mcp-http'
    b['url'] = 'http://127.0.0.1:%d/mcp' % port
    b['note'] = ('Decepticon MCP front (%s) - started by D:/opt/decepticon/start-decepticon.ps1. '
                 'audit-fix 2026-09-29: FastMCP servers pinned to host 127.0.0.1 (were 0.0.0.0) and '
                 'dispatched via kind=mcp-http one-shot MCP client.' % tools)
changes.append('decepticon x3 -> mcp-http')

# 3. caldera: honest row - not installed; hexstrike vacated 8888
cal = rows['caldera']
cal['note'] = ('audit-fix 2026-09-29: caldera is NOT installed on this box (nothing on 127.0.0.1:8888 since '
               'hexstrike moved to loopback :18888 per estate env). Its default port 8888 is now deconflicted. '
               'Probe reports unavailable until an operator installs and starts caldera.')
changes.append('caldera note + deconflict')

# 4. nuclei path note
rows['nuclei']['note'] = ('audit-fix 2026-09-29: resolved binary is C:/Users/prekzursil/.local/bin/nuclei.exe '
                          '(v3.11.1) via PATH; the D:/opt/bin copy loses PATH order. Prior note said D:/opt/bin.')
changes.append('nuclei note')

# 5. deepsource note (key restored from env backup)
rows['deepsource']['note'] = ('audit-fix 2026-09-29: DEEPSOURCE_API_KEY restored to User env from '
                              '.agents/secrets/env-backups/2026-09-29 (was missing after the reprovision). '
                              'Wrapper v1.8.3 spawns via node; lights up when the gateway env carries the key.')
changes.append('deepsource note')

# 6. tavily note (TAVILY_API_KEY restored; _2 never existed in the backups)
rows['tavily']['note'] = ('audit-fix 2026-09-29: TAVILY_API_KEY restored to User env from '
                          '.agents/secrets/env-backups/2026-09-29. TAVILY_API_KEY_2 has no value anywhere '
                          '(backups included) - keyless DDG fallback remains for the second channel.')
changes.append('tavily note')

# 7. firecrawl note: cloud lane needs the key (it is restored), not clearing FIRECRAWL_API_URL
rows['firecrawl']['note'] = ('audit-fix 2026-09-29: FIRECRAWL_API_KEY restored to User env from '
                             '.agents/secrets/env-backups/2026-09-29 (cloud lane). Self-host revival is '
                             'docker-pending at D:/opt/firecrawl-selfhost on external port 31115.')
changes.append('firecrawl note')

# 8. honest notes on module rows whose fronts/ code is absent (14 of 18)
GHOST_FRONT_NOTES = {
    'cloud-audit': '38-tool cloud audit - fronts/cloud_audit.py NEVER LANDED; install was also removed (bun/stdio form dead). Row is probe-honest: unavailable until the backend package lands in fronts/.',
    'github-security': 'claimed 39-tool backend - fronts/github_security.py absent; npx github-security-mcp form exists in agents.json (parked). Unavailable until code lands in fronts/.',
    'cve-mcp': 'claimed 41-tool backend - fronts/cve_mcp.py absent; npx cve-mcp form exists in agents.json (parked). Unavailable until code lands in fronts/.',
    'osint': 'claimed 37-tool backend - fronts/osint.py absent; npx osint-mcp-server form exists in agents.json (parked). Unavailable until code lands in fronts/.',
    'dbx-ai': 'fronts/dbx_ai.py absent AND tools/mcp/dbx-ai install removed from the toolchain tree. Unavailable until either is restored.',
    'angr': 'fronts/angr.py absent; a working angr-mcp.exe exists at C:/Users/prekzursil/.local/opt/angr (.venv) for direct stdio use. Unavailable in-process until fronts/angr.py lands.',
    'jb-library': 'fronts/jb_library.py absent. Unavailable until the backend package lands in fronts/ (EXEC-ALLOWED on estate/pre-authorized targets).',
    'darknet': 'superseded note: live row is the npx darknet-mcp-server mcp-stdio worker below (found by deepweb-coverage 2026-09-29).',
    'dns-security': 'fronts/dns_security.py absent. Unavailable until the backend package lands in fronts/.',
    'mcp-scanner': 'fronts/mcp_scanner.py absent. Unavailable until the backend package lands in fronts/.',
    'satellite': 'fronts/satellite.py absent. Unavailable until the backend package lands in fronts/.',
    'steganography': 'fronts/steganography.py absent. Unavailable until the backend package lands in fronts/.',
    'supply-chain': 'fronts/supply_chain.py absent. Unavailable until the backend package lands in fronts/.',
    'hackbrowser': 'fronts/hackbrowser.py absent. Unavailable until the backend package lands in fronts/.',
}
for name, note in GHOST_FRONT_NOTES.items():
    if rows[name]['kind'] == 'module':
        rows[name]['note'] = note
changes.append('ghost-fronts notes x14')

# 9. catalogs: honest totals
cats = {}
for b in d['backends']:
    cats[b['category']] = cats.get(b['category'], 0) + 1
spec = cats.get('specialized', 0) + cats.get('darkweb', 0)
d['catalogs']['specialized_total'] = spec
d['catalogs']['legacy_total'] = cats.get('legacy', 0)
d['catalogs']['total_backends'] = len(d['backends'])
d['catalogs']['policy'] = ('availability = lazily computed (module importable / binary on PATH / rpc reachable / '
                           'mcp-stdio worker spawn+initialize / mcp-http initialize handshake). An unavailable '
                           'backend stays discoverable and harness_invoke returns its install note. No raw fallback, '
                           'no silent degradation. Decepticon fronts light up when start-decepticon.ps1 runs '
                           '(127.0.0.1:3001-3003); hexstrike lights up through its launcher worker (loopback 18888). '
                           'audit-fix 2026-09-29: totals corrected from 34/12 to the measured 20/9 '
                           '(specialized incl. darkweb / legacy); totals_backends=43.')
changes.append('catalogs totals: 34/12 -> %d/%d (total %d)' % (spec, cats.get('legacy', 0), len(d['backends'])))

json.dump(d, open(P, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(P, 'a', encoding='utf-8').write('\n')
print('CHANGES:')
for c in changes:
    print(' -', c)
