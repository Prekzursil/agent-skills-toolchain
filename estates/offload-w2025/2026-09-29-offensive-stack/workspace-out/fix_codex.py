import re

P = r'C:\Users\prekzursil\.codex\config.toml'
src = open(P, encoding='utf-8').read()
orig = src

# 1. remove the dead firecrawl-kit block (port 31114 gone, lane parked estate-wide)
m = re.search(r'\n\[mcp_servers\."firecrawl-kit"\]\n(?:(?!\n\[)[^\n]*\n?)*', src)
if m:
    src = src[:m.start()] + src[m.end():]
    print('removed firecrawl-kit block')

# 2. node_repl: Codex's own runtime (dir gone post-reprovision) - disable, keep settings
m = re.search(r'(\[mcp_servers\.node_repl\]\n)', src)
if m:
    src = src[:m.end()] + 'enabled = false  # audit-fix 2026-09-29: runtime exe gone with C:/Users/prekzursil/AppData/Local/OpenAI/Codex/runtimes/; re-enable when Codex reinstalls the cua_node runtime\n'
    print('node_repl disabled in place')

assert src != orig
open(P, 'w', encoding='utf-8', newline='').write(src)
print('written')
