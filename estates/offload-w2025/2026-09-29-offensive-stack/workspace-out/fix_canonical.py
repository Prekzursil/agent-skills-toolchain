"""canonical-mcp-servers.json audit-fix 2026-09-29.

Remove the 12 ghost entries whose installs are gone from this machine (the git
history now restored in this repo preserves them for revival); fix the
basic-memory port to the live listener; bump the stale tooluniverse pin to the
version actually running on this box; register real, verified installs the
registry never knew about.
"""
import json
import shutil

P = r'C:\Users\prekzursil\source\agent-skills-toolchain\tools\mcp\canonical-mcp-servers.json'
shutil.copy2(P, P + '.bak-auditfix-20260929')
d = json.load(open(P, encoding='utf-8'))
ms = d['mcpServers']

GHOSTS = ['agent-mail', 'apktool-mcp', 'cloud-audit', 'fb-messenger', 'github_cli',
          'jadx-mcp', 'ocr-suite', 'openmm-md', 'paper-search', 'perplexity',
          'rdkit', 'schrodinger']
removed = [g for g in GHOSTS if ms.pop(g, None) is not None]

# basic-memory: canonical pointed at dead 8765; live listener is 18765 (netstat-verified)
ms['basic-memory'] = {"type": "http", "url": "http://127.0.0.1:18765/mcp"}

# tooluniverse: pin was 3 versions behind the running install
ms['tooluniverse'] = {"command": "uvx", "args": ["tooluniverse==1.5.0"]}

# real, verified installs previously unknown to the canonical registry
ADDITIONS = {
    "cyberstrike-gateway": {"type": "http", "url": "http://127.0.0.1:31100/mcp"},
    "patent-search-mcp": {"command": "C:\\Python314\\python.exe",
                          "args": ["C:\\Users\\prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\patent-search-mcp\\server.py"]},
    "tiktok-mcp": {"command": "C:\\Python314\\python.exe",
                   "args": ["C:\\Users\\prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\tiktok-mcp\\server.py"]},
    "hacktricks": {"command": "node",
                   "args": ["C:\\Users\\prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\hacktricks-mcp-server\\dist\\index.js"],
                   "env": {"HACKTRICKS_CORPUS": "D:\\opt\\corpora\\hacktricks"}},
    "video-agent-kit": {"command": "C:\\Python314\\python.exe",
                        "args": ["C:\\Users\\prekzursil\\.agents\\mcp-servers\\video-agent-kit\\mcp\\video_edit_server.py"],
                        "env": {"VE_PLUGIN_ROOT": "C:\\Users\\prekzursil\\.agents\\mcp-servers\\video-agent-kit"}},
    "open-coscientist": {"command": "C:/Users/prekzursil/.venvs/opencoscientist-mcp/Scripts/python.exe",
                         "args": ["C:/Users/prekzursil/source/open-coscientist/mcp_server_stdio.py"]},
    "angr": {"command": "C:\\Users\\prekzursil\\.local\\opt\\angr\\.venv\\Scripts\\angr-mcp.exe"},
    "deepsource": {"command": "node",
                   "args": ["C:\\Users\\prekzursil\\.local\\opt\\deepsource-mcp-server\\deepsource-mcp-wrapper.mjs"],
                   "env": {"DEEPSOURCE_API_KEY": "${DEEPSOURCE_API_KEY}"}},
    "hexstrike-ai": {"command": "D:\\opt\\hexstrike-ai\\.venv\\Scripts\\python.exe",
                     "args": ["D:\\opt\\hexstrike-ai\\repo\\hexstrike_mcp.py", "--server", "http://127.0.0.1:18888"]},
}
added = []
for k, v in ADDITIONS.items():
    if k not in ms:
        ms[k] = v
        added.append(k)

json.dump(d, open(P, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(P, 'a', encoding='utf-8').write('\n')
print('removed ghosts (%d): %s' % (len(removed), ', '.join(removed)))
print('fixed: basic-memory->18765, tooluniverse->1.5.0')
print('added (%d): %s' % (len(added), ', '.join(added)))
print('total entries now:', len(ms))
