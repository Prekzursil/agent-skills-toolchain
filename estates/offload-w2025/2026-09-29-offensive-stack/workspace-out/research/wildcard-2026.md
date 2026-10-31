---
title: wildcard-2026
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/wildcard-2026
---

# Research notes: wildcard-2026 — brand-new 2026 agentic offensive tools

Date: 2026-09-29. Researcher lane: wildcard-2026. VM: Windows Server (win32 10.0.26100), no Docker engine (GCP, no VT-x ⇒ WSL2 also unavailable). Estate: CyberStrike 1.1.16 + MCP gateway 127.0.0.1:31100 (43 backends/17 live), Decepticon LangGraph, PentAGI staged docker-pending, Ollama qwen3:4b.

## Backends used (mandate compliance)

- **GitHub**: `gh` CLI authenticated (account Prekzursil). 20 search-query templates + pagination (gh_sweep.py), 12 awesome-list README fetches, 2 GraphQL batch resolvers, 65-repo shortlist verification, 22 README scans, release-asset check.
- **Exa**: 10 queries (incl. Chinese/Japanese). Worked (10/10 results each).
- **Firecrawl**: direct `POST /v1/search` → **HTTP 401 "Unauthorized: Invalid token"** on all 9 attempts (env FIRECRAWL_API_KEY is invalid/expired). Configure-around attempts: (a) estate MCP gateway `http://127.0.0.1:31100/mcp` — initialize OK (`cyberstrike-gateway 1.29.0`, streamable HTTP, session `mcp-session-id` honored), but `tools/list` exposes only **3 tools, none firecrawl/search** to this client → firecrawl front not reachable anonymously. (b) Fell back to ddgs (installed via pip) + WebFetch. Firecrawl is therefore a **recorded dead end**, not a used discovery source.
- **Keyless DDG** (`ddgs` pip): 2 queries (reddit site:, X site:). Reddit results usable, X results were ads/profiles only.
- **HN Algolia** `hn.algolia.com/api/v1/search_by_date`: 12 queries, 228 unique 2026 stories.
- **Reddit**: old.reddit.com/r/{netsec,OffensiveSecurity,bugbounty}/search.json → **HTTP 403 all three** (IP/UA block). Partially covered via ddgs `site:reddit.com` query.
- **arXiv** export API: 1 query, 25 entries, 20 in 2026 (listed below).
- **WebFetch**: agentopfor.ai (1 fetch, successful).

## Every query issued

### GitHub REST search (gh_sweep.py; q=…&sort=updated&per_page=100, pages 1–3)
1. `topic:offensive-security+created:>2026-01-01` → 300 items
2. `topic:red-team+created:>2026-01-01` → 300
3. `topic:red-teaming+created:>2026-01-01` → 300
4. `agentic+pentest+created:>2026-01-01` → 300
5. `autonomous+pentest+created:>2026-01-01` → 300
6. `agentic+pentration+created:>2026-01-01` → 0 (typo template, kept for record)
7. `pentest+agent+created:>2026-01-01` → 300
8. `red+team+agent+created:>2026-01-01` → 300
9. `offensive+security+agent+created:>2026-01-01` → 202
10. `llm+hacking+agent+created:>2026-01-01` → 155
11. `mcp+pentest+created:>2026-01-01` → 300
12. `mcp+red+team+created:>2026-01-01` → 227
13. `exploit+generation+llm+created:>2026-01-01` → 21
14. `llm+fuzzing+created:>2026-01-01` → 217
15. `attack+path+agent+created:>2026-01-01` → 103
16. `agentic+ctf+created:>2026-01-01` → 300
17. `adversary+emulation+llm+created:>2026-01-01` → 5
18. `autonomous+hacking+created:>2026-01-01` → 212
19. `ai+hacking+agent+created:>2026-04-01` → 300
20. `pentest+mcp+server+created:>2026-04-01` → 79
→ **3220 unique repos** (out/research/gh_sweep_results.json). Filtered (STRONG-offensive AND agentic regex): 2438 (out/research/gh_filtered.txt). Second pass with CJK keywords (渗透|红队|漏洞|攻击|靶场… AND agent|MCP|大模型…): 59 more (out/research/gh_filter2.py).

### Awesome-lists walked (README via `gh api repos/X/readme`)
Yeti-791/Awesome-Offensive-AI-Agentic-Landscape (pushed 2026-09-10, 98 links) · R00T-Kim/awesome-offensive-mcp (2026-05-27, 102) · yeyintminthuhtut/awesome-ai-offensive-security (2026-07-30, 224) · skyvanguard/awesome-ai-pentesting (2026-09-28, 152) · Ed-Marcavage/awesome-security-agent-harnesses (2026-09-22, 85) · pazo01/awesome-cyber-ai-arsenal (2026-09-28, 221) · scadastrangelove/awesome-ai-security-tools (2026-09-27, 355) · sbilly/awesome-security (2026-01-11, 189).
404 dead ends: Letszooming/awesome-red-teaming, GangZhuo/awesome-red-teaming, Gotham/awesome-llm-security (wrong owners — not retried, canonical 2026 lists already covered). punkpeye/awesome-mcp-servers README → 0 extractable links (site-driven).
1089 flat links → GraphQL resolve (ghql_batch.py first run: 11/14 chunks failed on single bad names → fixed with recursive halving in ghql_retry.py) → **1052 resolved, 30+ repos created 2026+** (out/research/awesome_resolved.json).

### HN Algolia (tags=story, created_at_i>1767225600)
Queries: "agentic pentest", "autonomous pentest", "pentest agent", "red team agent", "offensive security agent", "AI pentesting", "LLM red team", "hacking agent", "MCP security", "agentic security", "autonomous hacking", "pentest AI open source". → out/research/hn_stories.json.

### Exa (api.exa.ai/search, 10 results each)
"brand new agentic offensive security tool released 2026 github" · "autonomous penetration testing agent framework 2026 open source" · "MCP server red team operations tool 2026" · "AI agent hacking framework launched 2026" · "new AI pentesting tool nobody talks about 2026" · "Claude Code offensive security skills 2026" · "agentic CTF solver tool 2026" · "红队 AI 智能体 渗透 工具 2026 开源" · "自動ペンテスト AIエージェント 2026 ツール" · "post-trained model that pen tests Argus Red" → out/research/exa_fc_results.json.

### Firecrawl (dead end, 401 invalid token ×9 searches + 1 scrape)
Queries attempted: "new agentic offensive security tools september 2026", "autonomous pentest agent open source 2026", "AI red teaming framework new release 2026", "agentic security tool launched 2026 github trending", "Nightcrawler AI pentesting agent smartphone", "new agentic offensive security tools 2026", "autonomous pentest agent open source 2026 github", "Agent OPFOR open source AI red teaming", "nightcrawler AI pentesting agent garagehq"; scrape https://agentopfor.ai/ → all 401.

### Reddit / X / arXiv / misc
- old.reddit r/netsec, r/OffensiveSecurity, r/bugbounty search.json → 403 ×3 (blocked).
- ddgs: `site:reddit.com/r/netsec agentic pentest tool 2026` (5 ok) · `site:x.com agentic pentest OR "red team" tool 2026` (8, all noise: bing ad, KitPloit profile, Fortune/Anthropic article) — X unusable without auth; recorded as dead end.
- arXiv: `all:"agentic" AND all:"penetration testing"` (25 results). 2026 hits: 2609.28940 (JEV/Laya calibration), 2609.30325 ScopeBench, 2609.22664 (capability→assurance framework), 2609.16694 (secure AI pentest agents), 2609.10780 (rising capability tracking), 2609.08093 (pentest vs honeypots), 2609.07344 (structured state long-horizon), 2608.26237 (trace-level provenance for agentic offensive evals), 2608.21423 (Agentic Security systematization — landscape cross-check), 2608.14352 ATLAS, 2608.14216 MazeRunner, 2608.12996 ATOBench, 2607.26998 AgentSnare, 2607.20255 ethics, 2607.15263 cost-aware eval, 2607.14006, 2607.13085 (coding agents as pentest baselines), 2607.09653 VEXAIoT, 2607.02605 survey. Papers checked for code: none shipped a repo in top results except ATLAS/FirmAgent (NDSS artifacts) — noted, not tool-grade.
- WebFetch: https://agentopfor.ai/ → GitHub = KeyValueSoftwareSystems/opfor (verified below).

### Verification calls
- GraphQL shortlist resolve of 66 repos → 65 verified (out/research/shortlist_verified.json). Missing: `xoxruns/deadend-cli` (actual owner straylabs-ai, resolved separately: created **2025**-07-22 — near-miss, excluded from 2026-born but noted: 311★, "81% (KIMI K2.5) on XBOW's benchmark in full b…"); `caoshanpu/AutoRedTeam-Orchestrator` (gone/renamed — dead end).
- `gh api repos/KeyValueSoftwareSystems/opfor` → 582★, created 2026-04-06, pushed 2026-09-29.
- `gh api repos/chainreactors/cyber-harness/releases/latest` → v0.4.0 assets include **aiscan_windows_amd64.zip** + aiscan-full_windows_amd64.zip (Windows-native proof).
- 22 README scans for install/Windows evidence → out/research/readme_scans.json (key lines quoted per tool below).

## Estate-fit exclusions
- CyberStrikeus/CyberStrike (2899★, 2026-02) — already installed (v1.1.16).
- xtenex/hexstrike-ai, PentAGI, mitmproxy/frida/caldera MCPs — already in estate.
- martian56/redcell (LangGraph AI red-team, 323★) — Docker/Kali-container required → same pending bucket as PentAGI (docker value only).
- xalgorix/xalgorix (1142★, Go) — Linux/macOS prebuilt only (README platform badge Linux; install script Linux/macOS; Docker image) → docker.
- garagehq/nightcrawler (HN 120pt, 816★) — targets Kali NetHunter chroot on smartphones → not Windows.
- weidutech/PentestPi — README: "Linux / macOS / WSL2"; estate has no VT-x ⇒ WSL2 unavailable → wsl-classified.
- h5i-dev/h5i (662★, Rust red-team workspace) — install.sh Linux/macOS, Chromium features Linux/macOS only → unknown/native-risky.

## Final tool shortlist (verified evidence)

| Tool | Repo | Stars | Created | Pushed | Windows evidence |
|---|---|---|---|---|---|
| reverse-skill | zhaoxuya520/reverse-skill | 38705 | 2026-05-13 | 2026-09-22 | README L164 PowerShell refresh script, L242 "CI … Windows + Ubuntu"; install = git clone |
| Claude-Red | SnailSploit/Claude-Red | 7096 | 2026-03-04 | 2026-09-19 | skills for ~/.claude/skills (client-neutral); Windows offensive skills (L199-200) |
| T3MP3ST | elder-plinius/T3MP3ST | 6277 | 2026-07-02 | 2026-09-08 | README L156 "Works on Windows (PowerShell) … Requires git and npm" |
| Agentic-Bug-Hunter | awarexone/Agentic-Bug-Hunter | 5205 | 2026-03-08 | 2026-09-28 | `uv tool install agentic-bug-hunter` (L79); Ollama supported (L220) |
| Claude-BugHunter | elementalsouls/Claude-BugHunter | 4713 | 2026-05-05 | 2026-09-29 | Claude Code skill bundle (82 skills) |
| VulnClaw | Netw0rkNoob/VulnClaw | 3462 | 2026-04-18 | 2026-09-23 | `pip install vulnclaw` (L98); Windows Chrome CDP path documented (L435-436); Docker optional |
| hack-skills | yaklang/hack-skills | 2333 | 2026-04-07 | 2026-09-13 | skill pack (any agent host) |
| pentest-ai-agents | 0xSteph/pentest-ai-agents | 2290 | 2026-03-28 | 2026-08-16 | Claude Code subagents pack |
| pentest-ai (ptai) | 0xSteph/pentest-ai | 1708 | 2026-04-04 | 2026-09-13 | `pipx install ptai` py3.10–3.14 (L17-22); Ollama route w/ `$env:PENTEST_AI_MODEL` (L43-56) |
| PentesterFlow/agent | PentesterFlow/agent | 1382 | 2026-05-31 | 2026-08-31 | install.ps1 + `pentesterflow-windows-x64.exe` asset (L106-124); Ollama provider (L217) |
| open-reverselab | LING71671/open-reverselab | 1190 | 2026-06-17 | 2026-09-29 | "Windows (recommended for first run)" START_HERE.bat (L107); PowerShell board installers (L117-120) |
| Cybermes | Zyrexnn/Cybermes | 894 | 2026-08-19 | 2026-09-19 | platform badge "Linux \| macOS \| Windows \| Docker" (L18); `npx -y cybermes-mcp install` |
| ctf-agent | verialabs/ctf-agent | 818 | 2026-03-23 | 2026-03-29 | 1st place BSidesSF 2026 CTF; python |
| nightcrawler | garagehq/nightcrawler | 816 | 2026-04-29 | 2026-08-19 | Kali NetHunter chroot (L125) → not Windows |
| pentestcode | s0ld13rr/pentestcode | 721 | 2026-07-08 | 2026-09-02 | TS multi-agent; release v0.1.3 |
| StrikeAgent_AtkBrain-Flash | Yean-Sec/StrikeAgent_AtkBrain-Flash | 573 | 2026-09-02 | 2026-09-29 | python; self-evolving loop |
| opfor (Agent OPFOR) | KeyValueSoftwareSystems/opfor | 582 | 2026-04-06 | 2026-09-29 | `npm install -g @keyvaluesystems/agent-opfor-cli` (README L50) |
| blitzstrike | shinthink/blitzstrike | 488 | 2026-09-12 | 2026-09-29 | TS MCP toolbelt v1.0.0 |
| AgentHound | adithyan-ak/AgentHound | 442 | 2026-04-05 | 2026-09-29 | Go; attacks AI-agent infra |
| S1N6H/pentest-harness | S1N6H/pentest-harness | 400 | 2026-08-26 | 2026-09-11 | TS self-hosted harness |
| oh-my-open-pentest | zakirkun/oh-my-open-pentest | 375 | 2026-06-18 | 2026-08-11 | `bunx oh-my-open-pentest install`; 109 tools auto-install |
| vibe-pentest | ok-helloworld/vibe-pentest | 343 | 2026-05-20 | 2026-09-21 | python multi-agent web pentest |
| redcell | martian56/redcell | 323 | 2026-08-02 | 2026-09-18 | Docker+Kali (L74-99) → docker only |
| cyber-harness (aiscan) | chainreactors/cyber-harness | 309 | 2026-05-07 | 2026-09-28 | **aiscan_windows_amd64.zip** release asset (verified) |
| red-run | blacklanternsecurity/red-run | 278 | 2026-02-22 | 2026-09-28 | Claude Code toolkit (bbot team) |
| Argus (AI-agent red-team) | gy15901580825/Argus | 205 | 2026-05-28 | 2026-08-25 | python, 205 probes vs agent endpoints |
| 0sec-labs/0 | 0sec-labs/0 | 195 | 2026-08-19 | 2026-09-28 | TS harness v0.13.0, "find AND fix" |
| reverse-flow-skill | lingbol088-spec/reverse-flow-skill | 924 | 2026-06-30 | 2026-07-24 | CTF RE flow skill for Codex/agents |
| cain-agent | cdxiaodong/cain-agent | 961 | 2026-03-18 | 2026-09-29 | `pip install -e .` (L40); cloud module AWS/Azure/GCP/Aliyun |
| hacker-bob | vmihalis/hacker-bob | 99 | 2026-03-31 | 2026-09-26 | `npm install --global hacker-bob@latest`; "17 CVEs across 9 projects" |
| ktol1/RedTeam-Agent | ktol1/RedTeam-Agent | 72 | 2026-02-28 | 2026-04-24 | MCP framework wrapping gogo/fscan/httpx/nuclei |
| dhunter | Dest1ny-Sec/dhunter | 63 | 2026-08-15 | 2026-08-18 | Go; blackboard engine |
| Luvv-MCP | Dest1ny-Sec/Luvv-MCP | 42 | 2026-06-12 | 2026-08-19 | npm MCP; 18k fingerprint rules |
| paranoid | kulchankas/paranoid | 42 | 2026-09-15 | 2026-09-27 | /hack-me agent skill |
| FlowLens | xiaoli-one/FlowLens | 30 | 2026-06-11 | 2026-08-12 | passive logic-vuln scanner + agent verify |
| Atlas | MingyiSecLab/Atlas | 29 | 2026-09-11 | 2026-09-26 | Electron+Mastra desktop agent |
| VERDICT | vvts-alpha/VERDICT | 22 | 2026-06-12 | 2026-09-10 | TS, evidence-first, behind-login |
| hexgraph | branover/hexgraph | 20 | 2026-05-30 | 2026-08-15 | agentic binary/firmware vuln research |
| CyberPenda | n1majne3/CyberPenda | 20 | 2026-06-19 | 2026-09-29 | Go daemon + dashboard |
| shannon-on-claude-code | us/shannon-on-claude-code | 15 | 2026-03-05 | 2026-09-19 | "No Docker" (L7) but tool deps via apt → Linux/WSL |
| HunterX | nullc0d30/HunterX | 13 | 2026-02-02 | 2026-09-07 | python discovery/validation/proof |
| mcpwn | D0rs4n/mcpwn | 10 | 2026-06-14 | 2026-06-20 | MCP attack tool (no README desc) |
| NeuroSploit | Red-Team-Leaders/NeuroSploit | 6 | 2026-08-27 | 2026-08-27 | Rust, 435 agents (stale) |
| qwythos | MickyBalladelli/qwythos | 3 | 2026-06-30 | 2026-06-30 | Ollama abliterated 9B for offensive work |
| mcp-vanguard | skyvanguard/mcp-vanguard | 3 | 2026-01-30 | 2026-02-22 | README L10-17: "native Windows/WSL bridge"; 89 tools; `npm install` |
| Creation | AntAISecurityLab/Creation | 3 | 2026-09-11 | 2026-09-11 | agentic real-world exploit system |
| decoy-redteam | decoy-run/decoy-redteam | 2 | 2026-04-02 | 2026-08-31 | MCP-server red team, proves exploits |
| hackmyagent | opena2a-org/hackmyagent | 51 | 2026-01-30 | 2026-09-29 | "Metasploit for AI agents"; 170 open issues (caveat) |

Near-miss (pre-2026 but 2026-hot): straylabs-ai/deadend-cli (311★, created 2025-07-22, XBOW-benchmark 81% w/ KIMI K2.5). Commercial/proprietary signals (no repo tool): ArgusRed by Cosine (post-trained pentest model CLI, HN 93pt), AWS Security Agent, Penligent, insom.ai, CyberAgents.pro.

## Source-diversity notes
- Chinese ecosystem (found via gh CJK pass + exa CN query): VulnClaw, vibe-pentest, dhunter, Luvv-MCP, FlowLens, StrikeAgent_AtkBrain-Flash, cain-agent, reverse-flow-skill, llm-sec-range, ktol1/RedTeam-Agent, RuwoScan, xuanjian — the Tencent Tsec-Hackathon repo (Yeti-791, 815★) and its Awesome-Offensive-AI-Agentic-Landscape list are the hub.
- Japanese: only commercial/blog results (AWS Security Agent article, IPA/MITOU report) — no new OSS tool surfaced.
- Defensible gap: X/Twitter search unusable (no auth, ddgs noise). Reddit direct 403; partially compensated via ddgs site: search (5 hits, no new tools beyond already-found). Firecrawl fully dead (invalid key, gateway exposes no firecrawl tool to anonymous MCP).