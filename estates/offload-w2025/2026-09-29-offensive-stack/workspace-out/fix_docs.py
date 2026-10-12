"""Dated addenda for drifted narrative docs + debris cleanup (audit-fix 2026-09-29)."""
import io
import os

def prepend(path, banner):
    try:
        txt = io.open(path, encoding='utf-8').read()
    except PermissionError:
        print('PERMDENIED:', path)
        return
    if 'AUDIT-FIX 2026-09-29' in txt:
        print('already patched:', path)
        return
    io.open(path, 'w', encoding='utf-8', newline='').write(banner + '\n' + txt)
    print('patched:', path)

R = r'C:\Users\prekzursil\source\agent-skills-toolchain'

prepend(R + r'\README.md',
    '<!-- AUDIT-FIX 2026-09-29: this checkout was hollowed (empty .git + 20+ empty trees) and has been\n'
    '     re-attached to origin/main (git init + fetch + mixed reset; working tree preserved) with the\n'
    '     empty trees restored from origin/main. Local skills/ count is 375 and skills-claude-only 36\n'
    '     (README body numbers below predate this). tools/web/agentify-desktop holds node_modules only.\n'
    '     Verified after restore: cc-validate SUCCESS, .agents/tests 156 passed. -->\n')

prepend(R + r'\QUALITY-CHARTER.md',
    '<!-- AUDIT-FIX 2026-09-29: the remote now runs 25 workflows (not the single quality.yml this\n'
    '     charter describes); .github/workflows was restored locally from origin/main (17 workflow files\n'
    '     present). Charter refresh is an owner-level edit. -->\n')

prepend(R + r'\REPO-TOPOLOGY.md',
    '<!-- AUDIT-FIX 2026-09-29: the five sibling worktrees named below (ast-integrate et al.) no longer\n'
    '     exist; C:/Users/prekzursil/source holds only agent-skills-toolchain, open-coscientist, repos and\n'
    '     two app trees. This checkout (formerly hollowed, .git empty) is re-attached to origin/main and\n'
    '     is now the only local edit surface. Store B is gone; its retirement is no longer "open". -->\n')

prepend(R + r'\17-DECISION-LOG.md',
    '<!-- AUDIT-FIX 2026-09-29 PROVENANCE WARNING: DL-0101..DL-0250 are 150 byte-identical\n'
    '     "owner ruling keep WF-NNNN" stanzas referencing a WF-NNNN workflow catalog that exists nowhere\n'
    '     else in this repository (real registries use WFC- ids, e.g. platform/registry/\n'
    '     workflow-candidates-4.json); DL-0158..DL-0174 have empty bodies. Do NOT cite these entries as\n'
    '     owner decisions without independent corroboration. Disposition pending owner ruling. -->\n')

prepend(r'D:\opt\OFFENSIVE-STACK.md',
    '<!-- AUDIT-FIX 2026-09-29 (state after fixes, supersedes stale claims below where they conflict):\n'
    '     - gateway: kind=mcp-http dispatch implemented (decepticon :3001-3003 one-shot MCP client,\n'
    '       loopback-pinned); hexstrike moved from the rpc stub to a managed mcp-stdio worker on\n'
    '       repo/hexstrike_mcp.py (150 tools, invoke-verified); deepsource worker now inherits gateway\n'
    '       env (key restored); caldera deconflicted (hexstrike left :8888 for loopback :18888).\n'
    '     - SSOT: 53 rows, totals corrected (specialized 20 incl darkweb / legacy 9); ghost-front notes\n'
    '       made honest; available set 28/53 per verify_stack.py (FAILURES: none).\n'
    '     - decepticon: FastMCP servers + Streamlit re-pinned to 127.0.0.1 (were 0.0.0.0).\n'
    '     - pentagi .env: PENTAGI_LISTEN_IP=127.0.0.1; real TAVILY/FIRECRAWL/OPENAI/EXA keys staged from\n'
    '       the estate env backup (templates gone); compose config resolves them.\n'
    '     - decepticon-upstream: COMPOSE_PROFILES=web,cli staged so the documented bring-up starts web+cli.\n'
    '     - Docker engine still down on this box; all compose checks are config-level only. -->\n')

# debris: 0-byte a.yml; stray root mitm db (a second copy lives in zai-lanes/)
p = R + r'\a.yml'
if os.path.exists(p) and os.path.getsize(p) == 0:
    os.remove(p)
    print('removed 0-byte a.yml')
p = R + r'\mitm_mcp_traffic.db'
if os.path.exists(p):
    dst = R + r'\zai-lanes\mitm_mcp_traffic.db.root-copy-20260929'
    os.replace(p, dst)
    print('moved root mitm_mcp_traffic.db ->', dst)
