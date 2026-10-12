import json

# ssot: direct adapter (launcher bridge is unnecessary - hexstrike_mcp.py is a
# native FastMCP stdio server; the framed bridge deadlocks line-delimited clients)
P = r'D:\opt\cyberstrike-mcp\mcp-ssot.json'
d = json.load(open(P, encoding='utf-8'))
for b in d['backends']:
    if b['name'] == 'hexstrike':
        b['command'] = [r'D:\opt\hexstrike-ai\.venv\Scripts\python.exe',
                        r'D:\opt\hexstrike-ai\repo\hexstrike_mcp.py',
                        '--server', 'http://127.0.0.1:18888']
        b['entry'] = 'repo/hexstrike_mcp.py'
        b['note'] = ('HexStrike AI local API - 150+ offensive tools. audit-fix 2026-09-29: moved from the '
                     'never-invocable kind=rpc row to a managed mcp-stdio worker on repo/hexstrike_mcp.py '
                     '(native FastMCP stdio; the framed launcher bridge is not needed and deadlocks line-delimited '
                     'clients). Server binds 127.0.0.1 only on the estate port 18888 (HEXSTRIKE_PORT env; '
                     'hexstrike_server.py patched to honor HEXSTRIKE_HOST instead of hardcoded 0.0.0.0). '
                     'Install root D:/opt/hexstrike-ai (pinned ref 8333779 + local loopback patch).')
json.dump(d, open(P, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(P, 'a', encoding='utf-8').write('\n')
print('ssot hexstrike row -> direct adapter')

# agents.json: same rewiring for the client-facing entries
A = r'C:\Users\prekzursil\.agents\agents.json'
a = json.load(open(A, encoding='utf-8'))
for n in ('hexstrike-ai', 'hexstrike-ai-hub'):
    s = a['mcp']['servers'][n]
    s['command'] = r'D:\opt\hexstrike-ai\.venv\Scripts\python.exe'
    s['args'] = [r'D:\opt\hexstrike-ai\repo\hexstrike_mcp.py', '--server', 'http://127.0.0.1:18888']
    s['description'] = ('audit-fix 2026-09-29: wired to the HexStrike MCP adapter repo/hexstrike_mcp.py '
                        '(native stdio MCP; 150 tools) against the loopback-only HTTP API on 127.0.0.1:18888. '
                        '|| ' + s.get('description', ''))
json.dump(a, open(A, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(A, 'a', encoding='utf-8').write('\n')
print('agents.json hexstrike entries -> direct adapter')
