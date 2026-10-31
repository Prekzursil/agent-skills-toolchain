---
title: mcp-tool-hubs
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/mcp-tool-hubs
---

# Research: mcp-tool-hubs (MCP security tool hubs + nmap/nuclei/sqlmap/ffuf/BloodHound bundlers)

Date: 2026-09-29. VM: Windows Server (no Docker engine, GCP no VT-x). Estate: CyberStrike 1.1.16 + MCP gateway 127.0.0.1:31100 (43 backends, 17 live: exa/tavily/firecrawl, nuclei, nmap, hexstrike :8888, hacktricks, decepticon, cheatengine/binary-ninja/chrome-devtools, zai-keys, frida/mitmproxy/caldera rpc), Decepticon local+upstream, PentAGI staged docker-pending, Ollama qwen3:4b.

## Local environment checks (run this session, Git Bash on the VM)

```
$ python --version; node --version; uv --version; where nmap; where nuclei; where ffuf; where sqlmap; where go
Python 3.12.10
v24.21.0
uv 0.12.20 (2274b80d6 2026-09-28 x86_64-pc-windows-msvc)
C:\Users\prekzursil\.local\bin\nuclei.exe
C:\Users\prekzursil\.local\bin\ffuf.exe
C:\Python314\Scripts\sqlmap.exe
(no nmap, no go on PATH in this shell)
```

→ nuclei, ffuf, sqlmap binaries ALREADY exist natively on this box; node + uv fresh. This is the linchpin fact: the FuzzingLabs hub's per-tool MCP servers are pure-Python stdio wrappers that shell out to exactly these binaries, so they run WITHOUT Docker here.

## Lineage discovery (verified via gh api)

- Estate's "CyberStrike 1.1.16" == `cyberstrikeus/CyberStrike` tag **v1.1.16** published 2026-08-13 — the LATEST release (releases list checked: v1.1.16 > v1.1.15 > ... > v1.1.9).
- `cyproxio/mcp-for-security` (629★) is **UNMAINTAINED**; README banner: "All tools have been migrated to Bolt — github.com/cyberstrikeus/bolt".
- `cyberstrikeus/bolt` (64★, AGPL-3.0) = same org as the estate's CyberStrike harness. 33 tools (nmap/nuclei/ffuf/sqlmap/hashcat/impacket/kerbrute/hydra/...), TypeScript/Bun, Docker-recommended (ghcr.io/cyberstrikeus/bolt), native TS plugins + external stdio MCP servers aggregated. Plugin `check` uses Unix `which` → native Windows unverified.

## Haul

### 1. FuzzingLabs/mcp-security-hub — THE "MCP Security Hub" (796★, pushed 2026-04-08)
- README badges: **38 MCP servers / 300+ tools / Docker-ready** (out/research/_fuzzinglabs_readme.md lines 11-13).
- Bundles exactly the ask's tools: nmap-mcp (8 tools), nuclei-mcp (7), sqlmap-mcp (8), ffuf-mcp (9), bloodhound-mcp (75+ tools, wrapper of MorDavid/BloodHound-MCP-AI), hashcat, masscan, whatweb, searchsploit, gitleaks, radare2/binwalk/yara/capa, trivy/prowler/roadrecon, semgrep, maigret/dnstwist, VT/OTX, medusa/dharma fuzzers, mcp-scan.
- **Native viability verified from code**: `reconnaissance/nmap-mcp/` contains only `Dockerfile, README.md, requirements.txt, server.py`; requirements.txt = `mcp>=1.0.0, pydantic>=2.0.0, pydantic-settings>=2.0.0` (no docker libs); server.py builds `cmd = ["nmap", "-oX", str(xml_output), ...]` and parses nmap XML — i.e., Docker is packaging only; with nmap.exe on PATH + Python 3.11+ it runs natively over stdio. sqlmap-mcp/ffuf-mcp server.py use the same `cmd = [...]` + `.extend(flags)` construction (grep run this session). Output dirs default to `/app/output` but are env-overridable (`NMAP_OUTPUT_DIR` etc.).
- Install (native path): `git clone https://github.com/FuzzingLabs/mcp-security-hub` → per server: `pip install -r <server>/requirements.txt` then run `python <server>/server.py` as stdio MCP child (gateway already does managed stdio workers). Docker path (README): `docker-compose build && docker-compose up nmap-mcp nuclei-mcp -d`.
- Windows: **native** (each server is an independent Python stdio process; underlying tool must be on PATH; ffuf/nuclei/sqlmap already present, nmap is not on PATH in this shell).
- Value: **high** — one maintained repo closes exactly the estate's gaps (sqlmap, ffuf, bloodhound, hashcat, masscan, searchsploit) without Docker.

### 2. nedlir/MCPwner (55★, pushed 2026-08-20) — "Beware the Badger"
- README (out/research/_mcpwner_readme.md line 38): 55+ containerized tools — SAST (CodeQL builtin+custom, semgrep, joern, opengrep...), SCA, secrets, IaC, recon (nmap, masscan, ffuf, subfinder, amass, bbot, httpx, katana...), DAST (sqlmap, nosqlmap, commix, dalfox, SSTImap, SSRFmap, jwt_tool, interactsh), source fuzzing (atheris/jazzer), PoC-script sandbox with deterministic oracles, findings ledger (deep-merge upserts), headless Chromium, mitmproxy, WireMock. Plugin system (wp-scan).
- Architecture: MCP server (Python) probes running Docker containers, registers only healthy tools; MCP entry = `docker exec -i mcpwner-server python src/server.py`.
- Prerequisites (README lines 187-193): Docker Engine 20.10+, Compose 2.0, "Windows (with WSL2)".
- Install: `git clone https://github.com/nedlir/mcpwner.git && cd mcpwner && cp .env.example .env && cp config/config.yaml.example config/config.yaml && docker compose up -d --build`.
- Windows: **docker** (hard requirement; no VT-x on this GCP box → blocked today; candidate to stage next to PentAGI).
- Value: **medium** — deepest single-hub capability set (CodeQL + PoC oracle + ledger is unique), but Docker-gated on this estate.

### 3. cyberstrikeus/bolt (64★, pushed 2026-04-03) — same vendor as estate's CyberStrike
- 33 tools: nmap, nuclei(+template update), ffuf, sqlmap, hashcat, john, hydra, medusa, kerbrute, impacket, commix, smuggler, wpscan, sslscan, rustscan, masscan, gobuster, arjun, katana, subfinder/amass/... , scoutsuite, run_command.
- Install: `docker run -d --name bolt -p 3001:3001 -e MCP_ADMIN_TOKEN=$(openssl rand -hex 32) --cap-add NET_RAW --cap-add NET_ADMIN -v bolt-data:/data ghcr.io/cyberstrikeus/bolt:latest` (or `curl -fsSL https://bolt.cyberstrike.io/install.sh | sudo sh`).
- Windows: **docker** (dev runtime is bun; plugin install-check uses `which` → native Windows unverified).
- Value: **medium** — in-family upgrade path for the estate's existing CyberStrike deployment; Docker-gated.

### 4. cyproxio/mcp-for-security (629★, pushed 2026-03-30) — predecessor hub, UNMAINTAINED
- 22 tool MCPs (nmap, nuclei, sqlmap, ffuf, masscan, amass, wpscan, mobsf, scoutsuite, sslscan, smuggler, httpx, katana, gowitness...). README warning: repo no longer maintained, migrated to bolt. `f1tz/mcp-for-security-python` (41★) = Chinese Python port; `StanLeyJ03/mcp-for-security` (20★) = fork.
- Value: **low** (superseded; estate already has newer lineage).

### 5. DMontgomery40/pentest-mcp (146★, pushed 2026-03-23)
- Single Node MCP server (`npm install -g pentest-mcp`), v0.9.0: stdio + Streamable HTTP + SSE, bearer/OIDC auth. Tools: `nmapScan, runJohnTheRipper, runHashcat, gobuster, nikto, subfinderEnum, httpxProbe, ffufScan, nucleiScan, trafficCapture, hydraBruteforce, privEscAudit, extractionSweep, generateWordlist, createClientReport, cancelScan` (+ engagement records, SoW elicitation).
- Node 22.7.5+ baseline; this VM has node v24.21.0 ✓. No sqlmap/BloodHound.
- Windows: **native**.
- Value: **medium** — bundles nmap+ffuf+nuclei in ONE native server with reporting; overlaps live backends but zero-Docker.

### 6. shinthink/blitzstrike (488★, pushed 2026-09-29 — active today)
- TS/Bun methodology MCP: BLITZ (attack-surface triage) / EAGLE-EYE (source→sink taint) / STRIKE (live verify with marker + negative control) + `run_engagement` one-call; 130-tool catalog (tools-catalog.json) incl. sqlmap, nuclei, ffuf, bloodhound, netexec, impacket, certipy, kerbrute with per-platform install commands + `ensure_tool(name)` auto-install; 317+ tool manuals; nuclei template lookup (11.9k), PayloadsAllTheThings payload DB; append-only memory JSONL.
- Install: `npx -y blitzstrike doctor && npx -y blitzstrike install` (auto-registers into detected agent CLIs).
- Windows: **native** (bun/node; catalog per-platform install commands exist — not verified on Windows in this session).
- Value: **medium** — methodology + verification layer complements (not duplicates) hexstrike; overlaps gateway's existing scan fronts.

### 7. MorDavid/BloodHound-MCP-AI (377★, pushed 2025-06-02)
- 75+ tools based on BloodHound CE Cypher queries; natural-language AD attack-path analysis. Prereqs: BloodHound 4.x+ data in **Neo4j** (bolt://), Python 3.8+. MCP config passes `BLOODHOUND_URI=bolt://localhost:7687`, user/pass.
- Windows: **native** (pure Python + neo4j driver; needs a Neo4j with collected data — Neo4j runs natively on Windows; SharpHound collectors run on Windows).
- Value: **high** — the only serious AD attack-path MCP; this is a Windows-domain estate; FuzzingLabs hub wraps it as `active-directory/bloodhound-mcp`.

### 8. mwnickerson/bloodhound_mcp (136★, pushed 2026-08-19, GPLv3)
- 13 composite tools (`domain_info`, `user_info`, `graph_analysis`, `adcs_info`, `cypher_query`, `file_upload`...) + 10 reference resources (offensive Cypher library, AD/Azure/ADCS methodology) + system prompt. Talks to **BloodHound CE/Enterprise REST API** (token id/key), read-only `/api/v2/self` startup check.
- Install: `uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp` (uv 0.12.20 present on VM ✓). Python 3.11+.
- Windows: **native** (needs reachable BH CE instance).
- Value: **medium** — cleaner token-efficient interface than MorDavid; requires standing up BH CE (its API is a Go binary that runs on Windows, though normally Dockerized).

### 9. ktol1/RedTeam-Agent (72★, pushed 2026-04-24)
- Chinese/English AI red-team framework, skill-first terminal workflow; 15+ tools with automated setup: gogo, fscan, httpx, nuclei, ffuf, SharpHound/bloodhound-python, impacket suite, nxc/NetExec, pywerview, ldapdomaindump. README explicitly supports **Windows 10/11** with `python scripts/install_tools.py` (PowerShell venv instructions included).
- Windows: **native**.
- Value: **medium** — the Windows-native AD chain (SharpHound→BloodHound→impacket→nxc) installer is exactly the manual wiring this estate lacks.

### 10. drcrypterdotru/sqlmap-skynet (98★, v1.2.0, pushed 2026-02-26)
- Autonomous AI sqlmap orchestration: Targets → Preflight → Phased Scan → AI Assist → Evidence → Report; FastMCP CLI mode "Best for Windows + Linux servers (headless / no GUI)"; MCP URL + targetlist scans. sqlmap.exe already on this VM.
- Windows: **native**.
- Value: **medium** for deep SQLi work; overlaps generic sqlmap-mcp.

### 11. redlightconsole/mcpwn (0★, pushed 2026-09-03) — name-collides with MCPwner
- Go MCP server (official modelcontextprotocol/go-sdk), YAML-configurable tools: nmap, subfinder, dnsx, gobuster, ffuf, httpx, sqlmap, msfvenom, msfconsole; bounded output + persisted outputs; optional Docker execution; "compiles for Linux, macOS, and Windows" via GoReleaser — but **no releases published yet** (releases API returned empty) → build from source with Go (Go NOT on this VM's PATH).
- Value: **low** (unreleased), on-target design.

### 12. CommonHuman-Lab/nyxstrike (152★)
- "200+ tools · 50+ categories · AI decision engine · tamper-evident evidence chain", dashboard on :8888 (same port as estate's hexstrike — would clash), `./nyxstrike.sh` bash installer → Linux-first.
- Windows: **wsl**. Value: **low** for this estate (hexstrike already live; bash-based).

### 13. hackersatyamrastogi/pentesting-cyber-mcp (29★)
- 50 TypeScript MCP servers (nmap, nuclei, sqlmap, ffuf, bloodhound, metasploit, crackmapexec, ghidra, k8s trio, nessus/zap/burp commercial wrappers) + `unified` all-in-one. Windows: **native** (Node). Value: **low** (thin wrappers, some wrap tools that need licenses).

### 14. Ed1s0nZ/SecurityMCP-Hub (8★, pushed 2026-01-09)
- Chinese hub; only fofa-mcp + zoomeye-mcp implemented (Go, stdio, native Windows compiles); nmap/nuclei/sqlmap still 计划中 (planned). Value: **low**.

### 15. 0x4m4/hexstrike-ai (12,240★, v6.0, pushed 2026-08-03) — already deployed in estate (:8888)
- Upstream for the estate's live hexstrike backend. v6.0.0: 150+ tools, 12+ autonomous agents. Not re-recommended (already live); noted for version tracking.

### Adjacent finds (recorded, out of core scope)
- `i3T4AN/Kali_Linux_MCP` (10★) Flask API + MCP bridge, Docker/Kali. `yashpatil118/PENTEST-MCP-SERVER` (7★) Kali Docker (nmap/nikto/sqlmap/wpscan/dirb/searchsploit).
- `asaotomo/FofaMap` (733★) FOFA recon agent w/ approved nuclei scanning. `owl234/ARL-Next` (447★) asset platform w/ native MCP (containerized).
- `sfr-development/WonderSuite-Ai-Bug-Bounty` (51★) Tauri/Rust desktop, 90 tools, native MCP — desktop GUI, not gateway-friendly.
- Per-tool standalones: `addcontent/nuclei-mcp` (49★), `crazyMarky/mcp_nuclei_server` (21★, bilingual), `vorotaai/nmap-mcp` (16★), `PhialsBasement/nmap-mcp-server` (48★), `imjdl/nmap-mcpserver` (19★), `mohdhaji87/SQLMap-MCP` (7★, FastMCP), `schwarztim/sec-ffuf-mcp` (0★), `samcsta/mcp-ffuf` (0★). ffuf has NO high-star standalone — it lives only inside hubs (cyproxio lineage / FuzzingLabs / bolt / pentest-mcp).
- Curated lists swept: `Puliczek/awesome-mcp-security` (204-line README, all entries checked — MorDavid/addcontent/semgrep etc., no missed hub), `R00T-Kim/awesome-offensive-mcp` (27★, checked — same names).

## Key conclusions for the estate
1. **The 300+ tool "MCP Security Hub" is FuzzingLabs/mcp-security-hub and it is Docker-optional in practice**: every per-tool server is a standalone Python stdio process that just exec's the tool binary; nuclei.exe/ffuf.exe/sqlmap.exe are already on this VM. Cherry-picking `sqlmap-mcp`, `ffuf-mcp`, `bloodhound-mcp`, `hashcat-mcp`, `searchsploit-mcp`, `whatweb-mcp`, `masscan-mcp` as managed stdio workers behind the 31100 gateway replaces manual wiring with zero Docker. nmap/nuclei wrappers are redundant (backends already live).
2. **MCPwner is the deepest hub but hard-blocked on Docker** (same bucket as PentAGI: stage for whenever nested-virt/VT-x or a remote Docker host appears).
3. **bolt is the estate vendor's own tool-hub** (cyberstrikeus org = CyberStrike 1.1.16): in-family upgrade, Docker-recommended.
4. **AD gap closers**: MorDavid/BloodHound-MCP-AI (377★, bolt→Neo4j, native) or mwnickerson/bloodhound_mcp (BH CE REST); RedTeam-Agent's Windows installer for the collection chain.
5. Name collision to remember: `MCPwner` (nedlir, Docker fleet) ≠ `mcpwn` (redlightconsole, Go single binary).

## Every query issued (chronological)
WebSearch:
1. `MCPwner MCP server security tools containerized GitHub`
2. `"MCP Security Hub" 300 security tools Model Context Protocol` (+ auto-variants: `MCP Security Hub Model Context Protocol security tools`, `MCP security tools directory 300 servers Model Context Protocol`)
3. `MCP 服务器 安全工具集合 nmap nuclei sqlmap 内网渗透 2026` (+ auto-variants incl. `security MCP server collection nmap nuclei sqlmap github`, `MCP 渗透测试工具 sqlmap nmap 集成 Model Context Protocol`)
4. `mcp-security-hub run without docker native python windows` (+ auto-variants: `mcp-security-hub GitHub python install`, `"mcp-security-hub"`, `mcp-security-hub github`, `"mcp-security-hub" docker python`, `mcp-security-hub repository` site-filtered) — hit web_search rate limit -429 mid-way; nothing new.

GitHub API (`gh api search/repositories`):
5. `q=MCPwner`
6. `q=mcp+security+hub`
7. `q=nmap+mcp+server`
8. `q=nuclei+mcp`
9. `q=bloodhound+mcp`
10. `q=sqlmap+mcp`
11. `q=ffuf+mcp`
12. `q=hexstrike`
13. `q=offensive+security+mcp` (sort=stars)

Repo reads (`gh api repos/<r>/readme` and `/contents/...`):
14. FuzzingLabs/mcp-security-hub (readme; contents: reconnaissance/nmap-mcp/ dir + server.py + requirements.txt; web-security/ffuf-mcp/ dir + server.py; web-security/sqlmap-mcp/server.py)
15. nedlir/MCPwner (readme)
16. Ed1s0nZ/SecurityMCP-Hub (readme)
17. cyproxio/mcp-for-security (readme)
18. cyberstrikeus/bolt (readme; tags; releases; org repo list) + cyberstrikeus/CyberStrike releases (v1.1.16 confirmed)
19. DMontgomery40/pentest-mcp (readme)
20. hackersatyamrastogi/pentesting-cyber-mcp (readme)
21. MorDavid/BloodHound-MCP-AI (readme)
22. mwnickerson/bloodhound_mcp (readme)
23. shinthink/blitzstrike (readme)
24. ktol1/RedTeam-Agent (readme)
25. redlightconsole/mcpwn (readme; releases → empty)
26. 0x4m4/hexstrike-ai (readme head)
27. stevenyu113228/BloodHound-MCP (readme head)
28. drcrypterdotru/sqlmap-skynet (readme head)
29. Puliczek/awesome-mcp-security (readme, full link extraction)
30. R00T-Kim/awesome-offensive-mcp (readme, full link extraction)
31. CommonHuman-Lab/nyxstrike (readme head)

Local commands run:
32. `python --version; node --version; uv --version; where nmap; where nuclei; where ffuf; where sqlmap; where go`

Dead ends / not reachable:
- WebSearch "MCP Security Hub" as a standalone product found nothing except FuzzingLabs repo (GitHub search resolved it); Backslash's hosted "MCP Server Security Hub" (adversa.ai mention) is a posture-rating database, not a tool hub — out of scope.
- mcpwn (redlightconsole) has no published releases despite GoReleaser claims in README.
- Could not verify bolt/blitzstrike/nyxstrike actually running on Windows (would require installs beyond this research lane); native ratings rest on README + runtime presence (node/uv) + code reading of the FuzzingLabs Python servers only.

Raw README dumps saved alongside: out/research/_fuzzinglabs_readme.md, _mcpwner_readme.md, _ed1s0nz_readme.md, _cyproxio_readme.md, _bolt_readme.md, _pentestmcp_readme.md, _satyam_readme.md, _bloodhoundai_readme.md, _mwnickerson_readme.md, _blitzstrike_readme.md, _redteam_readme.md, _mcpwn_readme.md, _awesome_sec_readme.md.

---

# SECOND PASS — independent verification + additions (merged from parallel lane instance, 2026-09-29)

A second instance of this same research lane ran concurrently on this VM (shared out/research/ cache files, timestamps 17:14–17:30, and the shared gh 5000/hr quota explains the 403 burst both instances hit). Everything above that this pass re-derived was independently re-verified; discrepancies and additions below.

## Re-verified in the second pass (commands actually run)
- `gh api repos/FuzzingLabs/mcp-security-hub` → 796★, MIT, Python, pushed 2026-04-08, 7 open issues, homepage fuzzinglabs.github.io/mcp-security-hub. README re-read in full: 38 servers / 300+ tools badge; catalog matches §1 above.
- `gh api repos/FuzzingLabs/mcp-security-hub/contents/reconnaissance/nmap-mcp/server.py` (raw) → line ~209 `cmd = ["nmap", "-oX", str(xml_output), "-oN", str(txt_output)]`, line ~243 `await asyncio.create_subprocess_exec(*cmd, …)` — confirms native exec of host binary.
- `…/web-security/nuclei-mcp/server.py` + `requirements.txt` (raw) → deps only `mcp>=1.0.0, pydantic>=2.0.0, pydantic-settings>=2.0.0`; output dirs env-overridable (`NUCLEI_OUTPUT_DIR` alias seen in Settings class).
- `gh api repos/FuzzingLabs/mcp-security-hub/contents/active-directory` → **`bloodhound-mcp` EXISTS**; its README (raw) confirms "wraps MorDavid/BloodHound-MCP-AI… 75+ specialized query functions based on BloodHound's Cypher queries" — the FuzzingLabs hub is therefore a one-stop shop covering the ask's full tool list (nmap/nuclei/sqlmap/ffuf/BloodHound).
- `gh api repos/nedlir/MCPwner` (+readme, Installation section) → 55★, Apache-2.0, Python 3.11+, pushed 2026-08-20, 0 open issues; "Docker Engine 20.10+ and Docker Compose 2.0+… Windows (with WSL2)"; MCP entry `docker exec -i mcpwner-server python src/server.py`; root listing shows docker-compose.yaml + docker/ + mcp.json.example. Docker = hard requirement (blocked on this estate).
- `gh api repos/DMontgomery40/pentest-mcp` → 146★, MIT, JavaScript, pushed 2026-03-23 — description confirms nmap/dirbuster/nikto/JtR/hashcat + STDIO/HTTP/SSE. (§5 above now source-verified.)
- `gh api repos/cyproxio/mcp-for-security/readme` → unmaintained banner + migration pointer to cyberstrikeus/bolt re-read: predecessor hub confirmed dead upstream.
- `gh api repos/CyberStrikeus/bolt` (+readme) → 64★, TypeScript, pushed 2026-04-03, **license reported by API as NOASSERTION** (§3 above says AGPL-3.0 — the API does not resolve it; treat license as custom/unresolved until checked in-repo). Architecture re-confirmed: native TS plugins (subfinder/nmap/nuclei/httpx/ffuf/run-command) + external stdio/HTTP MCP servers (alterx/amass/sqlmap shown), `bolt.config.json`, namespaced tools, 33-tool table.
- `gh api repos/MorDavid/BloodHound-MCP-AI/readme` (install section) → MCP env `BLOODHOUND_URI=bolt://localhost:7687`, `BLOODHOUND_USERNAME`, `BLOODHOUND_PASSWORD`; single-file `BloodHound-MCP.py` + requirements.txt (contents listing). Stale since 2025-06-02 but self-contained.
- `gh api repos/mwnickerson/bloodhound_mcp/readme` (install) → `uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp`, env BLOODHOUND_DOMAIN/TOKEN_ID/TOKEN_KEY, read-only `/api/v2/self` startup probe; GPLv3; freshest BloodHound MCP (2026-08-19). Covered by SpecterOps blog post (exa hit).
- `gh api repos/hackersatyamrastogi/pentesting-cyber-mcp/contents/servers/bloodhound/src/index.ts` (raw) → `Usage: mcp-bloodhound <neo4j-url> <neo4j-password>`; converts bolt://…:7687 to Neo4j HTTP :7474 `/db/neo4j/tx/commit`, Basic auth, arbitrary Cypher; tool `bloodhound-path-to-da` confirmed. Node 18+, `pnpm install && pnpm build`, binary path as argv → Windows-native given tool binaries.

## New candidates found ONLY in the second pass (not in §Haul above)
- **JameZUK/Arkana** — https://github.com/JameZUK/Arkana, 238★, MIT, Python 3.10+, pushed 2026-09-12. "Your entire malware analysis lab, behind one AI prompt" — **308 MCP tools** for binary analysis: angr decompilation + symbolic execution, data/control-dependency queries, signature engines, emulation, interactive debugging with breakpoints (VirtualAlloc/VirtualProtect) and memory snapshots. Found via Ed-Marcavage/awesome-security-agent-harnesses walk. Complements the estate's binary-ninja/cheatengine stdio workers. Windows: likely native (Python), NOT install-tested; `docs/installation.md` not read. Value: **medium-high**.
- **tidynest/raven-nest-mcp** — 2★, Apache-2.0, Rust v0.4.1, pushed 2026-09-23. 46 MCP tools wrapping 22 tools + optional Metasploit (incl. nmap, nuclei, sqlmap, ffuf, hydra, john, netexec, testssl.sh, enum4linux-ng) with safety hardening, findings persistence, SARIF/HTML reports (README read). Distribution = Docker image; several wrapped tools are Linux-only → low fit. Value: **low-medium**.
- **GH05TCREW/MetasploitMCP** — 733★, pushed 2026-02-05. msfrpcd bridge (list_exploits/payloads, run_exploit, session mgmt, generate_payload; README read). Needs Metasploit RPC daemon (Linux/remote) — not runnable natively on this Windows box. Value: **low** (only with a remote Kali host).
- **err0n-0x2A/bhe_mcp** — 0★, GPL-3.0, pushed 2026-05-15; fork of mwnickerson/bloodhound_mcp retargeted at BloodHound **Enterprise** API (README read). Relevant only if BHE is ever licensed.
- **stevenyu113228/BloodHound-MCP** — 160★ but pushed 2025-04-04 (stale); Neo4j-based AD+Azure NL queries (README head read). Superseded by fresher options.
- **Ed-Marcavage/awesome-security-agent-harnesses** (25★, pushed 2026-09-22) — walked in full; confirmed estate-relevant entries (CyberStrike, HexStrike, PentAGI, PortSwigger mcp-server, Arkana) and added nothing else hub-shaped.
- Minor/recorded-not-deep-read: rfunix/tengu (61★), ente0/mcpstrike (13★; nmap/nikto/sqlmap/dalfox + Ollama autonomous client — interesting given local Ollama qwen3:4b), azmisyahrul/prismsec, openbashok/pentest-mcp, NeveuGregor/mcp-noctua, sudohakan/kali-mcp-server, chfle/Pentest-MCP-Server, CyberMaster000/Cyber-Master-MCP, valITino/blhackbox, acaranta/hexstrike-docker-mcp (Docker re-wrap of hexstrike → redundant, estate already runs hexstrike :8888).
- **Name-caveat**: `tiluckdave/hound-mcp` (17★, npm `npx -y hound-mcp`) is NOT BloodHound — it is a deps.dev/OSV dependency-vulnerability scanner (README read). Excluded from the BloodHound lane despite the name.
- Fresh-2026 sweep (`q=mcp+pentest+created:>2026-04-01&sort=stars`): top results were harnesses/skills (0xSteph/pentest-ai 1708★, uphiago/recon-skills 1284★, owl234/ARL-Next 447★) — no new tool-bundling hub beyond blitzstrike (already recorded).

## Second-pass query log
Exa (POST api.exa.ai/search; key valid):
1. `MCP server that bundles nmap nuclei sqlmap ffuf offensive security tools for LLM agents` (10 results)
2. `MCP server exposing BloodHound Cypher attack path analysis to AI agent natural language` (8; incl. SpecterOps blog + glama listing)
3. `BloodHound Enterprise MCP server bhe_mcp github` (6)
4. `Arkana MCP server 308 binary analysis tools JameZUK` (5)
5. `security MCP server hub collection many tools one server no docker windows` (8; mcp-security-hub as top repeat hit = convergence signal)

Firecrawl — **DEAD**: `POST /v1/search` × 2 and `POST /v1/scrape` × 1 all returned `{"success": false, "error": "Unauthorized: Invalid token"}`. The env FIRECRAWL_API_KEY is invalid/expired on both endpoints. Worked around with Exa + gh (+ ddgs 9.16.0 installed as keyless fallback, not needed).

GitHub API (gh CLI): `search/repositories` q= mcpwner / mcp+security+hub / bloodhound+mcp / active-directory+mcp+server+attack / mcp-server+topic:offensive-security (sort=updated) / sqlmap+mcp / ffuf+mcp / metasploit+mcp / mcp+pentest+created:>2026-04-01 (sort=stars); repo reads: FuzzingLabs (meta + readme + nmap-mcp dir/server.py + nuclei-mcp server.py/requirements + active-directory dir + bloodhound-mcp README), MCPwner (meta + readme ×2 + contents), cyproxio readme, CyberStrikeus/bolt (meta + readme), GH05TCREW/MetasploitMCP readme, MorDavid readme ×2 + contents, mwnickerson readme ×2, stevenyu readme, err0n-0x2A/bhe_mcp meta+readme, JameZUK/Arkana meta+readme, blitzstrike readme ×2, raven-nest meta+readme, Ed1s0nZ readme, hackersatyamrastogi readme ×2 + servers/bloodhound contents + src/index.ts, DMontgomery40/pentest-mcp meta, Ed-Marcavage/awesome-security-agent-harnesses readme.
- Rate-limit event: `q=topic:red-team+topic:mcp-server` + `q=mcp+pentest+created:>2026-04-01` 403-failed at 17:27 UTC (shared 5000/hr exhausted by concurrent lanes); `gh api rate_limit` showed reset 18:27:44Z but quota returned to 5000 remaining within minutes; the fresh-2026 query was re-run successfully; the red-team topic query was NOT re-run (ground already covered by the offensive-security topic sweep).
- `gh auth status` → account Prekzursil, token OK.

## Net merge conclusions (unchanged + strengthened)
1. FuzzingLabs/mcp-security-hub native cherry-pick (sqlmap-mcp, ffuf-mcp, bloodhound-mcp, hashcat-mcp, whatweb-mcp, masscan-mcp, searchsploit-mcp, gitleaks-mcp) remains the #1 recommendation; the bloodhound-mcp wrapper is now source-verified present at `active-directory/bloodhound-mcp`.
2. MCPwner and bolt stay Docker-gated (stage beside PentAGI). Bolt license shows NOASSERTION via API — resolve before any redistribution.
3. AD lane: MorDavid (bolt→Neo4j, native, stale but self-contained) or mwnickerson (BH CE REST, fresh, uvx) — pick by whether the estate stands up Neo4j (native) or BH CE (needs hosting).
4. Arkana is the notable binary-analysis hub addition for this RE-heavy estate.