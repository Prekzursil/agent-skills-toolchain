"""Audit-fix pass on ~/.agents/agents.json (2026-09-29).

Fixes: control-char corruption, github Bearer prefix, bare-python contract,
ghost enabled entries parked with revival paths, dead 311xx hub entries parked
(consume via gateway :31100), hexstrike rewired to the stdio launcher,
linkedin aligned with its own default-off tag, legacy top-level mcpServers
residue removed. Disabled-list residue (D-06/L-32) is NOT touched.
"""
import json
import re
import shutil
import socket

P = r'C:\Users\prekzursil\.agents\agents.json'
BACKUP = r'C:\Users\prekzursil\.agents\agents.json.bak-auditfix-20260929'
shutil.copy2(P, BACKUP)
d = json.load(open(P, encoding='utf-8'))
sv = d['mcp']['servers']
changes = []


def set_desc(s, note):
    desc = s.get('description', '')
    if 'PARKED 2026-09-29' not in desc and 'audit-fix 2026-09-29' not in desc:
        s['description'] = note + ' || ' + desc


def park(name, reason, tag='parked'):
    s = sv[name]
    if s.get('enabled'):
        s['enabled'] = False
        tags = s.setdefault('tags', [])
        for t in (tag, 'parked-2026-09-29'):
            if t not in tags:
                tags.append(t)
        set_desc(s, 'PARKED 2026-09-29 (audit-fix): ' + reason)
        changes.append('parked ' + name)


def rewire(name, **kw):
    s = sv[name]
    s.update(kw)
    changes.append('rewired ' + name)


# --- 1. control-char corruption (\x08 from JSON \b escapes) ------------------
def fix_ctrl(obj, path=''):
    if isinstance(obj, dict):
        for k in list(obj):
            fix_ctrl(obj[k], path + '.' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            fix_ctrl(v, path + '[%d]' % i)
    elif isinstance(obj, str):
        n = sum(1 for c in obj if ord(c) < 32 and c not in '\n\r\t')
        if n:
            # \x08 came from a literal \b escape before 'olt'/'urp'/'reach'
            fixed = obj.replace('\x08', 'b')
            obj = fixed
            changes.append('decontrolled %s' % path)
        return obj

# walk servers dict manually so we can assign back
def walk_fix(o, path=''):
    if isinstance(o, dict):
        for k in list(o):
            v = o[k]
            if isinstance(v, str):
                if any(ord(c) < 32 and c not in '\n\r\t' for c in v):
                    o[k] = v.replace('\x08', 'b').replace('\x0c', 'f')
                    changes.append('decontrolled %s.%s' % (path, k))
            else:
                walk_fix(v, path + '.' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            if isinstance(v, str):
                if any(ord(c) < 32 and c not in '\n\r\t' for c in v):
                    o[i] = v.replace('\x08', 'b').replace('\x0c', 'f')
                    changes.append('decontrolled %s[%d]' % (path, i))
            else:
                walk_fix(v, path + '[%d]' % i)

walk_fix(d['mcp']['servers'], 'mcp.servers')

# --- 2. github Authorization Bearer prefix ----------------------------------
gh = sv['github']
if gh.get('headers', {}).get('Authorization') == '${GITHUB_MCP_PAT}':
    gh['headers']['Authorization'] = 'Bearer ${GITHUB_MCP_PAT}'
    changes.append('github Authorization Bearer prefix')

# --- 3. video-agent-kit: contract interpreter (3.14 import-tested) ----------
vak = sv['video-agent-kit']
if vak.get('command') == 'python':
    vak['command'] = r'C:\Python314\python.exe'
    set_desc(vak, 'audit-fix 2026-09-29: bare `python` (3.12) replaced with the estate interpreter C:\\Python314\\python.exe (server imports verified on 3.14).')
    changes.append('video-agent-kit command pinned to Python314')

# --- 4. dead 311xx hub band: park + point at the live gateway ---------------
HUB = ['cloud-audit', 'cloud-audit-hub', 'cve-mcp', 'cve-mcp-hub',
       'github-security', 'github-security-hub', 'nuclei', 'nuclei-hub',
       'osint', 'osint-hub', 'semgrep', 'semgrep-hub']
for n in HUB:
    park(n, 'CyberStrike mcp-proxy hub port dead (3111x band down; only gateway :31100 up). '
            'Supervisor script D:/opt/cyberstrike-mcp/start-cyberstrike-mcp-http.ps1 no longer exists; '
            'the rebuilt kit runs the single gateway D:/opt/cyberstrike-mcp/gateway-server.py on :31100. '
            'Consume these backends via server cyberstrike-gateway tool harness_invoke instead of direct mounts. '
            'Revival: re-point this entry at a live hub port if the hub fleet is ever rebuilt.',
         'parked-dead-hub-port')

# --- 5. ghost installs ------------------------------------------------------
park('dbx-ai', 'Install absent: tools/mcp/dbx-ai (dbx-ai-mcp-server.py) no longer exists on this machine. '
               'Revival: restore the dbx-ai MCP server tree and re-enable.',
     'parked-install-missing')
park('biomni-hub', 'Install gutted: hub/.venv exists but hub/server.py entrypoint is gone. '
                   'Revival: restore the biomni-hub server.py entrypoint and re-enable.',
     'parked-install-missing')
park('lifesciences', 'Install absent: C:/Users/Prekzursil/source/lifesciences-research no longer exists. '
                     'Revival: restore the lifesciences-research checkout and re-enable.',
     'parked-install-missing')
park('cursor-bridge', 'Install absent: D:/opt/cursor-bridge/cursor_bridge_mcp.py no longer exists. '
                      'Revival: restore the cursor-bridge install and re-enable.',
     'parked-install-missing')
park('zai-lane-a', 'Install absent: D:/bolt (zai-entitlement-fuzz lane incl. zai-anon-mcp.py) is gone. '
                   'Revival: restore D:/bolt lane tree and re-enable.',
     'parked-install-missing')
park('github_cli', 'Command unresolvable: gh-cli-mcp is neither on PATH nor in the global npm tree. '
                   'Revival: npm i -g gh-cli-mcp (or restore the global install) and re-enable.',
     'parked-install-missing')
park('burp', 'Install absent: jdk-21 java.exe and BurpSuite mcp-proxy-all.jar are both missing; SSE :9876 closed. '
             'Revival: install JDK 21 + Burp Suite mcp-proxy, start Burp headless, then re-enable.',
     'parked-install-missing')
park('breach-intel', 'Install absent: D:/opt/breach-mcp/breach_intel_mcp.py and the D:/bolt credentials file are both gone '
                     '(args[0] backspace corruption fixed in place 2026-09-29). '
                     'Revival: restore D:/opt/breach-mcp + D:/bolt/credentials/breach-vendor-keys.json and re-enable.',
     'parked-install-missing')
park('agent-mail', 'Full ghost: install .local/opt/mcp_agent_mail is gone; ports 8812 (canonical) and 18812 (real) have no listener. '
                   'Revival: restore the mcp_agent_mail install and start its bus, then re-enable.',
     'parked-install-missing')
park('biomni', 'WSL front :7870 not running and superseded by cloud-hub-first per MCP-UNIFICATION-CENSUS-2026-09-29. '
               'Revival: wsl bm-start (Biomni A1 server ~/Biomni/biomni_mcp_server.py), then re-enable.',
     'parked-superseded')
# sci-hub only if mirror still DNS-fails
try:
    socket.getaddrinfo('sci-hub.se', 443)
except OSError:
    park('sci-hub', 'Mirror https://sci-hub.se DNS-fails (getaddrinfo, 2026-09-29); package installs but the server is unusable. '
                    'Revival: set SCIHUB_MIRROR to a reachable mirror and re-enable.',
         'parked-mirror-dead')

# --- 6. linkedin: align with its own default-off/unapproved tags ------------
li = sv['linkedin']
if li.get('enabled') and 'default-off' in li.get('tags', []):
    li['enabled'] = False
    set_desc(li, 'audit-fix 2026-09-29: enabled flipped to false to match this entry\'s own default-off/unapproved tags; '
                 'per-session manager approval (recorded gate) re-enables it for that session\'s config.')
    changes.append('linkedin enabled=false (default-off alignment)')

# --- 7. hexstrike: wire the stdio launcher (loopback HTTP API behind it) ----
for n in ('hexstrike-ai', 'hexstrike-ai-hub'):
    s = sv.get(n)
    if s is None:
        continue
    s['transport'] = 'stdio'
    s.pop('url', None)
    s['command'] = r'C:\Python314\python.exe'
    s['args'] = [r'D:\opt\hexstrike-ai\hexstrike_mcp_launcher.py']
    set_desc(s, 'audit-fix 2026-09-29: rewired from dead hub port :31113 to the framed-stdio bridge '
                'D:/opt/hexstrike-ai/hexstrike_mcp_launcher.py (ensures the loopback HexStrike HTTP API on 127.0.0.1:8888, '
                'then bridges framed MCP stdio to it). Registered 2026-09-29; server now binds 127.0.0.1 only.')
    changes.append('rewired ' + n + ' to stdio launcher')

# --- 8. stale supervisor references in remaining descriptions ---------------
for name, s in sv.items():
    desc = s.get('description', '')
    if 'start-cyberstrike-mcp-http.ps1' in desc:
        s['description'] = desc.replace(
            'start-cyberstrike-mcp-http.ps1',
            'cyberstrike-launch.ps1 (single gateway :31100)')
        changes.append('supervisor ref updated in ' + name)

# --- 9. legacy top-level mcpServers residue --------------------------------
if 'mcpServers' in d:
    del d['mcpServers']
    changes.append('removed legacy top-level mcpServers key')

json.dump(d, open(P, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(P, 'a', encoding='utf-8').write('\n')
print('CHANGES(%d):' % len(changes))
for c in changes:
    print(' -', c)
