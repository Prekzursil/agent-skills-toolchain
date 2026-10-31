---
title: c2-agentic
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/c2-agentic
---

# Research: c2-agentic — Mythic LLM agents, Sliver/Havoc MCP, agentic C2, post-CALDERA

Date: 2026-09-29. Researcher lane: c2-agentic.
Estate context (from ask): CyberStrike 1.1.16 + MCP gateway 127.0.0.1:31100 (43 backends, 17 live incl. caldera rpc), Decepticon local+upstream (LangGraph), PentAGI staged docker-pending, Ollama qwen3:4b, Windows Server VM, **NO Docker engine** (GCP, no VT-x). Scoring axis = can it run natively on this Windows VM without Docker.

Raw evidence preserved in `out/research/scratch/`: exa_*.json (17 searches), fc_q1_*.json (firecrawl dead-end bodies), gh_*.json (sweep pages), repo_*.json (per-repo metadata for ~60 repos), readme_*.md (14 READMEs), sliver_MCP.md + sliver_agentic_loop.md (from BishopFox/sliver tree), vectra_mcp_swarm.html, arxiv_15998.xml, ddg_nonen.txt, ddg_reddit.txt, meta_batch1.txt / meta_batch2.txt. The prior live-appended query log (26 `GH-*` blocks with per-query totals and item lists) is superseded by this file but its raw gh item dumps remain in scratch/.

---

## 1. COMPLETE QUERY LOG (everything issued this session)

### Discovery backends
- **Exa** (`POST https://api.exa.ai/search`, header x-api-key, numResults 6–10) — 17 productive queries:
  1. "Mythic C2 LLM-generated disposable agents SpecterOps demo" → SpecterOps blog 2026-06-24, purpleshift writeups, mythic_ornn
  2. "Sliver C2 MCP server Model Context Protocol wrapper" → sliver.sh/docs MCP, v0idravl, x746b, schwarztim, PR2282, DeepWiki
  3. "Havoc C2 framework MCP integration LLM agent" → sec-havoc-c2-mcp, AdaptixC2 MCP servers, arXiv 2511.15998, Invoke-RE/Havoc
  4. "agentic C2 framework LLM autonomous post-exploitation" → RedTeamLLM, Erebus→ARK, endgame, Spectre, argus-lite
  5. "autonomous red team agent framework alternative to MITRE Caldera" → Gideon, Decepticon, Z3r0, T3MP3ST, autoredteam.com, symbi-redteam, seed_and_vine
  6. "MCP server for red team operations command and control" → canstralian, ktol1, kali-mcp, mergen-mcp, RedHands, MetasploitMCP
  7. "BloodHound MCP server attack paths AI agent" → mwnickerson, MorDavid, SpecterOps BloodHound-MCP blog 2025-06-04, pathhound, AgentHound, bhe_mcp
  8. "Havoc C2 successor maintained fork 2026" → Red-Cell-C2, TinyC2, khaos-c2, Havoc Pro Leviathan, Invoke-RE/Havoc, OctoC2, Phantom
  9. "Mythic MCP server 150 tools wrapper" → nbaertsch/Mythic-MCP, kyawthiha7/mythic-mcp, pkg.go.dev pages
  10. "MCP coordinated swarm agents command and controlVectra" → vectra.ai swarm-C2 blog
  11–14. convergence round ("mythic c2 mcp"; "sliver mcp agent"; "agentic c2"; "havoc extension llm") → stackviolator/mythic_mcp (tiny), **MythicAgents/sliver**, agentc2.ai (commercial; site 522 when fetched)
  15–17. final round ("c2 m2 server"→ "c2 mcp server"; "llm red team operator c2"; "disposable mythic agent generator") → dmcxblue/Claude-C2, Lune(404), otherwise only recorded names + out-of-domain LLM-safety repos
- **Firecrawl** (`POST https://api.firecrawl.dev/v1/search`, Bearer) — **DEAD END**: env FIRECRAWL_API_KEY (20 chars) rejected on all 6 queries with `{"success":false,"error":"Unauthorized: Invalid token"}` (bodies saved fc_q1_1..6.json). The env token is evidently an estate-gateway token, not a direct api.firecrawl.dev key. Worked around via Exa/DDG/WebFetch/gh. Local gateway probe `curl -o /dev/null -w %{http_code} http://127.0.0.1:31100/` → 404 (no plain HTTP passthrough).
- **DDG (keyless, `C:/Python314/python.exe -c "from ddgs import DDGS..."`)** — 7 queries:
  - non-EN ×4: `Mythic C2 LLM 生成代理 红队` (→ Mythic-zh, CSDN agent-dev guide, cn-sec coverage of the SpecterOps post, echidna, yashomer1994 AI-red-team-lab-3); `C2 MCPサーバー レッドチーム エージェント` (→ **Vectra JP swarm-C2 blog**, RedTeamMCP/RedTeam-MCP, mcpmarket SliverC2); `C2 프레임워크 LLM 에이전트 레드팀` (→ kitploit LazyOwn, koreanssam/vibehacking); `Sliver MCP server red team` (→ 0xhackerfren/sliver-mcp [now 404], mcpworld/lobehub listings)
  - reddit ×3 (`site:reddit.com mythic c2 llm agents` / `sliver mcp` / `agentic c2 framework`): classic threads only, nothing new.
- **HN Algolia** ×9 ("Mythic MCP", "Sliver MCP", "agentic C2", "T3MP3ST", "Havoc C2", "disposable tooling mythic", "red team agent", "SquidC5", "Havoc Leviathan"): near-zero yield (T3MP3ST 1pt 2026-07-05; rest off-topic). HN does not cover this niche.
- **arXiv API**: `id_list=2511.15998` (abstract read, saved); search `all:"agentic red teaming" AND all:C2` (0 hits). Related surfaced via exa: 2505.06913 RedTeamLLM.
- **WebFetch**: SpecterOps blog 2026-06-24 (full read); sliver.sh/docs?name=MCP (JS-rendered empty → read raw MCP.md from repo instead).
- **Vendor blogs read in full/part**: specterops.io ×2 (Mythic-LLM 2026-06-24; BloodHound-MCP 2025-06-04), vectra.ai MCP-swarm C2 (full HTML), infinitycurve.org Havoc Pro (title via search only).

### GitHub sweep (`gh api -X GET search/repositories`, per_page=100, pages followed while 100/page up to p3)
- **Batch A** (16 templates): `sliver mcp in:name,description,readme` (total 549, 3 pages), `havoc mcp in:...` (322), `mythic mcp in:...` (537), `metasploit mcp in:...` (1361, p3 rate-limited), `bloodhound mcp in:...` (659), `topic:mcp-server c2` (8), `topic:command-and-control llm` (2), `agentic red team` (1595), `autonomous pentest agent` (228), `pentest mcp server` (168), `llm c2 framework` (12), `adversary emulation agent llm` (0), `red team agent created:>2026-04-01` (1253), `mcp c2 created:>2026-04-01` (43), `caldera llm plugin` (2), `disposable agents c2` (0)
- **Batch B** (10): `bloodhound mcp in:...` (659), `topic:mcp-server c2` (8), `topic:command-and-control llm` (2), `topic:offensive-security topic:agent` (15), `topic:red-team sort:updated` (3709), `pentest agent stars:1..50 created:>2026-01-01 sort:updated` (317), `mcp server exploit stars:>20` (10), `mythic agent llm` (8), `sliver py` (6), `adaptix mcp` (5)
- **Batch C** (6): `beacon llm in:...` (5864, mostly noise; +Ankou, LitterBox, pentest-ai-agents), `implant llm generate in:name,description` (0), `topic:ai-c2` (0), `topic:c2-framework created:>2025-06-01` (84 → Ankou, PULSE-C2, khaos-c2, stratum-c2, Iris, BlackBerryC2, ICMP-Ghost, SmuggleMyPayload), `mythic agent in:name created:>2025-01-01` (11), `reddit agentic c2 sliver mythic` (0)
- **Final**: `red team mcp created:>2026-06-01` (30 — mostly LLM-safety-MCP, out of domain)
- **Lookup searches**: `AdaptixC2 in:name`, `hackingBuddyGPT`, `awesome red teaming in:name`, `CyberStrike in:name offensive`, `cyberstrike offensive security harness`, `havoc in:name c2`, `users/v0idravl/repos` (404)
- **Per-repo metadata** (`gh api repos/X`) for 60+ repos → scratch/repo_*.json + meta_batch1.txt/meta_batch2.txt (incl. BishopFox/sliver, its-a-feature/Mythic, HavocFramework/Havoc, Adaptix-Framework/AdaptixC2, CyberStrikeus/CyberStrike, vxcontrol/pentagi, ipa-lab/hackingBuddyGPT, all C2/MCP/agentic candidates)
- **READMEs fetched raw**: MythicAgents/sage (925 ln), n0qword/mythic_ornn, 0xrdi/echidna, x746b/sliver-mcp, schwarztim/sec-sliver-c2-mcp, SquidSec/SquidC5, r74tech/virga, RedTeamOperations/RedBeacon-AI, mitre/mcp, elder-plinius/T3MP3ST, Red-Hex-Consulting/Ankou, hrabanazviking/Mythic_Agent_Coder_CLI (name-collision decoy), 3mrgnc3/pi-mythicC2-mcp, MythicAgents/sliver
- **BishopFox/sliver internals**: `search/code repo:BishopFox/sliver mcp in:path` → `client/mcp/{mcp,server,auth,config,filesystem,log}.go`, `client/command/mcp/*`, `docs/.../MCP.md`; `contents/docs/sliver-ai-agentic-loop.md`; `pulls/2282` (closed, NOT merged); `releases/latest` (v1.7.7 asset list); `releases` of AdaptixC2 (empty `[]`)
- **Awesome-lists walked** (readme + grep for c2/mythic/sliver/havoc/caldera/llm): sbilly/awesome-security (stale for niche), yeyintminthuhtut/Awesome-Red-Teaming (classic links only), corca-ai/awesome-llm-security (papers only), punkpeye/awesome-mcp-servers (1812 lines, **zero offensive/C2 entries**). Finding: the LLM-C2 wave is NOT on the awesome lists yet; GitHub search + vendor blogs are the live sources.

---

## 2. FINDINGS BY CLUSTER

### 2.1 The SpecterOps demo (ask anchor) — fully mapped
- **Blog**: "Disposable Tooling: Building LLM-Generated Mythic Agents From Prompt to Deployment", Adam Chester (@xpn), SpecterOps TRACE, 2026-06-24 (read via WebFetch). Prompt→tested-implant pipeline with no human between spec and shippable Stage-0 agent (ls, cd, pwd, shell, upload/download, execute, stage). Key components: Anthropic Skill "mythic-implant-development" (Mythic docs as offline reference), "Oracle" 3-tier test harness (T1 unit/protocol vs mock Mythic; T2 debug build on live Ubuntu Mythic tested against a Windows 11 VM; T3 clean-context QA sub-agent returning PASS/FAIL), LabKit (Go gRPC exec + Windows stdout/stderr capture), mythic-cli API wrapper, Mythicd container wrapper. GPT-5.5-Cyber-Preview built working agents in Python/Go/Zig/C#/Rust at ~1.5–2 h each. **Public POC: github.com/specterops/kraken** (macOS Swift agent w/ Apple Containerization; s:23, pushed 2026-03-13; macOS-target → low value here).
- **n0qword/mythic_ornn** (s:54, pushed 2026-08-24): the open-source implementation of that idea — LLM-driven generator for Mythic Agents/Payload-Types/C2-Profiles. Prompt mode (`template/AGENT.md` — turn ANY coding agent into a Mythic dev; **no Docker required to scaffold**) + Build mode (`ornn-agent/` payload-type generating agents from the Mythic UI; Docker+Mythic required). Credits @xpn explicitly.
- **MythicAgents/sage** (s:28, pushed 2026-08-26, Python, GPL-3.0): "AI operator that lives inside your C2" — LangGraph Supervisor + 6 specialist agents; installs INTO Mythic ≥ v4.0.0rc5 (native chat containers) via `sudo ./mythic-cli install github https://github.com/MythicAgents/sage`; reads live callbacks/tasks/creds/files + BloodHound graph; engagement ledger with proof-gated verification (LLM+P / LLM-Modulo inspired); autonomous GOAD solve demo; modes conversation (read-only) / supervised (approve-per-action) / auto; providers openai/bedrock/anthropic/**ollama** + any OpenAI-compatible `API_ENDPOINT`; "Connecting other MCP servers" section → could sit behind the estate gateway. Docker-gated (Mythic itself).
- **0xrdi/echidna** (s:5, pushed 2026-08-25, MIT): virtual LLM agent for Mythic — instant AI callbacks in Mythic UI (no target host), 13 skill agents (recon→exfil), `campaign --auto` chaining with approval gates, providers incl. Kimi (Anthropic-protocol) and custom OpenAI-compatible. `mythic-cli install github https://github.com/0xrdi/echidna.git` + docker compose.
- **MythicAgents/sliver** (s:49, pushed 2024-11-18): Mythic payloads `sliverapi`+`sliverimplant` that bridge a Sliver server and its implants INTO Mythic as callbacks (operator cfg is the build param). Stale but the exact Sliver↔Mythic bridge pattern.
- Mythic MCP wrappers: **nbaertsch/Mythic-MCP** (Go, s:7, ~150 Mythic tools, docker container :3333/mcp streamable-HTTP; driven by 3mrgnc3/pi-mythicC2-mcp which auto-manages its container lifecycle), kyawthiha7/mythic-mcp (s:0), stackviolator/mythic_mcp (s:0), johanrobbenites/MCP-IA-for-Offensive-Security (s:0), Yaman-RedTeam/mcp-mythic-c2 (s:0), SkinwalkerSec/AI-Tooling (s:2; Mythic+BloodHound+nmap MCP servers + practice labs). All Docker-gated via Mythic.
- Mythic base: **its-a-feature/Mythic** s:4797, pushed 2026-09-27 (active). Docker-compose only → not runnable on this VM.

### 2.2 Sliver: NATIVE MCP in mainline — highest estate fit
- **BishopFox/sliver** s:11928, pushed 2026-09-26; latest release **v1.7.7 (2026-09-03)**. Verified in tree: `client/mcp/` + `client/command/mcp/` + `docs/sliver-docs/pages/docs/md/MCP.md` (fetched as scratch/sliver_MCP.md).
  - **MCP.md (read)**: experimental; two transports — **stdio** via `sliver-client mcp --config <multiplayer.cfg>` (recommended w/ Multiplayer Mode) and **HTTP/SSE** via `mcp` / `mcp start --transport http` from client OR server console (binds 127.0.0.1:8080; auto-generates 128-bit token → `~/.sliver-client/mcp.yaml`; every request needs `Authorization` header). Example console shows Server v1.6.4-era. Client config examples given for Codex (`[mcp_servers.sliver]`) and Claude Code (`claude mcp add sliver -- ...`).
  - PR #2282 "add AI Agent integration with MCP Server and CLI structured output" (20+ tools) by lxcxjxhx: **closed, not merged** — in-tree MCP landed separately (landing PR not pinned; not further chased).
  - `docs/sliver-ai-agentic-loop.md` (read): plan to port the Codex-rs agentic-loop (Responses API turn/item lifecycle, persisted reasoning + tool-call items kept out of context window) into Sliver's AI chat → Sliver is actively becoming an agentic C2 itself.
  - **Windows-native**: v1.7.7 assets include `sliver-server_windows-amd64.exe` and `sliver-client_windows-amd64.exe` (+386/arm64) — verified from releases/latest. No Docker needed. The estate MCP gateway can consume the HTTP/SSE MCP endpoint directly.
- Wrappers (all Python/Node → Windows-native via pip/npm/uv):
  - **x746b/sliver-mcp** (s:5, pushed 2026-04-23): ~74 tools — exec, armory (aliases + BOFs via coff-loader), listeners, implant generation, identity, recon, registry, services, websites, intel; README states it "complements the official fs-only MCP". Install: `git clone` → `uv venv` → `uv pip install -e .` → `uv run sliver-mcp --operator-config ~/.sliver-client/configs/<op>.cfg` (Python ≥3.11). Same author ships an EDR-resilient Windows loader for Sliver shellcode (VS2022-native build).
  - **schwarztim/sec-sliver-c2-mcp** (s:6, pushed 2026-09-09, MIT): Node MCP driving sliver-py; `npm install && npm run build`; `node dist/index.js --operator-config <cfg> --python <py>`; PYTHON_PATH env. (Same author's sec-havoc-c2-mcp is archived — see 2.3.)
  - **d4vydm/sliverc2_mcp** (s:3, 2025-05-20, Python/MIT).
  - **v0idravl/sliver-mcp**: repo+user GONE (404); orphaned PyPI `sliver-mcp` 1.0.1 (no project URLs; summary "MCP server for Sliver C2 — AI agent automation for post-exploitation"; requires-python ≥3.10). Dead end.
  - 0xhackerfren/sliver-mcp: 404. CuriousLearnerDev/Argus-Sliver (s:75; Vue3+FastAPI web console over sliver-py, CN). sliverarmory/sliver-py (s:86; gRPC client lib). puffert/kali-mcp (72 tools incl. Sliver; Kali/Linux-targeted).

### 2.3 Havoc: base archived, ecosystem moved
- **HavocFramework/Havoc s:8514, pushed 2025-12-18, ARCHIVED** (verified). Continuations: Invoke-RE/Havoc (s:0, pushed 2026-01-09); commercial **Havoc Professional 0.8 "Leviathan"** (infinitycurve.org; not OSS). Docs live at havocframework-havoc.mintlify.app (extensibility: custom agents, external C2, Python API).
- **schwarztim/sec-havoc-c2-mcp (s:6, MIT) ARCHIVED** — the only dedicated Havoc MCP found; dead end.
- Build path (make + mingw on Linux) → on this VM: Docker/WSL only. Havoc = low priority for a no-Docker Windows estate.

### 2.4 Agentic C2 frameworks newer than CALDERA
- **SquidSec/SquidC5** (s:57, pushed 2026-09-25, Python 3.11+, MIT): security-first **AI-native "C5" teamserver** (Command·Control·Cognitive·Collaborative·Coordination). INKO neural-operator chat + sandboxed Admin AI with railed tools + HITL, built-in scoped **MCP off by default**, **optional local Ollama**, Go implant factory (`sc5 implants build` / POST /api/v1/implants/build; sc5beacon: AEAD, sleep/jitter/kill, SOCKS reverse-dial), malleable profiles (base64/xor/netbios transforms), OAST (DNS/HTTP/SMTP), TLS library, ROE banned-commands + end time, immutable audit hash chain (`sc5 audit-verify`), multi-op collaboration. Release **v0.1.319-134e405 (2026-09-25) ships `squidc5-windows-x64.exe` + `sc5-windows-x64.exe`** (verified). Local install `python -m venv` + `pip install -r requirements-dev.txt && pip install -e .` → `squidc5`. Windows-native ✔, pairs with estate Ollama.
- **elder-plinius/T3MP3ST** (s:6277, pushed 2026-09-08, TypeScript, AGPL-3.0): "autonomous red teaming platform; multi-agent offensive-security meta-harness" — bolts an arsenal onto the coding agent you already run (Claude Code, Codex, Hermes, OpenCode, Oh My Pi) or **fully offline models (Ollama/LM Studio/vLLM)**; recon→exploit→report from a browser War Room (`npm install && npm run server` → http://127.0.0.1:3333/ui/) or CLI; 90.1% pass@1 on XBOW's 104-challenge suite, all claims re-derived by `npm run verify-claims`; domain matrix: web stable, CTF stable, robotics/OT disclosure pipeline, source, smart-contracts, cloud/mobile/binary scaffolds. README line 156: **"Works on Windows (PowerShell), macOS, Linux, and WSL. Requires git and npm on your PATH."** Windows-native ✔.
- **Red-Hex-Consulting/Ankou** (s:243, pushed 2026-04-24, BSD-3): modular C2 (Go server `go run .` + Electron client `npm install && npm run electron`, 3 reference agents, JSON agent-handlers, Ghost Relay transport). AI Operations panel talks to **any OpenAI-compatible endpoint (OpenAI, LM Studio, Ollama, OpenWebUI)** — ingests full command history, summarizes, proposes click-to-run commands (`<cmdankou>`), HITL. Windows: build-from-source (Go+Node); no prebuilt Windows release verified.
- **r74tech/virga** (s:7, pushed 2026-09-14, Go, MIT): **local LLM embedded in beacon implants** for autonomous post-exploitation — LLM inside the implant (the estate's local-first direction taken to the endpoint). Build via make; mingw for Windows cross-compile.
- **KKingZero/ARK** (ex-Erebus; s:12, pushed 2026-09-14, Go): "ARK C2 by Zypheron — AI-native C2 for authorized red teaming, human-in-the-loop, modular, cross-platform".
- **endgamec2framework/endgame** (s:35, pushed 2026-09-23, C): AI-powered C2 for professional red teams.
- **RedTeamOperations/RedBeacon-AI** (s:20, 2026-06-29): LLM-powered red-team signals C2; README documents **uv install with a Windows PowerShell path** (`irm https://astral.sh/uv/install.ps1 | iex`).
- **dmcxblue/Claude-C2** (s:94, 2025-05-15): "Utilizing an MCP Server to communicate with your C2" — Claude-as-operator over MCP.
- **Adaptix-Framework/AdaptixC2** (s:3648, pushed 2026-09-24): active modular red-team toolkit; `releases` API empty (no GitHub release assets to verify Windows build); MCP wrappers: 0xb11a1/AdaptixC2_mcp (s:39, 2025-07-20), Faceless0x7/AdaptixC2-MCP-Server (s:32, pushed 2026-09-14, GPL-3.0).
- Long tail recorded (scratch/repo_*.json): DevAli00/llm-dns-C2 (DNS C2 + autonomous LLM tasking), farooq9/wraithc2 (Gist dead-drop AI post-ex), KONDORDEVSECURITYCORP/c2Telegram (LLM Telegram C2 PoC per Unit42-2026 intel), swfk2154/Stopen (OODA agent + AntSword/Behinder/Godzilla webshells + C2 + MCP bridge, CN), Joshua-Millward/Maverick (PIC C2 agents, Crystal Palace/PICO modules), 28Zaaky/PULSE-C2 (s:53, Windows agent) + khaos-c2 (s:240, cloud-trusted routing), LAME-Projects/stratum-c2 (s:42, cloud dead-drop, Rust agents, P2P), dstours/OctoC2 (s:227, GitHub-native), 0xPrimo/TinyC2 (s:54, Havoc-Pro channel-switching reimpl), phantom-offensive/Phantom, WoodenshoeNL/Red-Cell-C2 (Rust), VantIer/Irudo, grisuno/LazyOwn (s:228, "first RedTeam Framework with AI-powered C&C"), GnomeMan4201/Lune (404).
- **Commercial (not OSS)**: agentc2.ai ("Agentic C2" — docs for agents/networks/MCP API; site 522 at fetch). Havoc Professional (above).

### 2.5 Caldera's own agentic path (estate already runs caldera rpc)
- **mitre/mcp** (s:40, pushed 2026-09-03, Apache-2.0): official **Caldera plugin** — orchestrates long-running LLM workflows that auto-create adversary-emulation abilities and plan operations; optional RAG from STIX CTI. Install into EXISTING Caldera (from Caldera root): `git clone https://github.com/mitre/mcp.git plugins/mcp` → `pip install -r plugins/mcp/requirements.txt` → `python -m spacy download en_core_web_lg` → add `mcp` to `plugins:` in `conf/local.yml`; needs poppler/pdftotext for PDF intel (Windows poppler builds exist); LLM creds + Caldera connection configured in plugin. This is the cheapest "newer-than-caldera" upgrade for the estate — no new Docker.
- Zhaxstronaut/seed_and_vine (s:0, 2026-07-08): second AI adversary-emulation Caldera plugin (human-oversight focused).

### 2.6 Agentic red-team harnesses adjacent to C2 (estate-compare set)
- **CyberStrikeus/CyberStrike** s:2899, pushed 2026-09-28 — the estate's own platform upstream is ACTIVE (estate on 1.1.16; check upstream releases). Fork ecosystem exists (TiaMEOWS/mergen, s:2, 2026-09-21, "fork of CyberStrike, AGPL-3.0").
- 0xSteph/pentest-ai-agents (s:2290, Shell, MIT, 2026-08-16): Claude Code offensive-security subagents (planning, recon analysis, exploit research, detections, STIG audit, reporting).
- H-mmer/pentest-agents (s:976): 48 agents / 26 commands / 19 CLI tools / 2 MCP servers, autonomous hunt loops, exploit-chain builder — multi-CLI (Claude Code/Codex/Gemini/Cursor/Windsurf/Copilot/OpenClaw).
- Aethena-Lab/Z3r0 (s:915, 2026-09-13, Python): AI-native red-team workbench, specialist agents, sandboxed tools.
- NeoTheCapt/RedteamAgent (s:137): turns Claude Code/OpenCode/Codex into a structured red-team operator.
- GH05TCREW/MetasploitMCP (s:733): MCP over msfrpcd (Python; Windows: msfrpc needs Metasploit — friction).
- BloodHound MCPs: mwnickerson/bloodhound_mcp (s:136; the one SpecterOps blogged 2025-06-04), MorDavid/BloodHound-MCP-AI (s:377), iabdullah215/pathhound-mcp (reasoning-over-graph), err0n-0x2A/bhe_mcp (BH-Enterprise), adithyan-ak/AgentHound (s:442, pushed 2026-09-29 — attack-path reasoning over AI-agent infrastructure; docs.agenthound.io).
- Others recorded: bhavsec/autopentest-ai (s:232, agentic pentest MCP), g4sk0/mergen-mcp (s:15), canstralian/red-team-mcp, iflow-mcp/ktol1-redteam-mcp, RedTeamMCP/RedTeam-MCP (s:2), Cogensec/Gideon (s:34), ThirdKeyAI/symbi-redteam (Cedar-gated, Rust), hett-patell/ShardReaper, bulwark-sec/bulwark, Dest1ny-Sec/dhunter (s:63, CN), Tangruwo/RuwoScan (s:39, CN), kmdn-ch/phantom-ethical-redteam (archived), BlackSnufkin/LitterBox (s:1542; self-hosted payload-vs-detection sandbox w/ MCP), 26zl/cybersec-toolkit (s:65; 670 tools via Kata-sandboxed MCP — Linux-only), Chaos-Monkey-Island/Autonomous-Pen-Testing, menashe12346/Autonomous-Cyber-Attack-Agent, ipa-lab/hackingBuddyGPT (s:1248; Linux/SSH-lab oriented), vxcontrol/pentagi (s:25107 — already staged on estate), PurpleAILAB/Decepticon (already on estate).

### 2.7 "MCP as the C2 bus" — the pattern the research world is converging on
- **arXiv 2511.15998** "Hiding in the AI Traffic: Abusing MCP for LLM-Powered Agentic Red Teaming" (abstract fetched): MCP-based C2 coordinating distributed adaptive recon agents covertly; improves goal-directed behavior and **eliminates key host/network artifacts** by blending into legitimate AI traffic.
- **Vectra AI** "New Technologies Bring New Risks: MCP-Powered Swarm C2" (full HTML fetched): MCP as central nervous system for polymorphic, distributed agent swarms — parallel ops, real-time intel sharing, resilience; real-network case study incl. BYOVD EDR-evasion tasking; defensive framing, full offensive architecture.
- Sliver's in-tree MCP + agentic-loop doc, Sage behind Mythic, SquidC5's scoped MCP, Claude-C2, and the two papers above all describe the same thing the estate already has hardware for: **the MCP gateway at 127.0.0.1:31100 is a ready-made C2 coordination plane**; adding sliver-server (HTTP/SSE MCP) + SquidC5 (Windows-native, Ollama-backed) behind it reproduces the published patterns with zero Docker.

---

## 3. DEAD ENDS / NEGATIVE RESULTS (verified this session)
- Firecrawl direct API invalid token (bodies in scratch/fc_q1_*.json).
- v0idravl/sliver-mcp: repo+user gone; PyPI orphan. 0xhackerfren/sliver-mcp: 404. GnomeMan4201/Lune: 404.
- schwarztim/sec-havoc-c2-mcp archived; HavocFramework/Havoc base archived 2025-12-18 → Havoc lane effectively dead for OSS.
- adaptixserver org wrong (404) → Adaptix-Framework/AdaptixC2; its /releases is empty `[]` (no GitHub release assets; Windows binary availability unverified).
- seps/hackingBuddyGPT wrong owner → ipa-lab/hackingBuddyGPT.
- hrabanazviking/Mythic_Agent_Coder_CLI: name-collision decoy ("Mythic Engineering" coding TUI, not Mythic C2).
- agentc2.ai: Cloudflare 522 at fetch (commercial; docs visible via search index only).
- HN + the four awesome-lists: no coverage of this niche (grepped).
- X/Twitter: not searched (no API auth in env); not covered.
- Reddit (via DDG site:): classic threads only.

## 4. EXHAUSTION STATE
Cross-backend mandate met: Exa ✓ (24 queries incl. convergence rounds), Firecrawl attempted (dead key, documented, substituted), gh ✓ (33+ templates across name/topic/star/date slices, pagination to ≥3 pages on big hits, 60+ per-repo lookups, code+contents+PRs on sliver), awesome-lists ✓ (4), HN ✓ (9), DDG ✓ (7 incl. zh/ja/ko), arXiv ✓, vendor blogs ✓ (specterops, vectra, sliver.sh, infinitycurve), Reddit ✓ (DDG). The final three rounds returned only already-recorded names, out-of-domain LLM-safety repos, or 404s; the two tail finds they produced (MythicAgents/sliver, dmcxblue/Claude-C2) are recorded above. Uncovered surfaces: X real-time chatter, CN/JP forums behind DDG's reach, commercial demos behind auth — coverage of those is NOT claimed.