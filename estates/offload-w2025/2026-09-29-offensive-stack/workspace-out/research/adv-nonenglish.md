---
title: adv-nonenglish
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/adv-nonenglish
---

# Adversarial hunter: non-English lanes — offensive-AI tooling haul

Angle: Chinese (先知/t00ls/看雪/freebuf/安全客/跳跳糖), Japanese, Korean, Russian, Spanish/Brazilian
security communities. Goal: offensive-AI tools absent from the known-tools list. All findings verified
live during this ask via the GitHub REST API (gh CLI, account Prekzursil) unless stated otherwise.
Star counts / push dates quoted as returned by `gh repo view` on 2026-09-29.

---

## Method

1. GitHub REST search with CJK/Cyrillic/JP/KR/ES/PT keywords (`gh api search/repositories -f q=... -f sort=stars`).
2. `chainreactors/picker` issues #1370–#1379 (Chinese "每日信息流" daily digests aggregating 先知社区, 安全客,
   Seebug Paper, 跳跳糖, 奇安信攻防社区, 棱角社区) — extracted every GitHub link, verified the suspicious ones.
3. WebSearch in zh/ja/ko/ru/es/pt (t00ls, 看雪, 先知, xiaodi8, Qiita, codeby.net, Xint/DarkBERT, CAI/Alias Robotics, PT-BR pentest IA).
4. HuggingFace model page fetch (DarkBERT).
5. Every tool returned in the structured result was README-verified this session (description, language, license, last push).

### Cross-check against the known-tools list (dedup)

Matches found and therefore **excluded**: `Yean-Sec/StrikeAgent_AtkBrain-Flash` (= strikeagent atkbrain-flash),
`ok-helloworld/vibe-pentest`, `Netw0rkNoob/VulnClaw`, `zhaoxuya520/reverse-skill`, `LING71671/open-reverselab`,
`verialabs/ctf-agent`, `ktol1/RedTeam-Agent`, `S1N6H/pentest-harness`, `0xSteph/pentest-ai-agents`,
`Armur-Ai/Pentest-Swarm-AI` (English-lane, listed as none of the above but excluded as English-lane famous),
`h4ckf0r0day/obscura` (28k★ headless browser, English-lane).
**Possible duplicate flagged**: `Ed1s0nZ/CyberStrikeAI` (7096★, Go, "AI-native cybersecurity system of action") —
almost certainly the list's "cyberstrike"; not returned as a finding.
**Name collision**: `QiantangCredit/heimdall-pentest` vs list's "heimdall" — different project, flagged.

---

## LANE: Chinese (the big haul)

### Tier 1 — full autonomous pentest agents

**ARTEX** — `Autumn-27/ARTEX` — 1290★, Go + Next.js, AGPL-3.0, pushed 2026-09-29, demo artex-demo.vercel.app.
"AI 自主渗透测试系统 | 百度'agent+'攻防挑战赛冠军项目" (Baidu agent+ attack-defense challenge **champion**).
Dashboard with token spend/activity stream, session replay of tool calls, exploration graph, asset coverage
force-graph with tested-node highlighting, traffic recording, human-in-the-loop intercept/approval, agent and
LLM config panels. Structurally missed because it is only ever discussed in Chinese challenge coverage.

**AiScan-N** — `SecNN/AiScan-N` — 541★, release v3.0.3, secnn.com. Chinese AI security-ops + pentest CLI agent
(red team drills, CTF, web pentest, APK reverse analysis, lateral movement, code audit). Multi-session chat
workbench, file upload analysis of PCAP/APK/ZIP/images, dashboards. Native Windows/Linux/macOS/WSL binaries.

**XuanMu RedTeam-Agent** — `guaidao2/XuanMu-RedTeam-Agent` — 125★, Python, MIT, pushed 2026-08-09.
Chinese-localized, feature-extended red-team multi-agent platform; "Blackboard-style shared reasoning graph"
(Cairn-inspired Fact-Intent coordination), React operator console + FastAPI control plane + evidence plane
(assets, findings, attack paths, replayable timelines). Runs on Kali directly, **no Docker**.

**dhunter** — `Dest1ny-Sec/dhunter` — 63★, Go, pushed 2026-08-18. Blackboard engine + multi-worker LLM agent;
notable: **SRC acceptance gate** — confirmed findings are mechanically replayed by a validator that rejects
time-variant noise; outputs attack-chain graph (49 facts / 7 intents example) + Markdown report.

**AegisX** — `238469/AegisX` — 21★, LangGraph + LLM multi-agent web-pentest system with feedback-driven
strategy evolution. Small but on-thesis (Chinese LangGraph security lineage).

### Tier 1 — post-exploitation / C2 with AI

**Oktos** — `1y0n/oktos` — 179★, pushed 2026-09-25, XRED.TEAM. Red-team post-exploitation platform:
BOF dynamic loading, multi-channel async comms, memory evasion, payload builder (Windows x86/amd64 shellcode,
Linux amd64, .NET webshell, DLL side-loading), and a built-in **AI assistant for post-exploitation
orchestration — MCP support added in v0.1.3**. Author states the whole platform is "vibe coded" (no human
lines). Authorized-use notice in README.

**WolfShell** — `0x7556/wolfshell` — 276★, ASP.NET, MIT, pushed 2026-08-16. "首款支持AI渗透的高级WebShell &
C2管理工具" — first AI-pentest-capable webshell/C2 manager for ASPX: natural language to webshell command,
built-in **WebShell MCP server**, AES-random-key comms, in-memory tool loading, fileless execution, intranet
webshell cascading without proxies. README in zh/en/**ru** (triple language).

### Tier 1 — MCP toolchains / skills / knowledge bases

**SecSkills** — `DaoYiSec/SecSkills` — 1093★, Apache-2.0, pushed 2026-09-14. Catalog of 102 curated Chinese
security Agents, Skills and MCP servers (46 agents, code-audit 12, pentest 16, JS-reverse 2, 域渗透
(AD pentest), WeChat-miniprogram audit, CTF…). The single best map of the Chinese agent-security lane.

**AboutSecurity** — `wgpsec/AboutSecurity` — 1767★. Pentest knowledge base "以 AI Agent 可执行的格式沉淀安全
方法论" (methodology precipitated in AI-Agent-executable format) — from the wgpsec org (authors of the
known cloudsword). Feed-ready knowledge for agent harnesses.

**AICryptoProxy** — `hzhsec/AICryptoProxy` — 51★, Python 3.12+, pushed 2026-06-02, MIT. Claude Code + MCP
framework that **auto-reverses frontend-encrypted web app traffic**: AI locates the crypto logic via MCP
browser debugging, then emits a production mitmproxy encrypt/decrypt script (direct-crypto or JSRPC bridge
mode for dynamic keys) so Burp operates in plaintext. Closes a real capability gap (hours of JS RE → ~seconds).

**REx-skill** — `tihanyin/REx-skill` — 98★, Python, MIT, pushed 2026-09-23. "Agentic Reverse Engineering
eXecution Skill for binary vulnerability discovery": **seven subagents + one evidence tree**, pinned toolchain
(Ghidra, r2, rizin, QEMU-user, angr, z3, AFL++, valgrind, capa, Unicorn, Triton, Frida, semgrep) reproducible
via Nix flake; Claude Code skill format; Linux x86_64/aarch64. Surfaced via the Chinese picker digest.

**apk-reverse** — `newliver666/apk-reverse` — 3006★, Python, pushed 2026-09-24. Agent Skill (SKILL.md
"procedure with gates") for Android APK RE: debloating, ad removal, **surgical dex patching**, repacking,
runtime/server analysis; bilingual EN/zh. High-star and invisible to English lanes.

**hello_js_reverse_skill** — `WhiteNightShadow/hello_js_reverse_skill` — 1301★. AI-powered JS reverse-engineering
skill: crypto restoration, obfuscation analysis, dynamic cookie, WASM RE, protocol adversarial work; Node.js
algorithm restoration + simulated requests; Claude Code-compatible.

**aimy-skill** — `Prohao42/aimy-skill` — 242★, Python, MIT, pushed 2026-09-28. Lightweight embeddable
pentest recon + basic vuln-probe skill for AI agents (callable from LangChain/AutoGPT or standalone CLI).

**FofaMap** — `asaotomo/FofaMap` — 733★, Python, Apache-2.0, pushed 2026-08-16. Evidence-driven FOFA
asset-mapping agent: natural-language recon decomposed into FOFA queries with **AI self-reflection on real
hits**, CLI / MCP 2.0 (15 tools) / Skill / OpenAPI 3.1 entrypoints, Nuclei scanning only behind a one-time
human approval gate. Windows/macOS/Linux.

**zoomeye MCP** — `zoomeye-ai/mcp_zoomeye` — 82★, Python, pushed 2026-09-09. Official ZoomEye MCP server
(Know Chuangyu network-asset queries for LLMs).

**ARL-Next** — `owl234/ARL-Next` — 447★, Python, pushed 2026-09-29. Modern rebuild of the classic ARL (灯塔)
asset-lighthouse: asset correlation, async scheduling, **native MCP protocol integration**, dockerized.

**Scan-Spring-GO (SSP)** — `sspsec/Scan-Spring-GO` — 308★, Go, MIT, pushed 2026-08-29. Spring-framework
scanner, 17 exploit modules (Spring4Shell, Cloud Function SpEL, Gateway SpEL, 2025-41242/41243 …) +
actuator/swagger/druid leak probing, **MCP server** exposing Detect/Exploit to AI clients with `--scope`
whitelist, exploit kill-switch and full audit logs; v2.x refactored end-to-end by AI.

**ProcMon-MCP** — `0xhackerfren/ProcMon-MCP` — 82★, Python, MIT, pip `procmon-mcp`. MCP server giving AI
agents deep Windows internals visibility: 18 tools over live process state, **kernel ETW traces**, event logs,
services, drivers, minifilters, static PE analysis; admin-required, no guardrails. Windows-native — directly
relevant to this VM estate.

**wmpf-mcp-bridge** — `an7ln/wmpf-mcp-bridge` — 122★, TypeScript, MIT, pushed 2026-07-18. Local streamable-HTTP
MCP server wrapping WMPFDebugger's Chrome DevTools Protocol websocket so Codex/Cursor/VS Code agents can
safely assess **WeChat mini-programs** (local-only bind, token auth, dangerous-action confirm gates).

**ez-xbow-platform-mcp** — `m-sec-org/ez-xbow-platform-mcp` — 93★, Go, GPLv3. MCP server for an AI-driven
pentest **competition platform** — full API surface so LLMs autonomously play CTF challenges (XBOW-style).

### Tier 1 — knowledge/LLM artifacts

**SecGPT** — `Clouditera/SecGPT` — 3109★. First open-source cybersecurity LLM (云起无垠, 2023), V2.0 2025-04;
SecGPT-Mini runs on CPU. Vuln analysis, log/traffic trace-back, attack-chain reasoning, command parsing —
a Chinese-language security-tuned model for offline ops.

**CyberKimi benchmarks (evidence repo)** — `huoji120/cyberkimi-benchmarks` — pushed 2026-09-22. Public evidence
for "CyberKimi" = **Kimi K3 with the refusal layer ablated + cyber tuning, self-hosted GPUs** (adverserial.ai):
CyberGym 78/90 crash-repro (86.7%), ExploitBench CVE-2024-6100 **16/16 unassisted** (stock K3: 4/16) with full
transcripts/tool-call logs. Not a tool — an artifact proving an ablated Chinese cyber model exists and scores.

**Kimi-break** — `YD-233/kimi-break` — 137★. Kimi Code pentest-jailbreak system prompts (AI red-team research).

**ai-redteam-notes** — `zzqsec/ai-redteam-notes` — 66★. AI-generated red-team evasion knowledge base (免杀).

### Tier 2 — Chinese long tail (verified, smaller)

`wr0x00/Lsploit` 139★ (asset + vuln-scan framework with embedded AI exp/poc assembly, Django+Docker);
`hnking-star/FlySecAgent` 122★ (LLM+MCP security assistant); `Kxiandaoyan/github-C2` 64★ (web console + Rust
agent, Cloudflare Worker main channel, GitHub-issue fallback, MCP AI hook); `SeaC-25/Kali-Security-MCP` 80★
(vector-KB + web-search LLM multi-agent pentest); `0x7556/kali_mcp` 66★ (Kali AI pentest MCP tools);
`0x7556/webshell` 27★ (AI one-click evasion webshell variants: Godzilla/Behinder/Chopper); `k8gege/ChatLadon`
62★ (Ladon pentest robot, NL→GetShell, Ladon MCP server, Kali); `MingyiSecLab/Atlas` 29★ (Electron local AI
agent desktop with pentest visual workflow + Kali sandbox + multi-provider routing, alpha); `QiantangCredit/
heimdall-pentest` 99★ (autonomous CTF/labs agent, TS); `ctkqiang/NezhaSec` 4★ (DeepSeek function-calling red
team TUI driving nmap/sqlmap/nuclei/ffuf); `Mr-xn/dsh2shell` (unauth RCE PoC against exposed DeepSeek Harness
web instances — AI-infra exploitation); `bai-yi-meng/AegisAI`, `GeekShuo/pentest_llm`,
`blkheadfish/AuroraRecon`, `hauyer/VulnAgent`, `What-canIsay/VeriAudit` (LLM multi-agent audit/verify),
`pant0m/phantom-audit` 14★ (AI code-audit skill pack), `THATYEAR/Artificer` (LLM vuln-intel → auto POC/EXP),
`gatsby-sec/llm-sec-range` 30★ (LLM pentest range: prompt-injection CTF / vulnerable Agent), `ALKAERR/
Kali_Hack_Agent` 89★ (3-layer agent for Kali containers).

### Chinese context (no repo, community intel)

- 看雪 (kanxue) 2026-07-06: "[原创]用AI写了一套IoT固件扫描审计系统IFDA" → became `cn0xroot/IFDA` (69★, Go,
  bilingual web UI, automated IoT firmware RE + vuln discovery, pushed 2026-09-21).
- 小迪安全 (xiaodi8, 2026-09-19) sells "AI渗透测试蜂群项目 / Skill 渗透评估 / Agent架构自动渗透" course tracks —
  Chinese training ecosystem consolidating around agent pentest skills.
- Tencent Cloud dev article "RedAmon：AI 驱动自动化红队框架架构解析" introduced `samugit83/redamon` (below) to
  the Chinese audience.
- t00ls: login-gated; search-indexed threads on AI 自动渗透 exist but tool shares could not be pulled this
  session (not run against the forum itself).

---

## LANE: Spanish (the second-biggest haul)

**RedAmon** — `samugit83/redamon` — 2807★, Python, MIT, v6.21.0, pushed 2026-09-29, redamon.org, Trendshift
badge, Discord + Telegram communities. "AI-powered agentic red team framework … reconnaissance → exploitation →
post-exploitation with zero human intervention", then triages findings, writes code fixes and **opens pull
requests** on the target repo. Full Docker Compose stack: webapp, postgres, **neo4j attack graph**, agent,
kali-sandbox, recon-orchestrator, docker-broker (filtering Docker-socket proxy); optional OpenVAS/GVM
(~170K NVTs); deployment sizing documented (~70 GB base / ~95 GB with GVM). Explicit Windows install path:
Docker Desktop with WSL2 backend, clone inside the WSL2 filesystem. Found via the Chinese Tencent Cloud article;
author `samugit83` (locale not published).

**CAI (Cybersecurity AI)** — `aliasrobotics/cai` — 9839★, Python, **archived 2026-08-22**. The framework behind
18 papers and 30+ CVEs (per SecSkills catalog note); Spanish company Alias Robotics (Zaragoza) with an active
Spanish-language talk/community circuit ("Automatiza tu pentesting con IA" – Luis Javier Navarrete). English-lane
famous but absent from the known list entirely. Docker/pip.

**CrystalPotato** — `ricardojoserf/CrystalPotato` — 125★, Crystal, pushed 2026-08-22. GodPotato port (SeImpersonatePrivilege
abuse) with indirect syscalls, dynamic API resolution, compile-time string obfuscation. Author is Spanish
(location: Spain on GitHub profile), tooling spread through the Spanish community. Non-AI offensive tooling —
adjacent find.

---

## LANE: Brazilian / Portuguese

**Xalgorix** — `xalgorix/xalgorix` — 1143★, Go 1.24+ + TypeScript, Apache-2.0, active releases (v4.6.x),
docs.xalgorix.com. Surfaced by a Portuguese-language query ("ferramentas pentest IA agente autônomo …
brasileiro"). "Autonomous LLM agent works a full pentest methodology, then an **independent verifier
re-exploits every finding** before it's reported — proof, not a pile of maybes." Self-hosted, bring-your-own-LLM;
Platform badge: Linux (Docker).

No other Brazilian-authored offensive-AI repo surfaced above threshold; BR community presence is mostly
curation/OSINT tooling.

---

## LANE: Korean

**OWASP Noir** — `owasp-noir/noir` — 1439★, Crystal. Hybrid static + **AI-driven** endpoint/attack-surface
detector ("Hunt every Endpoint … expose Shadow APIs") by hahwul (Korean; ex-ZAP community). Medium: OWASP
visibility means partial English-lane exposure, but absent from the list.

**DarkBERT** — `s2w-ai/DarkBERT` (HuggingFace, verified 2026-09-29). RoBERTa pretrained on Dark Web corpora
(Korean firm S2W + KAIST, ACL 2023). **Gated with manual review**: institutional email, usage purpose, ACM
ethics, CC BY-NC 4.0, research only. Value for the estate: darkweb-text classification/ransomware-family
recognition — complements the darkweb search tooling already in the list.

**Xint (씬트)** — closed Korean AI vuln-detection platform (xint.io/ko) claiming 모의해킹-grade (pentest-grade)
automated diagnosis. Product, not OSS — context only.

## LANE: Japanese

Thin on GitHub. `gmo-ierae/ierae-ctf` (9★, GMO Cybersecurity by Ierae's IERAE CTF challenge archive) is the
main artifact; Qiita (2026-05) surveys "39+ OSS autonomous pentest agents" but all named examples are
English-lane projects (PentestGPT etc.). Japanese offensive-AI activity is blog/CTF-writeup-shaped, not
repo-shaped. No Japanese repo made the findings cut.

## LANE: Russian

codeby.net thread "Агентный пентест: обзор ИИ-инструментов 2026" (fetched; thread body is login-gated, only a
summary was reachable: compares LLM assistants ChatGPT/HackerGPT and self-hosted multi-LLM stacks — nothing
new beyond the list). `boumer7/bombshot` 21★ is SMS-attack simulation, marginal and abuse-prone — noted, not
recommended. Habr itself had no dedicated LLM-pentest-agent tooling article in reachable results. The Russian
lane yielded no verifiable offensive-AI tool absent from the list — reported as a negative result.

---

## Every query tried (this session)

GitHub API (gh, authed): `渗透测试 AI agent`; `大模型 渗透`; `漏洞挖掘 大模型`; `红队 AI`; `AI 免杀`;
`渗透 MCP`; `AegisX 渗透`; `AI 逆向`; `CTF agent AI`; `fofa mcp`; `quake mcp`; `zoomeye mcp`; `hunter mcp 鹰图`;
`安全大模型`; `codeby`; `Xalgorix`; `HackerGPT`; `RedAmon`; `IFDA firmware`; `ペネトレーションテスト AI`;
`セキュリティ AI エージェント CTF`; `ペネスト AI`; `脆弱性診断 AI`; `ハッキング AI`; `CTF 自動`; `ペネスト`;
`侵入テスト`; `해킹 AI`; `취약점 AI agent`; `보안 AI agent`; `пентест нейросеть`; `хакер AI agent`; `пентест`;
`уязвимости нейросеть`; `багбаунти`; `pentest IA agente`; `pentest IA brasileiro`; `pentesting IA agente`.
Issue search: `repo:chainreactors/picker AI 智能体 OR 大模型 OR LLM is:issue`; picker issues #1370/#1373/#1375/#1377/#1379
GitHub-link extraction. Org/user listings: `GMO-Cybersecurity-by-Ierae` (404 → `gmo-ierae`), `flattsecurity` (404),
`team-enu` (empty), `hahwul` repos, users `samugit83/cn0xroot/tihanyin/ricardojoserf/xalgorix`.
README verifications: ARTEX, AiScan-N, oktos, Lsploit, XuanMu, AIPentestKit, RedScope-AI, KubeTrail, AITTAK,
dhunter, ChatLadon, AICryptoProxy, SecSkills, Scan-Spring-GO, wolfshell, wmpf-mcp-bridge, FofaMap, apk-reverse,
redamon, Xalgorix, SecGPT, REx-skill, IFDA, Atlas, CyberKimi, ProcMon-MCP, CrystalPotato metadata.
WebSearch: t00ls AI 自动渗透; 看雪 大模型 逆向; 先知社区 大模型 红队 agent; freebuf AI 渗透 agent 盘点;
AI 自动化渗透测试 工具 开源 github; Japanese pentest AI OSS; Korean AI 모의해킹/DarkBERT; habr агент пентест LLM;
Spanish agente IA pentesting; PT-BR ferramentas pentest IA. WebFetch: huggingface.co/s2w-ai/DarkBERT.
Bash curl codeby.net thread (87609 bytes fetched; thread body login-gated, no useful tool links extracted).

## Not reachable / not run

- t00ls.com and full 奇安信攻防社区 / 先知社区 post bodies: login-gated; only search-index summaries read.
- codeby.net thread body: login-gated.
- Japanese `flattsecurity` / `GMO-Cybersecurity-by-Ierae` orgs under those exact names: 404 (orgs renamed or
  private); `gmo-ierae` listed instead.
- No check was run against live targets of any kind — discovery and verification only (GitHub API, web, HF).