# Adversarial hunter: social/chatter — haul

Angle: tools visible in social/community chatter (HN, Reddit, Telegram indexes, LinkedIn, X) that are NOT in the known-tools list. Date: 2026-09-29.
Workspace: `C:\Users\prekzursil\.zcode\workspace\default`. Raw scrape artifacts under `out/research/_*.html/_*.json`.

## Channel reachability (what actually worked)

| Channel | Status | Method that worked |
|---|---|---|
| Hacker News | **Excellent** | `hn.algolia.com/api/v1/search` + `/items/{id}` (curl) |
| Reddit | **Good** | Z.ai WebSearch snippets + `api.pullpush.io/reddit/search/submission/?ids=...` (direct reddit.com / old.reddit.com / WebFetch all 403; webReader shows bot-check) |
| Telegram (tgstat) | **Good, partial** | `tgstat.com/en/channel/@handle` static pages scrape fine (curl); the tgstat *search* UI is JS-only (search pages render no results); telemetr not reached |
| LinkedIn | **Moderate** | Exa API with `includeDomains:["linkedin.com"]` |
| X/Twitter | **Blocked** | xcancel.com "service is suspended"; nitter.privacyredirect.com serves an Anubis bot-check wall ("Making sure you're not a bot!", verified in `out/research/_nitter2.html`); nitter.space/lightbrd 403, nitter.poast.org dead; Exa has 0 results for `includeDomains:["x.com","twitter.com"]`; Z.ai WebSearch indexes x.com root only. Only indirect mirrors (threadreaderapp/typefully) reachable — returned generic MCP content, no new tools |
| Discord | **Blocked** | disboard.org Cloudflare "Just a moment…" both via curl (403) and webReader. No Discord-sourced finds verified |
| Firecrawl | **Broken on this VM** | `FIRECRAWL_API_KEY` user env is a literal unexpanded `${FIRECRAW...}` placeholder → direct API unusable; used Exa API (`EXA_API_KEY` verified live, e.g. requestId `cc982ad46ee66aa...`) + WebSearch + webReader instead |

## Queries run (exact)

- HN Algolia `search?tags=story`: `pentest`, `pentest agent`, `AI red team`, `hacking agent`, `offensive security LLM`, `MCP kali`, `bug bounty agent`, `pentesting LLM`, `exploitation agent`, `XBOW`; `search_by_date?query=pentest`.
- HN Algolia items fetched: 47296367 (Tengu), 46974791 (bug bounty #86), 45721704 (Bugbunny), 48199725 (VeilGate), 48609231 (ArgusRed), 47372369, 44082372, 48016224(dead id).
- Exa `/search`: reddit-restricted (`0 results both tries`), news.ycombinator-restricted, x.com-restricted (0), threadreaderapp/typefully, linkedin.com, plus open queries: `tengu MCP rfunix`, `numasec`, `ShipSafe Hermes`, `Bugbunny vibecoded`, `VeilGate deception reverse proxy`, `Shannon AI pentest`, `skillaudit`, `Redthread millenniums`, `PentestAgent hexstrike`, `offensive security MCP find-fix-verify`, `pentest MCP servers unified 11 tools`, `MCP penetration testing framework`, `HackerGPT`, `WhiteRabbitNeo`, `hackingBuddyGPT`, `MindFort YC`, `PentestGPT GreyDGL`, `XBOW`.
- Z.ai WebSearch: `site:x.com pentest MCP server AI agent`, `telegram channel pentest AI tools tgstat OR telemetr`, `site:reddit.com "pentest" "MCP" claude tool`, `site:reddit.com AI agent penetration testing tool built`, two follow-ups for named threads, `site:tgstat.com channel MCP pentest...`.
- PullPush API ids: 1rou5fo (PAIStrike), 1r05v4k (Numasec), 1s6wu98 (0xSteph toolkit), 1o4o01l (pentest-ai-killer), 1socexa (ShipSafe/Hermes), 1qc0unz (NullSquare), 1ukdicf, 1v8t86u.
- tgstat channel pages scraped: `@NinjaSecurity` (283 KB, **178 unique github.com links**), `@news4hack` (16 links), `@reconshell` (0 links in page), `@securation`/`@cvebird` (0-byte responses — rate-limited after repeated hits).
- GitHub API `/repos/{owner}/{repo}` for ~75 candidate repos (2 windows of 403 rate-limits hit; all headline repos verified).

## The haul — new tools (not in known list), grouped by discovery channel

### Telegram channel indexes (@NinjaSecurity, @news4hack)
- **robin** — `https://github.com/apurvsinghgautam/robin` — "AI-Powered Dark Web OSINT Tool", 7,379★, pushed 2026-09-26 (GitHub API). Same author's `dark-web-osint-tools` list also on the channel. → darknet cluster.
- **cve-mcp-server** — `https://github.com/mukul975/cve-mcp-server` — "Production-grade MCP server giving Claude 27 security intelligence tools across 21 APIs — CVE lookup, EPSS, CISA KEV, MITRE ATT&CK, Shodan, VirusTotal", 1,596★. → MCP security-intel.
- **skill-scanner** — `https://github.com/cisco-ai-defense/skill-scanner` — "Security Scanner for Agent Skills" (prompt-injection / data-exfil in agent skill packages), 2,565★, Cisco AI Defense.
- **microsoft/agent-governance-toolkit** — 6,362★ — "Policy enforcement, zero-trust identity, execution sandboxing… for autonomous AI agents".
- **agentseal** — `https://github.com/getagentseal/agentseal` — 377★ "Scan your machine for dangerous skills and MCP configs, monitor for supply chain attacks, test prompt injection resistance".
- **onex** — `https://github.com/jackind424/onex` — 943★ "hacking tool installer… can install 370+ Kali tools".
- **H4X-Tools** — `https://github.com/vil/H4X-Tools` — 836★ modular OSINT/recon/scraping toolkit (Linux+Windows).
- **FinalRecon** — `https://github.com/thewhiteh4t/FinalRecon` — 3,003★ all-in-one web recon (classic, but absent from known list).
- **airgorah** — `https://github.com/martin-olivier/airgorah` — 3,662★ WiFi security auditing software.
- **TotalRecall** — `https://github.com/xaitax/TotalRecall` — 167★ extracts Windows 11 Recall activity snapshots (forensics/privacy).
- **Watcher** — `https://github.com/thalesgroup-cert/Watcher` — 1,387★ AI-powered CTI & hunting platform (Thales CERT).
- **nox-framework** — `https://github.com/nox-project/nox-framework` — 331★ OSINT/CTI identity pivoting across 120+ sources.
- **BobTheSmuggler** — `https://github.com/TheCyb3rAlpha/BobTheSmuggler` — 597★ HTML-smuggling payload builder (embedded 7z/zip + HTMLi).
- **roborev** — `https://github.com/kenn-io/roborev` — 1,738★ background code-review DB for AI coding agents (adjacent, not offensive).
- **vmkatz** — `https://github.com/nikaiw/VMkatz` — 1,620★ "Extract Windows credentials directly from VM memory snapshots and virtual disks".
- **DumpBrowserSecrets** — `https://github.com/Maldev-Academy/DumpBrowserSecrets` — 817★ Chromium token/cookie/credential extraction.
- **dirtyfrag** — `https://github.com/V4bel/dirtyfrag` — 5,014★ (README 404 on main branch — description empty; identity unconfirmed beyond handle).
- **RegPwn / RegPwnBOF** — `mdsecactivebreach/RegPwn` (251★) + `Flangvik/RegPwnBOF` (129★).
- **mssqlbof** — `https://github.com/MazX0p/mssqlbof` — 100★ BOF suite speaking TDS 7.4 natively vs MSSQL.
- **ICMP-Ghost** — `https://github.com/JM00NJ/ICMP-Ghost-A-Fileless-x64-Assembly-C2-Agent` — 96★ fileless x64-asm C2, ICMP↔DNS pivoting.
- **flexphish** — `https://github.com/P0cL4bs/flexphish` — 84★ red-team phishing ops toolkit.
- **DeepZero** — `https://github.com/416rehman/DeepZero` — 733★ "Find zero-days while you sleep… parses, decompiles, and analyzes thousands of Windows kernel drivers".
- **OBLITERATUS** — `https://github.com/elder-plinius/OBLITERATUS` — 8,492★, Pliny the Liberator's jailbreak repo ("OBLITERATE THE CHAINS THAT BIND YOU").
- **claudini** — `https://github.com/romovpa/claudini` — 246★ "Autoresearch for LLM adversarial attacks".
- **bug-hunter** — `https://github.com/codexstar69/bug-hunter` — 512★ adversarial AI bug hunter + auto-fix skill for Claude Code/Cursor/Codex/Kiro/Opencode.
- **ULTRASHIP** — `https://github.com/Houseofmvps/ultraship` — 123★ Claude Code plugin: 39 skills/33 tools/11 agents incl. pentesting.
- **dontgo403** — `https://github.com/mbrg/dontgo403` — 48★ 40X bypass (cluster: nomore403, 4-ZERO-3, bypass-403, byp4xx all seen on same channel).
- **dabit3/skill-audit** — 47★ "Audit agent skill definitions for security… across Codex, Claude Code, OpenClaw".
- **crossbow-agent** — `https://github.com/harishsg993010/crossbow-agent` — 245★ "world's first Opensource fully Autonomous AI Security Engineer".
- **L0p4Map** — `https://github.com/HaxL0p4/L0p4Map` — 946★ ARP discovery + nmap + network map.
- Also on the channels but excluded as already-known: `0xSteph/pentest-ai-agents` (= known "pentest-ai-agents (0xsteph)"), `yaklang/hack-skills`, `PurpleAILAB/Decepticon`, `ktol1/RedTeam-Agent`, `SnailSploit/Claude-Red`, `SpecterOps/ConfigManBearPig`, `usestrix/strix`, `elder-plinius/T3MP3ST`. Excluded as criminal-branded: `hexsecteam/worm-gpt`. Meta-index found: `Yeti-791/Awesome-Offensive-AI-Agentic-Landscape` (315★) — "curates open-source projects, papers, benchmarks, commercial solutions in AI penetration testing" — good feed for future sweeps.

### Hacker News
- **Shannon** — `https://github.com/KeygraphHQ/shannon` — **48,486★** "AI pentester for web applications and APIs… analyzes your source code, identifies attack vectors, and executes real exploits to prove vulnerabilities". Referenced in HN comments on ArgusRed (item 48609231: "running shannon on aws/bedrock fully airgapped"). Biggest find of the sweep.
- **Zero (0sec-labs/0)** — `https://github.com/0sec-labs/0` — 222★ "extensible cybersecurity harness for full-stack LLM-driven penetration testing and remediation [RESEARCH PREVIEW]" (story 2026-09-29).
- **ArgusRed / Lumen Outpost (Cosine)** — `https://www.argusred.com/cli` — "We post-trained a model that pen tests instead of refusing" (93 pts, 2026-06-20); RL on Kimi K2.6, free read-only scan CLI (`brew install`), active exploitation gated; company blog `cosine.sh/blog/introducing-lumen-outpost`. ⚠ possible alias with known entry "argus (ai-agent red-team)" — needs dedup decision.
- **Detail** — `https://detail.dev/` — "Detail, a Bug Finder" (67 pts, 2025-12-09).
- **Tengu** — `https://github.com/rfunix/tengu` — 61★ MCP server exposing 80 Kali tools to Claude with input sanitization, target allowlisting, rate limiting, audit logging (HN item 47296367, author rfunix).
- **MCP Security Suite (ninesunsinc)** — `github.com/ninesunsinc` (HN item 44904974, 36 pts): "devs get pwned through MCP tools in ways security scanners completely miss". Org repos API returned empty this session — org may have renamed.
- **MCP-Shield** — `github.com/riseandignite` (HN item 43689178, 134 pts) — "Detect security issues in MCP servers".
- **MCP-Scanner** (HN item 45723699) — "Scan MCP Servers for vulnerabilities" — repo not resolved.
- **Deadend CLI** — `https://github.com/xoxruns/deadend-cli` — "Open-source self-hosted agentic pentest tooling" (18 pts, 2026-02-11). Repo returned 404 this session (possibly renamed/deleted).
- **MindFort (YC X25)** — `https://www.mindfort.ai` — "AI agents for continuous pentesting" (Launch HN, 60 pts); verified on ycombinator.com/companies/mindfort.
- **Vulnetic** — `https://app.vulnetic.ai` — "multi-purpose hacking agent" SaaS (Show HN 45361224; R&D writeup by Vulnetic CEO on Medium).
- **RedThread / MILLENNIUMS.AI** — `https://github.com/matheusht/redthread` — "autonomous red-teaming engine for LLMs… full security lifecycle" + `matheusht/adopt-redthread`; product: millenniums.ai "AI-Native Application Protection Platform powered by Redthread" (Show HN 49875292).
- **BugBunny** — `https://bugbunny.ai` (+ GitHub org `bugbunny-research`, repos API empty) — "AI cybersecurity hire… in Slack and Teams" for bug bounty/pentest (HN item 45721704 "Securing VibeCoded Apps").
- **VeilGate** — `https://github.com/C0oki3s/veilgate` (+ `C0oki3s/veilgate-rules`, veilgate.dev) — "deception reverse proxy… redirects suspected agents into a per-IP-consistent honeypot" (HN item 48199725).
- **Penclaw.ai** — `https://penclaw.ai` — "hire OpenClaw tenant for pentesting" (Show HN 47156511).
- **Bobbin** — `https://github.com/daniele110199/bobbin` — "Pentest with a local LLM, so target data never leaves your machine"; repo self-describes as dependency-free coding agent for small local models via Ollama (HN 2026-09-06).
- **kali-docker-mcp** — `https://github.com/weirdmachine64/kali-docker-mcp` — containerized Kali MCP for semi-autonomous pentesting (2 pts).
- **cyberillo/kali-mcp-server** — HN 47409052 (2026-03-17).
- **Auto-Pentest-GPT-AI** — `https://github.com/Armur-Ai/Auto-Pentest-GPT-AI` (HN 44237903).
- **onelook** — `https://github.com/onelook-ai/onelook` — pentest reports from screen recordings (HN 41002237).
- **XBOW** — `https://xbow.com/` — autonomous pentester that "reached the top spot on HackerOne" (HN 284 pts, 2025-06-24) and found CVE-2026-45185 Exim unauth RCE (HN 72 pts, 2026-05-12). Absent from known list despite being the highest-profile chatter item of 2025.
- Unnamed/unreleased (md note): "Autonomous Bug Bounty Agent: Reached #86 on HackerOne, DoD Triage" (item 46974791, author Layer_8 — scope-enforcing proxy, human-in-loop, no link); "I spent 8 months trying to make LLMs Hack" (item 44082372 — 29 custom agents, Kali on AWS Fargate, no name); "What agentic collaborative pentesting looks like" (video PU5BicXMiio).
- Benchmarks/papers surfaced in chatter (likely covered by other hunters): BountyBench/CyberGym (dawnsongtweets HN 44328370), "Forge: Multi-Agent Graduated Exploitation and Detection Engineering" (arXiv 2606.03453), LLM Agent Honeypot (arXiv 2410.13919 — repo `XuandongZhao/llm-agent-honeypot` 404'd this session), MITRE Offensive Security Eval Framework (2502.15797).

### Reddit (r/cybersecurity, r/Pentesting — threads verified via PullPush archive)
- **Numasec** — `https://github.com/FrancescoStabile/numasec` — 800★ (npm `numasec`, AGPL) — "Claude Code for security": CLI ReAct agent orchestrating nmap/nuclei/sqlmap/ffuf/Playwright, 14 structured-output extractors, evidence trails (thread 1r05v4k).
- **PAIStrike** — `https://paistrike.scantist.io/en` — Scantist's AI platform "end-to-end automated pentesting — from recon to exploitation and reporting… validates exploitability and generates reproducible evidence" (thread 1rou5fo).
- **pentest-ai-killer** — `https://github.com/vietjovi/pentest-ai-killer` — 38★ "pentesting toolkit MCP Agent" (thread 1o4o01l).
- **NullSquare** — `https://nullsquare.net` — continuous pentesting / code-review / compliance agents platform, four discipline agents ("attack surface discovery", early access; thread 1qc0unz).
- **ShipSafe + Hermes** — `https://github.com/asamassekou10/ship-safe` — 849★ (npm `ship-safe`) "29 agents scan 80+ attack classes incl. MCP tool injection"; thread 1socexa describes a ShipSafe-wrapped multi-agent pentest workflow (secrets/CVE/pentest/red-team agents + Lead correlator). Hermes agent security page: shipsafe.sh/hermes.
- `0xSteph/pentest-ai` — thread 1s6wu98 (6 Claude Code subagents, PTES/OWASP/NIST methodology, Sigma output) — **maps to known entry "pentest-ai-agents (0xsteph)"**, listed only as alias confirmation.
- Chatter discussions (no tool): threads 1ukdicf, 1v8t86u (Claude Code/Codex for pentesting; Claude refuses, Codex more permissive — recurring theme in comments).

### LinkedIn chatter (via Exa)
- **PentestAgent** — `https://github.com/GH05TCREW/pentestagent` — **3,073★** "AI agent framework for black-box security testing, supporting bug bounty, red-team, and penetration testing workflows" + prebuilt attack playbooks + HexStrike integration (cybersecuritynews.com/pentestagent).
- **mseep-ai/pentester-mcp** — "integrates 200+ pentesting tools via the Model Context Protocol".
- **Hackerobi/pentest-osint-mcp-server** — "MCP server integrating 25+ OSINT tools… Sherlock, Maigret, Holehe, Nmap".
- **Siemba MCP** — PRNewswire 2026-09-22: "Connecting its offensive security platform directly to AI assistants".
- **NodeZero MCP Server** (Horizon3.ai) — LinkedIn 2025-08-05: "Start Fixing What Matters with agentic workflows" — NodeZero itself absent from known list.
- **Pentest MCP Servers (Pruthu Raut)** — LinkedIn 2026-02-08, "unified interface for integrating 11 popular pentesting tools directly into Claude Desktop via MCP" — repo not resolved.
- **"® MCP Server"** — LinkedIn 2025-08-21 activity 7364285999276855299: "first offensive security MCP Server that feeds validated exploitability data into agentic AI workflows (Find–Fix–Verify)" — brand name stripped in snippet; unresolved lead.
- **MCP Penetration Testing Framework (Deepu A)** — LinkedIn 2025-12-22 announcement — repo not resolved.
- **mcp-redteam** — `https://github.com/m0rvayne/mcp-redteam` — 2★ "Active red-teaming for MCP servers. Source analysis + live exploitation + auto-fix. Claude Code plugin".
- **mcp-stress-test** — `https://github.com/mcp-tool-shop-org/mcp-stress-test` — "Red Team Toolkit for AI agents" (press-release style).
- **Mr-Infect/MCP-Penetration-testing** — OWASP MCP Top 10 checklist + pentest framework.
- **Strobes** — strobes.co — "LiveAgentic Validation Platform… agents validate findings the way an attacker would" (positions as Horizon3 alternative).
- **nbshenxm/pentest-agent** — academic PentestAgent (ACM DOI 10.1145/3708821.3733882).
- Known-list confirmations from LinkedIn: HexStrike AI (0x4m4), fuzzinglabs/mcp-security-hub, Wiz MCP (GA 2026-07-02).

### Older chatter staples verified this session (absent from known list)
- **PentestGPT** — `https://github.com/GreyDGL/PentestGPT` — 15,649★, USENIX Security 2024 Distinguished Artifact, "Automated Penetration Testing Agentic Framework Powered by LLMs" (pentestgpt.com; v1.0.0 agentic pipeline release 2025-12-24).
- **HackingBuddyGPT** — `https://github.com/ipa-lab/hackingBuddyGPT` — "Helping Ethical Hackers use LLMs in 50 Lines of Code or less" (hackingbuddy.ai).
- **HackerGPT** — `https://github.com/hacker-gpt/hackergpt` (98★) + hackergpt.app / HackerGPT Lite — AI OSINT + CTF companion.
- **WhiteRabbitNeo → "Deep Hat"** — app.whiterabbitneo.com + huggingface.co/WhiteRabbitNeo — Kindo's uncensored cybersecurity LLM line ("Deep Hat v2: Defense in the AI Abyss").
- **Telegram channel indexes discovered** (coverage leads, not tools): `@NinjaSecurity` (AI-security tool index), `@news4hack` ("Pentester"), `@reconshell`, `@securation` (Security Analysis), `@cvebird` (渗透/安全推送中心), `@saghebPentest`, `@securixy_kz`, `@bekzodkurbonov`; meta-list `github.com/ivolake/awesome-ai-security-tg`.

## Not found / not run / unresolved
- **X/Twitter direct search: not achievable this session** (xcancel suspended; all live nitter mirrors bot-walled or dead; x.com not indexed by Exa or Z.ai). X-sourced finds above (XBOW, ArgusRed chatter) reached me via HN/LinkedIn mirrors, not via X itself.
- **Discord: nothing verified** — disboard Cloudflare-walled from this VM (curl 403 + webReader "Just a moment…"); top.gg not attempted after that (same WAF class expected).
- **Firecrawl scrape: not run** — API key env var is a broken literal (`${FIRECRAW...}`); Exa API used instead (verified working).
- tgstat *search* and telemetr channel discovery: JS/auth-walled; channel list above came from Z.ai WebSearch + follow-links.
- `@securation` and `@cvebird` pages returned 0 bytes on scrape (rate-limited) — only handles captured.
- Unresolved names: "® MCP Server" (LinkedIn 2025-08-21), Pruthu Raut's 11-tool Pentest MCP Servers repo, Deepu A's MCP Pentest Framework repo, `dirtyfrag`'s purpose (README 404), Deadend CLI's current repo location, ninesunsinc org rename.
- Layer_8's HackerOne-#86 agent and the "8 months making LLMs hack" 29-agent system: described in HN comments but unnamed/unreleased.

## Dedup notes (map to known list — do NOT double-count)
`0xSteph/pentest-ai(-agents)` = "pentest-ai-agents (0xsteph)" · `PurpleAILAB/Decepticon` = "decepticon" · `yaklang/hack-skills` = "hack-skills" · `ktol1/RedTeam-Agent` = "ktol1/redteam-agent" · `SnailSploit/Claude-Red` = "claude-red" · `usestrix/strix` = "strix" · `elder-plinius/T3MP3ST` = "t3mp3st" · `SpecterOps/ConfigManBearPig` = "configmanbearpig" · ArgusRed ↔ "argus (ai-agent red-team)" — POSSIBLE same project (Cosine's pentest model vs an "argus" AI-agent red-team framework); flagged for dedup.
