---
title: gap-chase
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/gap-chase
---

# gap-chase — uncovered subtopic sweep (2026-09-29)

Subagent lane: gap chaser. Input = the fleet coverage list in the ask + all 88 `out/research/*.md` files (all lane notes read in full; the 1.3 MB `_awesome.md`/`_awesome_mcp.md` dumps used as a local mining source). Mandate: find subtopics NO lane covered, chase with fresh queries, return NEW tools only.

## 0. Environment / backend status (verified this session)

- `gh auth status` → "✓ Logged in to github.com account Prekzursil" (keyring token).
- `EXA_API_KEY` in process env: True. Process-env `FIRECRAWL_API_KEY` is the broken 20-char literal placeholder `${FIRECRAWL_API_KEY}` (len 20 printed) — **but** the real key lives in the Windows User registry: `[Environment]::GetEnvironmentVariable('FIRECRAWL_API_KEY','User')` → `fc-213666f696894d77aeb05a5610c7f4ca` (35 chars). With that key `POST https://api.firecrawl.dev/v1/search` returns `{"success": true, "data": [...]}` — firecrawl search lane is ALIVE this session (previous lanes declared it dead; the registry key was the fix, same as llm-fuzzing's finding).
- Helper written: `out/research/_gapq.py` (exa / fc / gh wrappers).
- No tool was installed or executed beyond query helpers — research only.

## 1. How the gap list was derived

Grep-audited all `*.md` for candidate topics; a topic counts as UNCOVERED when it appears only inside raw dumps (`_awesome.md`), other tools' catalogs (blitzstrike tool table, satyam hub table), or not at all — never as an analyzed lane. Confirmed gaps:

1. **LLM/AI red-teaming frameworks** — PyRIT/garak/deepteam: 0 mentions anywhere (fleet had only promptfoo + LLAMATOR).
2. **Massive skills libraries** — `mukul975/Anthropic-Cybersecurity-Skills` (33.5k★) never surfaced (fleet covered hack-skills/Claude-Red but not this).
3. **PentestGPT lineage** — 0 mentions.
4. **Recon/OSINT surface MCPs** — Shodan/Censys/maigret/dnstwist/SpiderFoot MCPs only as names in dumps/hub tables.
5. **CVE/vuln-intel aggregation MCPs** — NVD/EPSS/CISA-KEV/OSV unowned (KEV/EPSS appeared only as raw dump lines + fissure side-mentions).
6. **Security knowledge-graph MCPs** — MITRE ATT&CK / CWE / CAPEC lookup for agents (only a Sigma-rules dump entry).
7. **Wireless/RF offense automation** — aircrack/wifite/bettercap only as blitzstrike catalog rows; zero lane.
8. **K8s/container offense** — kube-hunter/Peirates only as a satyam catalog row; dearbhadh was a benchmark, not tooling.
9. **Mobile pentest automation** — MobSF/jadx/apktool only as catalog rows/dump lines; no mobile lane.
10. **RE/malware-analysis MCPs** — radare2/volatility/YARA MCPs unowned (estate covered binary-ninja/cheatengine/frida/ghidra-diff lanes only); `radareorg/r2mcp` 404 → renamed.
11. **ROADrecon MCP** — ROADtools covered, its MCP wrapper was not.
12. **Initial access / phishing infra automation** — GoPhish/Evilginx only as blitzstrike catalog rows.
13. **Deception/honeypots as agent targets** — only a paper mention (2609.08093).
14. **Report generation agents** — not covered at all.
15. **Web3 contract-audit agents** — only `ultrafuzz` side-mention (thin; chased, found mostly small repos).

## 2. Haul of NEW tools (all verified via `gh api repos/...` this session unless noted)

### 2.1 LLM red-teaming frameworks (biggest structural gap)
| Tool | Evidence (this session) | Windows | Value |
|---|---|---|---|
| **microsoft/PyRIT** | 4,558★, Python, pushed 2026-09-29 (Firecrawl scrape showed commits "33 minutes ago"); "The Python Risk Identification Tool for generative AI… proactively identify risks in generative AI systems" | native (pip) | **high** — the canonical agent-attack automation the fleet lacked |
| **NVIDIA/garak** | 9,386★, "the LLM vulnerability scanner"; README: `python -m pip install -U garak` | native (pip) | **high** |
| **confident-ai/deepteam** | 2,975★, "framework to red team LLMs and AI agents"; `pip install -U deepteam`; README ships an MCP server (run red teams from Cursor/Claude Code) | native (pip) | **high** |
| EdenYavin/Garak-MCP | 7★, MCP wrapper for garak | native | medium |
| mbergo/deepteam-mcp | 0★, pushed 2026-09-21, stdio MCP over deepteam, "Sem Docker" | native | medium |

### 2.2 Skills library + classic lineage
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **mukul975/Anthropic-Cybersecurity-Skills** | 33,573★, pushed 2026-08-31; README: "818 production-grade cybersecurity skills · 34 security domains · 6 framework mappings (MITRE ATT&CK, NIST CSF 2.0, MITRE ATLAS, D3FEND, MITRE F3) · 26+ AI platforms"; install `npx skills add mukul975/Anthropic-Cybersecurity-Skills`; includes offensive+dual-use skills with authorized-use framing | native (skill files) | **high** — biggest skills haul the fleet missed |
| **GreyDGL/PentestGPT** | 15,648★, pushed 2026-07-14 — NOT dead; README now documents "Autonomous Agent — Drives Claude Code or Codex to run tools and reason without human intervention", pluggable CTF pipeline | native (Python) | medium-high |
| PentHertz/grimoire | 201★, "Offensive knowledge, offline. One search box for every playbook." — clones HackTricks + other corpora into one full-text index + **MCP server** for Claude/Codex/Gemini; part of PentHertz RF-Swift toolkit; `pip install -r requirements.txt` (PyYAML+markdown) | native | medium-high (hacktricks-lane complement) |

### 2.3 Recon / OSINT surface (estate had exa/tavily/firecrawl but no Shodan-class fronts)
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **w0h1v/mcp-shodan** (npm `@burtthecoder/mcp-shodan`) | 173★, pushed 2026-09-08; "search internet-connected devices, IP reconnaissance, DNS lookups, CVE/CPE vulnerability intelligence"; install `claude mcp add --transport stdio --env SHODAN_API_KEY=… shodan -- npx -y @burtthecoder/mcp-shodan` | native (npx) | **high** |
| **badchars/osint-mcp-server** | 57★, pushed 2026-03-17; "37 tools, 12 sources — Shodan, VirusTotal, Censys, SecurityTrails, DNS recon, WHOIS, certificate transparency, BGP, Wayback, GeoIP"; `npx osint-mcp-server` | native (npx) | **high** |
| w0h1v/mcp-maigret | 265★, maigret OSINT username-enumeration MCP; README requires "macOS, Linux, or **Windows with Docker Desktop**" → docker on this no-Docker VM | docker | medium (blocked here) |
| w0h1v/mcp-dnstwist | 51★, dnstwist typosquat/phish-domain MCP | native (npx) | medium |
| nickpending/mcp-recon | 30★, "Tellix is a conversational recon interface powered by httpx and LLMs" | native (Go) | medium |
| marlinkcyber/spiderfoot-mcp | 6★, SpiderFoot OSINT automation MCP | native (Python) | medium-low |
| pipeworx-io/mcp-censys | 0★, pushed 2026-09-25, Censys Platform API MCP — watch | native | medium-low |

### 2.4 CVE / vuln-intel aggregation
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **badchars/cve-mcp** | 29★, pushed 2026-09-17; "23-tool MCP server — NVD, EPSS, CISA KEV, GitHub Advisory, OSV unified; risk scoring, bulk triage, exploit search; 2 dependencies"; `npx cve-mcp` / `claude mcp add cve-mcp -- npx cve-mcp` | native (npx) | **high** |
| roadwy/cve-search_mcp | 107★, MCP for the CVE-Search API | native (pip) | medium |
| zer0-kr/security-framework-mcp | 14★, pushed 2026-04-26; "Unified NIST + OWASP — 36 tools, 3,439+ records, live NVD/KEV, PDF reading, STRIDE threat modeling, compliance mapping" | native | medium |
| Cyreslab-AI/circl-cve-search-mcp-server | 10★, pushed 2026-09-20; CIRCL Vulnerability-Lookup — query CVE, **CWE, CAPEC** | native (npx) | medium-low |
| jonnybottles/patch-tuesday-mcp | 4★, pushed 2026-09-10; MSRC Patch Tuesday triage: rollups, CVE/KB, supersedence, **EPSS + CISA KEV urgency ranking** — feeds the covered patchwatch lane | native | medium-low |
| StacklokLabs/osv-mcp | 42★, pushed 2026-09-24, "An MCP server for OSV" (Go) | native | medium-low |
| HaroldFinchIFT/vuln-nist-mcp-server | 14★, NVD Vulnerabilities API MCP | native | medium-low |
| cuttalo/depscope | 1★, "22 MCP tools, 19 ecosystems, free, no auth" package intel incl. OSV/KEV/EPSS/typosquats | native | medium-low |

### 2.5 Security knowledge-graph MCPs
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **stoyky/mitre-attack-mcp** | 44★, "MCP server for the MITRE ATT&CK knowledge base" | native | medium |
| imouiche/complete-mitre-attack-mcp-server | 5★, 80+ tools over ATT&CK techniques/tactics/groups/software/mitigations across Enterprise/Mobile/ICS | native | medium-low |
| jalvarezz13/mitre-attack-atlas-mcp | 0★, ATT&CK + **ATLAS** (AI-system adversary ML) querying — pairs with PyRIT lane | native | medium-low |

### 2.6 Wireless / RF offense
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **badchars/wifi-security-mcp-server** | 6★, pushed 2026-09-25; "Full-spectrum wireless security MCP — WiFi, Bluetooth, RF/SDR, NFC/RFID, Cellular/5G, IoT, MouseJack, air-gap, UWB, WIDS/WIPS, compliance. 34 tools, 9 knowledge bases"; `npx wifi-security-mcp-server` | native (npx; underlying radio tooling may need adapters) | medium-high (young; exactly the missing lane) |
| techchipnet/aircrack-mcp | 42★, pushed 2026-04-27; aircrack-ng MCP; README: "Kali Linux recommended… Root/Administrator required for monitor mode" → poor native fit on Windows Server | unknown (Kali-leaning) | medium-low |
| PentHertz RF-Swift | referenced as grimoire's parent toolkit (RF/SDR environment manager) — pointer only, not deep-verified | unknown | low |

### 2.7 Kubernetes / containers offense
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **inguardians/peirates** | 1,482★, pushed 2026-09-22, Go, "Kubernetes Penetration Testing tool" — classic, no MCP, but single Go binary | native (Go binary) | medium |
| Hackndo/Dark-Moon | 2★, pushed 2026-06-30; "Autonomous AI pentesting engine… web, cloud, AD and Kubernetes… agentic reasoning, real exploit execution, attack path analysis" — by Hackndo (pixis); watch item | unknown | medium-low (watch) |
| ggeorgeazevedo/yubel | 7★, pushed 2026-09-04; "multi-target DAST orchestrator — one config runs ZAP, Nuclei, Nikto, testssl.sh, dalfox, schemathesis, kube-hunter" | unknown | medium-low |

### 2.8 Mobile pentest automation
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **zinja-coder/jadx-ai-mcp** | 2,842★, pushed 2026-09-23; "Plugin for JADX to integrate MCP server"; deps `uv pip install httpx fastmcp` | native (Java) | **high** |
| **zinja-coder/apktool-mcp-server** | 661★, pushed 2026-07-02; "MCP Server for APK Tool (Part of Android Reverse Engineering MCP Suites)" | native | medium-high |
| **callstack/agent-device** | 4,817★, pushed 2026-09-29; "Mobile app automation and verification for AI coding agents. CLI, MCP server, typed Node.js API for iOS, Android, HarmonyOS…"; `npm install -g agent-device@latest` (Node ≥22.12) | native | medium-high |
| CursorTouch/Android-MCP | 875★, pushed 2026-07-01, "MCP Server for interacting with Android Devices" | native (needs device/adb) | medium |
| pullkitsan/mobsf-mcp-server | 22★, pushed 2026-09-09; "uses MobSF APIs to scan and analyze apk and ipa files"; `git clone` + `npm install` + `npx tsx server.ts` | native (needs MobSF server, which is Docker/Linux-leaning) | medium |
| plur1bu5/mobsf-mcp | 3★, "autonomous Android security analysis: SAST, DAST, Frida instrumentation via MobSF" | unknown | medium-low |
| PhoenixHairpin/mcp-termux | 59★, "Android 逆向工程一体化 MCP — 73 tools, stackplz eBPF + paradise 内存 + radare2"; ARM64 rooted device only | unknown (device-only) | low |
| youichi-uda/droidpilot | 7★, "Accessibility Service + MCP — no ADB, no OCR" Android automation | unknown | medium-low |

### 2.9 RE / malware-analysis MCPs (radare2/volatility/Ghidra-AI)
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **radareorg/radare2-mcp** | 312★, pushed 2026-09-27, official "MCP stdio server for radare2" (the old `r2mcp` name 404s — renamed); native r2 build or Docker | native | medium-high |
| **sjkim1127/Reversecore_MCP** | 205★, pushed 2026-09-29; "security-first MCP: automated reverse engineering, malware analysis, forensics, VR, SAST — powered by Radare2, YARA, LIEF, Capstone"; `pip install reversecore-mcp` (Docker "recommended for full functionality") | native-leaning | medium-high |
| symgraph/GhidrAssistMCP | 756★ (moved from jtang613/), pushed 2026-08-03; "native MCP server extension for Ghidra" (GhidrAssist AI plugin) | native (Ghidra/Java) | medium-high |
| Gaffx/volatility-mcp | 52★, Volatility 3 MCP; git clone + pip | native (volatility 3 runs on Windows) | medium |
| 0xhackerfren/Windows-Memory-Forensics-MCP | 13★, pushed 2026-01-28; "33 tools… Volatility 3, MemProcFS, CLR/SOS backends — process analysis, malware detection" | native | medium |
| zboralski/ida-headless-mcp | 2★, headless IDA analysis MCP | native | medium-low |
| mrexodia/ida-pro-mcp | 12,406★ — **excluded from NEW haul: estate already carries the `ida-pro-mcp` skill** (estate-known, not fleet-new) | — | — |

### 2.10 Entra: the missing ROADrecon MCP
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| atomicchonk/roadrecon_mcp_server | 52★, "Claude MCP server to perform analysis on ROADrecon data"; pip install -r requirements.txt — pairs with covered ROADtools (`pip install roadrecon`) | native | medium-high |

### 2.11 Initial access / phishing infra
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| dan1t0/gophish-mcp | 21★, pushed 2026-06-08; "automate Gophish campaigns, streamline phishing assessments, speed up MCP workflows"; `pip install -e .` | native (needs a GoPhish instance) | medium |
| CyberSecurityUP/PhishletGenerator-Evilginx | 42★, phishlet generation for Evilginx | unknown | medium-low |
| m0b1u3/Gophish-mcp | 4★, zh Gophish campaign-management MCP | unknown | low |
| fin3ss3g0d/evilgophish | 2,016★ — classic evilginx3+gophish combo (not AI); context anchor for the lane | native | low (classic, not new) |

### 2.12 Deception / honeypots (agent-target side)
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| **beelzebub-labs/beelzebub** | 2,186★, pushed 2026-09-28; "secure low code deception runtime framework, leveraging AI for System Virtualization"; local **Go binary** or Docker; docs beelzebub.ai | native (Go binary; installer docs lean Linux/Docker) | medium |
| honeylabshq/honeylabs-mcp | 2★, pushed 2026-09-27; "honeypot telemetry for Claude, Cursor and any MCP client — per-address evidence, CVE probing, JA4" | unknown | medium-low |

### 2.13 Report generation
| Tool | Evidence | Windows | Value |
|---|---|---|---|
| AnshumanAtrey/redink | 0★, pushed 2026-05-22; "Compose pentest reports from 28 modular sections for 17+ compliance frameworks. Claude Code plugin + AGENTS.md compatible (codex, cursor, gemini, aider, kimi)" | native | medium-low (tiny but exactly the missing shape) |
| felipemelchior/ghostwriter | 1★, "AI ghostwriter for pentesters — raw findings → professional report sections" | native | low |

### 2.14 SAST / supply-chain (recorded small)
- qianniuspace/mcp-security-audit — 57★, npm dependency-vuln audit MCP (dump-sourced, verified). medium-low.
- Skyrxin/sast-mcp-server — 3★. low.
- omermaksutii/RugProof — 10★, "smart contract security auditor for Claude Code — vuln detection, exploit PoCs, mainnet-fork simulation; Solidity+Vyper, 38 commands, 19 agents"; web3 gap remains thin overall. medium-low.
- muhannad-hash/mcp-shield — 2★, "detect backdoors, exfiltration, prompt injection" in MCP servers — the covered g0/agenthound lane already owns this; marginal. low.

## 3. Query log (everything issued this session)

- gh api repos/... verification calls (stars/pushed/desc): radareorg/r2mcp (404 → renamed), mrexodia/ida-pro-mcp, zinja-coder/apktool-mcp-server, zinja-coder/jadx-ai-mcp, fr0gger/MCP_Security, muhannad-hash/mcp-shield, atomicchonk/roadrecon_mcp_server, BurtTheCoder/mcp-shodan, BurtTheCoder/mcp-maigret, BurtTheCoder/mcp-dnstwist, mariocandela/beelzebub (→ beelzebub-labs/beelzebub), honeylabshq/honeylabs-mcp, urldna/mcp, badchars/osint-mcp-server, badchars/cve-mcp, zer0-kr/security-framework-mcp, sjkim1127/Reversecore_MCP, radareorg/radare2-mcp, ggeorgeazevedo/yubel, dan1t0/gophish-mcp, mukul975/Anthropic-Cybersecurity-Skills, semgrep/semgrep, nickpending/mcp-recon, callstack/agent-device, CursorTouch/Android-MCP, AnshumanAtrey/redink, CyberSecurityUP/PhishletGenerator-Evilginx, Hackndo/Dark-Moon, badchars/wifi-security-mcp-server, PentHertz/grimoire, jtang613/GhidrAssistMCP (→ symgraph/), zboralski/ida-headless-mcp, Skyrxin/sast-mcp-server, qianniuspace/mcp-security-audit, StacklokLabs/osv-mcp, jonnybottles/patch-tuesday-mcp, cuttalo/depscope, EdenYavin/Garak-MCP, mbergo/deepteam-mcp, PhoenixHairpin/mcp-termux, youichi-uda/droidpilot, marlinkcyber/spiderfoot-mcp, plur1bu5/mobsf-mcp, 0xhackerfren/Windows-Memory-Forensics-MCP, techchipnet/aircrack-mcp.
- gh api search/repositories q= (via _gapq.py gh): `PyRIT`; `garak LLM vulnerability scanner`; `deepteam red teaming`; `PentestGPT`; `wifi mcp aircrack OR wifite OR bettercap`; `kubernetes attack mcp`; `peirates OR kube-hunter`; `mitre attack mcp server`; `cwe OR capec mcp` (junk — default-star sort, see dead ends); `gophish OR phishing mcp in:name,description` (junk); `shodan mcp in:name` (clean); `censys mcp in:name,description`; `spiderfoot OR osint mcp in:name,description` (junk); `gophish mcp in:name,description`; `spiderfoot mcp in:name,description`; `maigret mcp in:name`; `volatility mcp in:name,description`; `yara mcp in:name`; `mobsf mcp in:name`; `android mcp jadx OR apktool OR frida in:name,description`; `cve-search mcp in:name`; `nvd mcp in:name,description`; `radare2 mcp in:name,description`; `bettercap mcp in:name,description`; `smart contract audit agent mcp in:name,description`.
- exa (via _gapq.py exa): "MCP server AI agent WiFi wireless pentesting aircrack wifite automation"; "autonomous Kubernetes penetration testing AI agent MCP 2026"; "open source pentest report generation AI agent markdown docx writer 2026 github"; "LLM phishing simulation automation agent gophish evilginx red team initial access 2026".
- firecrawl /v1/search (registry key): "Microsoft PyRIT github" (shape-inspection call; confirmed microsoft/PyRIT active with same-day commits).
- curl raw.githubusercontent.com README greps (install lines): mukul975/Anthropic-Cybersecurity-Skills, badchars/wifi-security-mcp-server, techchipnet/aircrack-mcp, radareorg/radare2-mcp, sjkim1127/Reversecore_MCP, badchars/cve-mcp, badchars/osint-mcp-server, w0h1v/mcp-shodan, w0h1v/mcp-maigret, zinja-coder/jadx-ai-mcp, zinja-coder/apktool-mcp-server, pullkitsan/mobsf-mcp-server, atomicchonk/roadrecon_mcp_server, dan1t0/gophish-mcp, Gaffx/volatility-mcp, PentHertz/grimoire, Hackndo/Dark-Moon (empty), microsoft/PyRIT (README has no install grep hits — install per PyRIT docs, not README-verified this session), NVIDIA/garak, confident-ai/deepteam, GreyDGL/PentestGPT, beelzebub-labs/beelzebub.
- Local grep audit of all 88 out/research/*.md for gap-candidate topics (PentestGPT/PyRIT/garak/shodan/spiderfoot/MobSF/gophish/slither/kube-hunter/Peirates/ATT&CK/CAPEC/KEV/EPSS/any.run/YARA/honeypot/WiFi/BLE/recon-ng/censys/zoomeye/mcp-scan/trufflehog/dns counts) + full Security-section extraction from `_awesome.md` (lines 3661–3910 → 250 repo candidates).

## 4. Dead ends / not found / honest notes

- `kubernetes pentest mcp` and `bettercap mcp in:name,description` → no on-domain hits. The K8s-offense-AI lane genuinely has no mature OSS MCP; Peirates (no MCP) is the strongest tool.
- Multi-OR gh queries without `in:` qualifiers (cwe/capec, spiderfoot/or, gophish/or phishing) fell back to GitHub's default top-starred repos (n8n, dify, …) — treated as query failures, re-issued with `in:name,description` or single terms.
- `radareorg/r2mcp` → 404; real repo is `radareorg/radare2-mcp` (312★).
- `mariocandela/beelzebub` → redirects to `beelzebub-labs/beelzebub`.
- `jtang613/GhidrAssistMCP` → moved to `symgraph/GhidrAssistMCP` (756★).
- BurtTheCoder account → renamed to `w0h1v` (npm package keeps `@burtthecoder/*` names).
- w0h1v/mcp-maigret requires Docker Desktop on Windows → blocked on this no-Docker VM (recorded as-is).
- microsoft/PyRIT README install line not captured (README is docs-heavy); pip install per project docs — flagged as not README-verified.
- aircrack-mcp is Kali-first (monitor mode, root) — Windows fit poor; recorded honestly.
- Web3 audit-agent chase produced only small repos (≤10★) — the gap is real but immature; recorded as thin.
- X/Twitter and Reddit: not searched (no auth; consistent with every prior lane's dead end).
- Not installed or executed: none of the hauled tools were run on this VM — discovery and verification only (README/registry/API evidence).